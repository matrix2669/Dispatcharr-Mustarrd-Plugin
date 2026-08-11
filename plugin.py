"""Dispatcharr -> Mustarrd DVR handoff plugin.

Normal operation:
  * Dispatcharr remains the source of DVR intent / series rules.
  * Future recordings on non-catch-up channels are ignored.
  * At T-handoff_minutes (60 minutes by default), catch-up recordings are
    recreated in Mustarrd.
  * The Dispatcharr Recording row is deleted only after the Mustarrd schedule
    is read back and verified. Dispatcharr's post_delete signal then removes
    the native one-off DVR PeriodicTask.
  * Any failure is fail-safe: the Dispatcharr recording remains untouched.
"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

PLUGIN_KEY = "mustarrd-dvr-handoff"
DEFAULTS = {
    "mustarrd_url": "http://mustarrd:4177",
    "mustarrd_username": "",
    "mustarrd_password": "",
    "mustarrd_account_id": 1,
    "handoff_minutes": 60,
    "handoff_cron": "* * * * *",
    "dry_run": False,
}

TERMINAL_OR_ACTIVE_STATUSES = {
    "recording",
    "completed",
    "stopped",
    "interrupted",
}


class MustarrdError(RuntimeError):
    pass


class MustarrdClient:
    def __init__(self, base_url: str, username: str, password: str, timeout: int = 15):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.username = (username or "").strip()
        self.password = password or ""
        self.timeout = timeout
        self.session = requests.Session()
        self.csrf_token: str | None = None

    def close(self):
        self.session.close()

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def login(self):
        if not self.base_url:
            raise MustarrdError("Mustarrd URL is not configured")
        if not self.username or not self.password:
            raise MustarrdError("Mustarrd username/password are not configured")

        try:
            csrf = self.session.get(self._url("/api/auth/csrf"), timeout=self.timeout)
            csrf.raise_for_status()
            self.csrf_token = str(csrf.json().get("csrf_token") or "").strip()
            if not self.csrf_token:
                raise MustarrdError("Mustarrd did not return a CSRF token")

            response = self.session.post(
                self._url("/api/auth/login-credentials"),
                json={"username": self.username, "password": self.password},
                headers={"X-CSRF-Token": self.csrf_token},
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                raise MustarrdError(
                    f"Mustarrd authentication failed ({response.status_code}): {_response_detail(response)}"
                )
            payload = response.json()
            if not payload.get("authenticated"):
                raise MustarrdError("Mustarrd authentication did not establish a session")
        except requests.RequestException as exc:
            raise MustarrdError(f"Could not connect to Mustarrd: {exc}") from exc

    def get_json(self, path: str, params: dict | None = None):
        try:
            response = self.session.get(self._url(path), params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise MustarrdError(f"Mustarrd GET {path} failed: {exc}") from exc
        if response.status_code >= 400:
            raise MustarrdError(
                f"Mustarrd GET {path} failed ({response.status_code}): {_response_detail(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise MustarrdError(f"Mustarrd GET {path} returned invalid JSON") from exc

    def post_json(self, path: str, payload: dict):
        headers = {"X-CSRF-Token": self.csrf_token or ""}
        try:
            response = self.session.post(
                self._url(path), json=payload, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise MustarrdError(f"Mustarrd POST {path} failed: {exc}") from exc
        if response.status_code >= 400:
            raise MustarrdError(
                f"Mustarrd POST {path} failed ({response.status_code}): {_response_detail(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise MustarrdError(f"Mustarrd POST {path} returned invalid JSON") from exc


def _response_detail(response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            return str(data.get("detail") or data)
        return str(data)
    except Exception:
        text = (getattr(response, "text", "") or "").strip()
        return text[:300] or "unknown error"


def _load_settings() -> dict[str, Any]:
    from apps.plugins.models import PluginConfig

    settings = {}
    candidates = [PLUGIN_KEY, PLUGIN_KEY.replace("-", "_")]
    for key in candidates:
        try:
            cfg = PluginConfig.objects.get(key=key)
            settings = dict(cfg.settings or {})
            break
        except PluginConfig.DoesNotExist:
            continue
    return {**DEFAULTS, **settings}


def _coerce_int(value, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt_timezone.utc)
    return value.astimezone(dt_timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return _aware_utc(value)
    try:
        text = str(value).strip().replace("Z", "+00:00")
        return _aware_utc(datetime.fromisoformat(text))
    except (TypeError, ValueError):
        return None


def _epoch(value: datetime) -> int:
    return int(_aware_utc(value).timestamp())


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _program_window_from_recording(recording) -> tuple[datetime | None, datetime | None, dict]:
    cp = recording.custom_properties or {}
    program = cp.get("program") if isinstance(cp, dict) else None
    if not isinstance(program, dict):
        return None, None, {}
    return _parse_iso(program.get("start_time")), _parse_iso(program.get("end_time")), program


def _derive_padding(recording, original_start: datetime, original_end: datetime) -> tuple[int, int]:
    rec_start = _aware_utc(recording.start_time)
    rec_end = _aware_utc(recording.end_time)
    pre_seconds = max(0.0, (original_start - rec_start).total_seconds())
    post_seconds = max(0.0, (rec_end - original_end).total_seconds())
    pre = max(0, min(120, int(round(pre_seconds / 60.0))))
    post = max(0, min(120, int(round(post_seconds / 60.0))))
    return pre, post


def _program_key(account_id: int, channel_id: str, program: dict) -> tuple[int, str, int, int] | None:
    try:
        start_ts = int(program.get("start_timestamp") or 0)
        stop_ts = int(program.get("stop_timestamp") or 0)
    except (TypeError, ValueError):
        return None
    if start_ts <= 0 or stop_ts <= start_ts:
        return None
    return int(account_id), str(channel_id), start_ts, stop_ts


def _schedule_key(schedule: dict) -> tuple[int, str, int, int] | None:
    try:
        account_id = int(schedule.get("account_id"))
        channel_id = str(schedule.get("channel_id"))
        start_ts = int(schedule.get("start_timestamp") or 0)
        stop_ts = int(schedule.get("stop_timestamp") or 0)
    except (TypeError, ValueError):
        return None
    if start_ts <= 0 or stop_ts <= start_ts:
        return None
    return account_id, channel_id, start_ts, stop_ts


def _normalize_filename(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if text and not text.lower().endswith(".ts"):
        text += ".ts"
    return text


def _schedule_is_verified(schedule: dict, expected_key, pre: int, post: int, filename: str) -> bool:
    if _schedule_key(schedule) != expected_key:
        return False
    if int(schedule.get("pre_padding_minutes") or 0) != int(pre):
        return False
    if int(schedule.get("post_padding_minutes") or 0) != int(post):
        return False
    return _normalize_filename(schedule.get("custom_filename")) == _normalize_filename(filename)


def _find_rich_epg_program(programs: list[dict], recording) -> tuple[dict | None, str]:
    """Resolve the current Mustarrd EPG entry for an EPG-backed Recording."""
    original_start, original_end, source_program = _program_window_from_recording(recording)
    if not original_start or not original_end:
        return None, "manual"

    wanted_start = _epoch(original_start)
    wanted_stop = _epoch(original_end)
    exact = [
        p for p in programs
        if int(p.get("start_timestamp") or 0) == wanted_start
        and int(p.get("stop_timestamp") or 0) == wanted_stop
    ]
    if len(exact) == 1:
        return exact[0], "exact"
    if len(exact) > 1:
        return None, "ambiguous_exact"

    wanted_title = _normalize_text(source_program.get("title"))
    wanted_subtitle = _normalize_text(source_program.get("sub_title"))
    if not wanted_title:
        return None, "missing_title"

    candidates = []
    for program in programs:
        if _normalize_text(program.get("title")) != wanted_title:
            continue
        try:
            start_ts = int(program.get("start_timestamp") or 0)
            stop_ts = int(program.get("stop_timestamp") or 0)
        except (TypeError, ValueError):
            continue
        if not start_ts or not stop_ts:
            continue
        start_delta = abs(start_ts - wanted_start)
        stop_delta = abs(stop_ts - wanted_stop)
        if wanted_subtitle:
            candidate_subtitle = _normalize_text(program.get("subtitle"))
            if candidate_subtitle != wanted_subtitle:
                continue
            if start_delta > 30 * 60 or stop_delta > 30 * 60:
                continue
        else:
            if start_delta > 10 * 60 or stop_delta > 10 * 60:
                continue
        candidates.append((start_delta + stop_delta, program))

    if len(candidates) != 1:
        return None, "ambiguous_or_missing_shifted_match"
    return candidates[0][1], "shifted"


def _synthetic_program(recording) -> dict:
    start = _aware_utc(recording.start_time)
    end = _aware_utc(recording.end_time)
    title = f"{recording.channel.name} Recording"
    return {
        "id": None,
        "epg_id": None,
        "title": title,
        "description": "Manual recording handed off from Dispatcharr",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "start_timestamp": _epoch(start),
        "stop_timestamp": _epoch(end),
        "provider_start": None,
        "provider_stop": None,
        "duration_minutes": max(1, int(math.ceil((end - start).total_seconds() / 60.0))),
        "has_archive": True,
        "channel_id": str(recording.channel_id),
        "category": "",
    }


def _fetch_catchup_channels(client: MustarrdClient, account_id: int) -> dict[str, dict]:
    channels = client.get_json(
        f"/api/accounts/{account_id}/channels",
        params={"catchup_only": "true"},
    )
    if not isinstance(channels, list):
        raise MustarrdError("Mustarrd channel endpoint returned an unexpected payload")
    return {
        str(ch.get("stream_id")): ch
        for ch in channels
        if ch.get("stream_id") is not None
    }


def _fetch_schedules(client: MustarrdClient) -> list[dict]:
    schedules = client.get_json("/api/schedules")
    if not isinstance(schedules, list):
        raise MustarrdError("Mustarrd schedules endpoint returned an unexpected payload")
    return schedules


def _delete_dispatcharr_recording(recording_id: int, expected_start: datetime, expected_channel_id: int) -> bool:
    from django.db import transaction
    from django.utils import timezone
    from apps.channels.models import Recording

    with transaction.atomic():
        recording = (
            Recording.objects.select_for_update()
            .select_related("channel")
            .filter(pk=recording_id)
            .first()
        )
        if not recording:
            return True
        if recording.channel_id != expected_channel_id:
            return False
        if recording.start_time != expected_start:
            return False
        if recording.start_time <= timezone.now():
            return False
        if not bool(getattr(recording.channel, "is_catchup", False)):
            return False
        if int(getattr(recording.channel, "catchup_days", 0) or 0) <= 0:
            return False
        cp = recording.custom_properties or {}
        if str(cp.get("status") or "").lower() in TERMINAL_OR_ACTIVE_STATUSES:
            return False
        recording.delete()

    try:
        from core.utils import send_websocket_update
        send_websocket_update(
            "updates", "update",
            {"success": True, "type": "recordings_refreshed"},
        )
    except Exception:
        pass
    return True


def run_handoff(settings: dict[str, Any], task_logger=None) -> dict[str, Any]:
    from django.utils import timezone
    from apps.channels.models import Recording

    log = task_logger or logger
    handoff_minutes = _coerce_int(settings.get("handoff_minutes"), 60, 1, 24 * 60)
    account_id = _coerce_int(settings.get("mustarrd_account_id"), 1, 1)
    dry_run = bool(settings.get("dry_run", False))
    now = timezone.now()
    window_end = now + timedelta(minutes=handoff_minutes)

    result = {
        "status": "ok",
        "dry_run": dry_run,
        "window_minutes": handoff_minutes,
        "considered": 0,
        "ignored_no_catchup": 0,
        "handed_off": 0,
        "already_verified": 0,
        "skipped": 0,
        "errors": 0,
        "details": [],
    }

    recordings = list(
        Recording.objects.select_related("channel")
        .filter(start_time__gt=now, start_time__lte=window_end)
        .order_by("start_time", "id")
    )
    if not recordings:
        return result

    client = MustarrdClient(
        settings.get("mustarrd_url") or DEFAULTS["mustarrd_url"],
        settings.get("mustarrd_username") or "",
        settings.get("mustarrd_password") or "",
    )

    try:
        client.login()
        catchup_channels = _fetch_catchup_channels(client, account_id)
        schedules = _fetch_schedules(client)
        epg_cache: dict[str, list[dict]] = {}

        for recording in recordings:
            result["considered"] += 1
            channel = recording.channel
            channel_id = str(recording.channel_id)
            cp = recording.custom_properties or {}
            status = str(cp.get("status") or "").lower()

            if status in TERMINAL_OR_ACTIVE_STATUSES:
                result["skipped"] += 1
                continue

            if not bool(getattr(channel, "is_catchup", False)) or int(
                getattr(channel, "catchup_days", 0) or 0
            ) <= 0:
                result["ignored_no_catchup"] += 1
                continue

            mustarrd_channel = catchup_channels.get(channel_id)
            if not mustarrd_channel:
                result["skipped"] += 1
                result["details"].append({
                    "recording_id": recording.id,
                    "channel": channel.name,
                    "status": "kept_in_dispatcharr",
                    "reason": "channel_not_catchup_in_mustarrd",
                })
                continue

            original_start, original_end, source_program = _program_window_from_recording(recording)
            match_mode = "manual"
            pre_padding = 0
            post_padding = 0

            if original_start and original_end:
                if channel_id not in epg_cache:
                    epg = client.get_json(
                        f"/api/accounts/{account_id}/channels/{channel_id}/epg",
                        params={"days_back": 1, "fresh": "true"},
                    )
                    epg_cache[channel_id] = epg if isinstance(epg, list) else []
                program, match_mode = _find_rich_epg_program(epg_cache[channel_id], recording)
                if not program:
                    result["skipped"] += 1
                    result["details"].append({
                        "recording_id": recording.id,
                        "channel": channel.name,
                        "title": source_program.get("title"),
                        "status": "kept_in_dispatcharr",
                        "reason": f"epg_match_failed:{match_mode}",
                    })
                    continue
                pre_padding, post_padding = _derive_padding(
                    recording, original_start, original_end
                )
            else:
                program = _synthetic_program(recording)

            expected_key = _program_key(account_id, channel_id, program)
            if expected_key is None:
                result["skipped"] += 1
                continue

            preview_payload = {
                "account_id": account_id,
                "channel_id": channel_id,
                "channel_name": mustarrd_channel.get("name") or channel.name,
                "program": program,
            }
            preview = client.post_json("/api/downloads/preview-filename", preview_payload)
            filename = str(preview.get("filename") or "").strip()
            if not filename:
                result["skipped"] += 1
                result["details"].append({
                    "recording_id": recording.id,
                    "status": "kept_in_dispatcharr",
                    "reason": "mustarrd_filename_preview_empty",
                })
                continue

            existing = next(
                (s for s in schedules if _schedule_key(s) == expected_key),
                None,
            )
            if existing:
                if not _schedule_is_verified(
                    existing, expected_key, pre_padding, post_padding, filename
                ):
                    result["skipped"] += 1
                    result["details"].append({
                        "recording_id": recording.id,
                        "mustarrd_schedule_id": existing.get("id"),
                        "status": "kept_in_dispatcharr",
                        "reason": "existing_mustarrd_schedule_mismatch",
                    })
                    continue
                verified_schedule = existing
                result["already_verified"] += 1
            elif dry_run:
                result["details"].append({
                    "recording_id": recording.id,
                    "channel": channel.name,
                    "title": program.get("title"),
                    "match": match_mode,
                    "status": "would_handoff",
                    "pre_padding": pre_padding,
                    "post_padding": post_padding,
                    "filename": filename,
                })
                continue
            else:
                schedule_payload = {
                    "account_id": account_id,
                    "channel_id": channel_id,
                    "channel_name": mustarrd_channel.get("name") or channel.name,
                    "program": program,
                    "custom_filename": filename,
                    "pre_padding_minutes": pre_padding,
                    "post_padding_minutes": post_padding,
                }
                client.post_json("/api/schedules", schedule_payload)

                schedules = _fetch_schedules(client)
                verified_schedule = next(
                    (s for s in schedules if _schedule_key(s) == expected_key),
                    None,
                )
                if not verified_schedule or not _schedule_is_verified(
                    verified_schedule, expected_key, pre_padding, post_padding, filename
                ):
                    result["skipped"] += 1
                    result["details"].append({
                        "recording_id": recording.id,
                        "status": "kept_in_dispatcharr",
                        "reason": "mustarrd_schedule_readback_failed",
                    })
                    continue

            if dry_run:
                continue

            deleted = _delete_dispatcharr_recording(
                recording.id,
                recording.start_time,
                recording.channel_id,
            )
            if not deleted:
                result["skipped"] += 1
                result["details"].append({
                    "recording_id": recording.id,
                    "mustarrd_schedule_id": verified_schedule.get("id"),
                    "status": "mustarrd_verified_dispatcharr_kept",
                    "reason": "dispatcharr_recording_changed_during_handoff",
                })
                continue

            result["handed_off"] += 1
            result["details"].append({
                "recording_id": recording.id,
                "mustarrd_schedule_id": verified_schedule.get("id"),
                "channel": channel.name,
                "title": program.get("title"),
                "match": match_mode,
                "status": "handed_off",
                "filename": filename,
                "pre_padding": pre_padding,
                "post_padding": post_padding,
            })
            log.info(
                "Mustarrd handoff: Dispatcharr recording %s -> Mustarrd schedule %s (%s / %s)",
                recording.id,
                verified_schedule.get("id"),
                channel.name,
                program.get("title"),
            )

    except Exception as exc:
        result["status"] = "error"
        result["errors"] += 1
        result["message"] = str(exc)
        log.exception("Mustarrd DVR handoff pass failed")
    finally:
        client.close()

    return result


class Plugin:
    name = "Mustarrd DVR Handoff"
    version = "0.1.0"
    description = (
        "Hands catch-up-capable Dispatcharr DVR recordings to Mustarrd shortly "
        "before airtime, with verification and native-DVR failover."
    )
    author = "matrix2669"

    SCHEDULE_TASK_NAME = "plugin-mustarrd-dvr-handoff"
    SCHEDULED_TASK_CELERY_NAME = "mustarrd_dvr_handoff.check"

    with open(__file__.replace("plugin.py", "plugin.json"), "r", encoding="utf-8") as _manifest_file:
        _manifest = json.load(_manifest_file)
    fields = _manifest.get("fields", [])
    actions = _manifest.get("actions", [])

    @staticmethod
    def _parse_cron(expression: str):
        parts = str(expression or "").strip().split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have exactly 5 fields")
        return tuple(parts)

    def _apply_schedule(self, settings: dict[str, Any], action_logger) -> dict[str, Any]:
        from django_celery_beat.models import PeriodicTask, CrontabSchedule

        cron_expr = str(settings.get("handoff_cron") or DEFAULTS["handoff_cron"]).strip()
        minute, hour, dom, month, dow = self._parse_cron(cron_expr)
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_month=dom,
            month_of_year=month,
            day_of_week=dow,
            timezone="UTC",
        )
        _, created = PeriodicTask.objects.update_or_create(
            name=self.SCHEDULE_TASK_NAME,
            defaults={
                "crontab": schedule,
                "task": self.SCHEDULED_TASK_CELERY_NAME,
                "queue": "dvr",
                "kwargs": "{}",
                "enabled": True,
                "one_off": False,
                "interval": None,
                "clocked": None,
                "solar": None,
            },
        )
        verb = "Created" if created else "Updated"
        action_logger.info("%s Mustarrd handoff cron: %s", verb, cron_expr)
        return {"status": "ok", "message": f"{verb} handoff cron '{cron_expr}'."}

    def run(self, action: str, params: dict, context: dict):
        settings = {**DEFAULTS, **(context.get("settings") or {})}
        action_logger = context.get("logger") or logger

        if action == "test_connection":
            client = MustarrdClient(
                settings.get("mustarrd_url"),
                settings.get("mustarrd_username"),
                settings.get("mustarrd_password"),
            )
            try:
                client.login()
                account_id = _coerce_int(settings.get("mustarrd_account_id"), 1, 1)
                channels = _fetch_catchup_channels(client, account_id)
                return {
                    "status": "ok",
                    "message": f"Connected to Mustarrd. Account {account_id} exposes {len(channels)} catch-up channels.",
                    "catchup_channels": len(channels),
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}
            finally:
                client.close()

        if action == "run_now":
            return run_handoff(settings, action_logger)

        if action == "apply_schedule":
            try:
                return self._apply_schedule(settings, action_logger)
            except Exception as exc:
                action_logger.exception("Failed to apply Mustarrd handoff cron")
                return {"status": "error", "message": str(exc)}

        if action == "schedule_status":
            try:
                from django_celery_beat.models import PeriodicTask
                task = PeriodicTask.objects.filter(name=self.SCHEDULE_TASK_NAME).first()
                if not task:
                    return {"status": "ok", "message": "No automatic handoff cron is registered."}
                cron = task.crontab
                expression = (
                    f"{cron.minute} {cron.hour} {cron.day_of_month} "
                    f"{cron.month_of_year} {cron.day_of_week}"
                    if cron else "none"
                )
                return {
                    "status": "ok",
                    "message": (
                        f"Cron: {expression}; enabled={task.enabled}; "
                        f"last_run={task.last_run_at or 'never'}; total_runs={task.total_run_count}"
                    ),
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        if action == "remove_schedule":
            try:
                from django_celery_beat.models import PeriodicTask
                deleted, _ = PeriodicTask.objects.filter(name=self.SCHEDULE_TASK_NAME).delete()
                return {
                    "status": "ok",
                    "message": "Handoff cron removed." if deleted else "No handoff cron was registered.",
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        return {"status": "error", "message": f"Unknown action: {action}"}


try:
    from celery import shared_task

    @shared_task(name=Plugin.SCHEDULED_TASK_CELERY_NAME)
    def mustarrd_dvr_handoff_check():
        return run_handoff(_load_settings(), logger)
except Exception as exc:  # pragma: no cover
    logger.warning("Mustarrd DVR Handoff Celery registration unavailable: %s", exc)
