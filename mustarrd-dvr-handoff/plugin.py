"""Dispatcharr -> Mustarrd DVR handoff plugin.

Normal operation:
  * Dispatcharr remains the source of DVR intent, EPG metadata, catch-up
    capability, and filename templates.
  * Catch-up recordings are mirrored into Mustarrd up to mirror_hours ahead
    (72 hours by default) while the native Dispatcharr recording remains intact.
  * Inside the final handoff window (60 minutes by default), the plugin confirms
    that Mustarrd currently sees the channel as catch-up capable and that the
    mirrored schedule still matches.
  * Only after that final verification is the Dispatcharr Recording deleted.
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

DEFAULT_TV_TEMPLATE = (
    "TV Shows/{show} {tmdb}/Season {season:02d}/"
    "{show} - S{season:02d}E{episode:02d} - {title}"
)
DEFAULT_MOVIE_TEMPLATE = "{title} ({year}) {tmdb}"
DEFAULT_SPORTS_TEMPLATE = "{title} - {date}"
DEFAULT_GENERIC_TEMPLATE = "{title} - {date}"

DEFAULTS = {
    "mustarrd_url": "http://mustarrd:4177",
    "mustarrd_username": "",
    "mustarrd_password": "",
    "mustarrd_account_id": 1,
    "mirror_hours": 72,
    "handoff_minutes": 60,
    "handoff_cron": "*/5 * * * *",
    "tv_template": DEFAULT_TV_TEMPLATE,
    "movie_template": DEFAULT_MOVIE_TEMPLATE,
    "sports_template": DEFAULT_SPORTS_TEMPLATE,
    "default_template": DEFAULT_GENERIC_TEMPLATE,
    "dry_run": False,
}

TERMINAL_OR_ACTIVE_STATUSES = {
    "recording",
    "completed",
    "stopped",
    "interrupted",
}

ACTIVE_MUSTARRD_STATUSES = {
    "scheduled",
    "paused_low_space",
    "queued",
    "downloading",
    "processing",
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
                    f"Mustarrd authentication failed ({response.status_code}): "
                    f"{_response_detail(response)}"
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
                f"Mustarrd GET {path} failed ({response.status_code}): "
                f"{_response_detail(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise MustarrdError(f"Mustarrd GET {path} returned invalid JSON") from exc

    def post_json(self, path: str, payload: dict):
        headers = {"X-CSRF-Token": self.csrf_token or ""}
        try:
            response = self.session.post(
                self._url(path),
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MustarrdError(f"Mustarrd POST {path} failed: {exc}") from exc
        if response.status_code >= 400:
            raise MustarrdError(
                f"Mustarrd POST {path} failed ({response.status_code}): "
                f"{_response_detail(response)}"
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


def _coerce_int(
    value,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
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
    return (
        _parse_iso(program.get("start_time")),
        _parse_iso(program.get("end_time")),
        program,
    )


def _derive_padding(
    recording,
    original_start: datetime,
    original_end: datetime,
) -> tuple[int, int]:
    rec_start = _aware_utc(recording.start_time)
    rec_end = _aware_utc(recording.end_time)
    pre_seconds = max(0.0, (original_start - rec_start).total_seconds())
    post_seconds = max(0.0, (rec_end - original_end).total_seconds())
    pre = max(0, min(120, int(round(pre_seconds / 60.0))))
    post = max(0, min(120, int(round(post_seconds / 60.0))))
    return pre, post


def _program_key(
    account_id: int,
    channel_id: str,
    program: dict,
) -> tuple[int, str, int, int] | None:
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


def _schedule_is_verified(
    schedule: dict,
    expected_key,
    pre: int,
    post: int,
    filename: str,
) -> bool:
    if _schedule_key(schedule) != expected_key:
        return False
    if str(schedule.get("status") or "").lower() not in ACTIVE_MUSTARRD_STATUSES:
        return False
    if int(schedule.get("pre_padding_minutes") or 0) != int(pre):
        return False
    if int(schedule.get("post_padding_minutes") or 0) != int(post):
        return False
    return _normalize_filename(schedule.get("custom_filename")) == _normalize_filename(filename)


def _sanitize_component(value: Any) -> str:
    text = str(value or "")
    text = re.sub(
        "[\u00ad\u200b\u200c\u200d\u200e\u200f"
        "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff]",
        "",
        text,
    )
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if text in {"", ".", ".."}:
        return "unknown-program"
    encoded = text.encode("utf-8")
    if len(encoded) > 200:
        text = encoded[:200].decode("utf-8", errors="ignore").rstrip() or "unknown-program"
    return text


def _render_template_path(template: str, context: dict[str, Any]) -> str:
    components = []
    for raw_component in str(template or "").split("/"):
        if not raw_component.strip():
            continue
        rendered = raw_component.format_map(context)
        rendered = re.sub(r"\s+[-–—:]\s*$", "", rendered).strip()
        components.append(_sanitize_component(rendered))
    return "/".join(components) or "unknown-program"


def _normalize_external_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"(\d+)", text)
    return match.group(1) if match else ""


def _tmdb_tag(value: Any) -> str:
    tmdb_id = _normalize_external_id(value)
    if not tmdb_id:
        return ""
    return f"{{tmdb-{tmdb_id}}} [tmdbid={tmdb_id}]"


def _category_values(cp: dict) -> list[str]:
    raw = cp.get("categories") or []
    if isinstance(raw, str):
        raw = [raw]
    values = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            value = item.get("value") or item.get("name") or item.get("category")
        else:
            value = item
        text = str(value or "").strip()
        if text:
            values.append(text)
    return values


def _detect_program_type(program: dict) -> str:
    season = program.get("season_number")
    episode = program.get("episode_number")
    if season is not None and episode is not None:
        return "tv_show"

    categories = " ".join(program.get("categories") or [program.get("category") or ""]).casefold()
    title = str(program.get("title") or "").casefold()
    description = str(program.get("description") or "").casefold()

    if any(token in categories for token in ("movie", "movies", "film", "films")):
        return "movie"

    sports_words = (
        "sports", "sport", "football", "baseball", "basketball", "hockey",
        "soccer", "boxing", "wrestling", "tennis", "golf", "racing",
        "motorsport", "cricket", "rugby",
    )
    if any(token in categories for token in sports_words):
        return "sports"
    if re.search(
        r"\b(?:nfl|nba|wnba|nhl|mlb|mls|ufc|mma|ncaa|fifa|uefa|nascar|pga|lpga)\b"
        r"|\bvs\.?\b|\bplayoffs?\b|\b(?:quarter|semi)-?finals?\b",
        f"{title} {description}",
        flags=re.IGNORECASE,
    ):
        return "sports"

    return "default"


def _extract_year(program: dict) -> int:
    for value in (
        program.get("production_date"),
        program.get("description"),
        program.get("title"),
    ):
        match = re.search(r"\b(19\d{2}|20\d{2})\b", str(value or ""))
        if match:
            return int(match.group(1))
    start = _parse_iso(program.get("start_time"))
    return start.year if start else datetime.utcnow().year


def _render_filename(program: dict, channel_name: str, settings: dict[str, Any]) -> str:
    start = _parse_iso(program.get("start_time")) or datetime.utcnow().replace(
        tzinfo=dt_timezone.utc
    )
    title = str(program.get("title") or "Unknown").strip()
    subtitle = str(program.get("subtitle") or "").strip()
    season = program.get("season_number")
    episode = program.get("episode_number")
    tmdb = _tmdb_tag(program.get("tmdb_id"))

    program_type = _detect_program_type(program)
    context = {
        "show": title,
        "season": int(season or 0),
        "episode": int(episode or 0),
        "title": subtitle if program_type == "tv_show" else title,
        "date": start.strftime("%Y-%m-%d"),
        "channel": channel_name,
        "year": _extract_year(program),
        "tmdb": tmdb,
        "tmdb_id": _normalize_external_id(program.get("tmdb_id")),
        "tvdb_id": _normalize_external_id(program.get("tvdb_id")),
        "imdb_id": str(program.get("imdb_id") or "").strip(),
    }

    if program_type == "tv_show":
        template = settings.get("tv_template") or DEFAULT_TV_TEMPLATE
    elif program_type == "movie":
        template = settings.get("movie_template") or DEFAULT_MOVIE_TEMPLATE
    elif program_type == "sports":
        template = settings.get("sports_template") or DEFAULT_SPORTS_TEMPLATE
    else:
        template = settings.get("default_template") or DEFAULT_GENERIC_TEMPLATE

    try:
        rendered = _render_template_path(template, context)
    except (KeyError, ValueError, AttributeError):
        rendered = _render_template_path(
            DEFAULT_GENERIC_TEMPLATE,
            {
                **context,
                "title": title,
            },
        )
    return rendered + ".ts"


def _program_to_payload(program_obj, recording) -> dict[str, Any]:
    cp = dict(program_obj.custom_properties or {})
    categories = _category_values(cp)
    season = cp.get("season")
    episode = cp.get("episode")
    start = _aware_utc(program_obj.start_time)
    end = _aware_utc(program_obj.end_time)
    tmdb_id = cp.get("themoviedb.org_id")
    tvdb_id = cp.get("thetvdb.com_id")
    imdb_id = cp.get("imdb.com_id")
    return {
        "id": program_obj.id,
        "epg_id": f"{recording.channel_id}_{_epoch(start)}_{_epoch(end)}",
        "title": program_obj.title,
        "subtitle": program_obj.sub_title or "",
        "description": program_obj.description or "",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "start_timestamp": _epoch(start),
        "stop_timestamp": _epoch(end),
        "provider_start": None,
        "provider_stop": None,
        "duration_minutes": max(1, int((end - start).total_seconds() // 60)),
        "has_archive": True,
        "channel_id": str(recording.channel_id),
        "category": categories[0] if categories else "",
        "categories": categories,
        "season_number": season,
        "episode_number": episode,
        "episode_onscreen": cp.get("onscreen_episode"),
        "tmdb_id": tmdb_id,
        "tvdb_id": tvdb_id,
        "imdb_id": imdb_id,
        "production_date": cp.get("date"),
        "is_new": bool(cp.get("new")),
        "is_live": bool(cp.get("live")),
        "is_premiere": bool(cp.get("premiere")),
    }


def _resolve_dispatcharr_program(recording) -> tuple[dict | None, str]:
    """Resolve the current EPG row from Dispatcharr's own ProgramData table."""
    from apps.epg.models import ProgramData

    original_start, original_end, source_program = _program_window_from_recording(recording)
    if not original_start or not original_end:
        return None, "manual"

    source_id = source_program.get("id")
    if source_id is not None:
        try:
            obj = ProgramData.objects.filter(pk=int(source_id)).first()
        except (TypeError, ValueError):
            obj = None
        if obj is not None:
            return _program_to_payload(obj, recording), "dispatcharr_id"

    epg_obj = getattr(recording.channel, "effective_epg_data_obj", None)
    if callable(epg_obj):
        epg_obj = epg_obj()
    if epg_obj is None:
        epg_obj = getattr(recording.channel, "epg_data", None)
    if epg_obj is None:
        return None, "channel_has_no_epg"

    exact = list(
        ProgramData.objects.filter(
            epg=epg_obj,
            start_time=original_start,
            end_time=original_end,
        )[:2]
    )
    if len(exact) == 1:
        return _program_to_payload(exact[0], recording), "dispatcharr_exact"
    if len(exact) > 1:
        return None, "ambiguous_exact"

    wanted_title = _normalize_text(source_program.get("title"))
    wanted_subtitle = _normalize_text(source_program.get("sub_title"))
    if not wanted_title:
        return None, "missing_title"

    lower = original_start - timedelta(minutes=30 if wanted_subtitle else 10)
    upper = original_start + timedelta(minutes=30 if wanted_subtitle else 10)
    candidates = list(
        ProgramData.objects.filter(
            epg=epg_obj,
            start_time__gte=lower,
            start_time__lte=upper,
        ).order_by("start_time")[:20]
    )
    matches = []
    for obj in candidates:
        if _normalize_text(obj.title) != wanted_title:
            continue
        if wanted_subtitle and _normalize_text(obj.sub_title) != wanted_subtitle:
            continue
        start_delta = abs((_aware_utc(obj.start_time) - original_start).total_seconds())
        stop_delta = abs((_aware_utc(obj.end_time) - original_end).total_seconds())
        limit = 30 * 60 if wanted_subtitle else 10 * 60
        if start_delta <= limit and stop_delta <= limit:
            matches.append((start_delta + stop_delta, obj))

    if len(matches) != 1:
        return None, "ambiguous_or_missing_shifted_match"
    return _program_to_payload(matches[0][1], recording), "dispatcharr_shifted"


def _synthetic_program(recording) -> dict:
    start = _aware_utc(recording.start_time)
    end = _aware_utc(recording.end_time)
    title = f"{recording.channel.name} Recording"
    return {
        "id": None,
        "epg_id": None,
        "title": title,
        "subtitle": "",
        "description": "Manual recording handed off from Dispatcharr",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "start_timestamp": _epoch(start),
        "stop_timestamp": _epoch(end),
        "provider_start": None,
        "provider_stop": None,
        "duration_minutes": max(
            1,
            int(math.ceil((end - start).total_seconds() / 60.0)),
        ),
        "has_archive": True,
        "channel_id": str(recording.channel_id),
        "category": "",
        "categories": [],
        "season_number": None,
        "episode_number": None,
        "tmdb_id": None,
        "tvdb_id": None,
        "imdb_id": None,
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


def _delete_dispatcharr_recording(
    recording_id: int,
    expected_start: datetime,
    expected_channel_id: int,
) -> bool:
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
            "updates",
            "update",
            {"success": True, "type": "recordings_refreshed"},
        )
    except Exception:
        pass
    return True


def run_handoff(settings: dict[str, Any], task_logger=None) -> dict[str, Any]:
    from django.utils import timezone
    from apps.channels.models import Recording

    log = task_logger or logger
    mirror_hours = _coerce_int(settings.get("mirror_hours"), 72, 1, 24 * 14)
    handoff_minutes = _coerce_int(
        settings.get("handoff_minutes"),
        60,
        1,
        min(mirror_hours * 60, 24 * 60),
    )
    account_id = _coerce_int(settings.get("mustarrd_account_id"), 1, 1)
    dry_run = bool(settings.get("dry_run", False))
    now = timezone.now()
    mirror_end = now + timedelta(hours=mirror_hours)
    final_end = now + timedelta(minutes=handoff_minutes)

    result = {
        "status": "ok",
        "dry_run": dry_run,
        "mirror_hours": mirror_hours,
        "handoff_minutes": handoff_minutes,
        "considered": 0,
        "ignored_no_catchup": 0,
        "mirrored": 0,
        "already_mirrored": 0,
        "handed_off": 0,
        "skipped": 0,
        "errors": 0,
        "details": [],
    }

    recordings = list(
        Recording.objects.select_related("channel", "channel__epg_data")
        .filter(start_time__gt=now, start_time__lte=mirror_end)
        .order_by("start_time", "id")
    )
    if not recordings:
        return result

    eligible = []
    for recording in recordings:
        channel = recording.channel
        cp = recording.custom_properties or {}
        status = str(cp.get("status") or "").lower()
        if status in TERMINAL_OR_ACTIVE_STATUSES:
            continue
        if not bool(getattr(channel, "is_catchup", False)) or int(
            getattr(channel, "catchup_days", 0) or 0
        ) <= 0:
            result["ignored_no_catchup"] += 1
            continue
        eligible.append(recording)

    if not eligible:
        return result

    client = MustarrdClient(
        settings.get("mustarrd_url") or DEFAULTS["mustarrd_url"],
        settings.get("mustarrd_username") or "",
        settings.get("mustarrd_password") or "",
    )

    try:
        client.login()
        schedules = _fetch_schedules(client)
        final_catchup_channels: dict[str, dict] | None = None
        final_channel_error: str | None = None

        for recording in eligible:
            result["considered"] += 1
            channel = recording.channel
            channel_id = str(recording.channel_id)
            original_start, original_end, source_program = _program_window_from_recording(
                recording
            )

            if original_start and original_end:
                program, match_mode = _resolve_dispatcharr_program(recording)
                if not program:
                    result["skipped"] += 1
                    result["details"].append(
                        {
                            "recording_id": recording.id,
                            "channel": channel.name,
                            "title": source_program.get("title"),
                            "status": "kept_in_dispatcharr",
                            "reason": f"dispatcharr_epg_match_failed:{match_mode}",
                        }
                    )
                    continue
                pre_padding, post_padding = _derive_padding(
                    recording,
                    original_start,
                    original_end,
                )
            else:
                program = _synthetic_program(recording)
                match_mode = "manual"
                pre_padding = 0
                post_padding = 0

            expected_key = _program_key(account_id, channel_id, program)
            if expected_key is None:
                result["skipped"] += 1
                continue

            filename = _render_filename(program, channel.name, settings)
            existing = next(
                (
                    s
                    for s in schedules
                    if _schedule_key(s) == expected_key
                    and str(s.get("status") or "").lower() in ACTIVE_MUSTARRD_STATUSES
                ),
                None,
            )

            verified_schedule = None
            if existing:
                if _schedule_is_verified(
                    existing,
                    expected_key,
                    pre_padding,
                    post_padding,
                    filename,
                ):
                    verified_schedule = existing
                    result["already_mirrored"] += 1
                else:
                    result["skipped"] += 1
                    result["details"].append(
                        {
                            "recording_id": recording.id,
                            "mustarrd_schedule_id": existing.get("id"),
                            "status": "kept_in_dispatcharr",
                            "reason": "existing_mustarrd_schedule_mismatch",
                            "expected_filename": filename,
                        }
                    )
                    continue
            elif dry_run:
                result["details"].append(
                    {
                        "recording_id": recording.id,
                        "channel": channel.name,
                        "title": program.get("title"),
                        "match": match_mode,
                        "status": "would_mirror",
                        "filename": filename,
                        "pre_padding": pre_padding,
                        "post_padding": post_padding,
                    }
                )
            else:
                schedule_payload = {
                    "account_id": account_id,
                    "channel_id": channel_id,
                    "channel_name": channel.name,
                    "program": program,
                    "custom_filename": filename,
                    "pre_padding_minutes": pre_padding,
                    "post_padding_minutes": post_padding,
                }
                client.post_json("/api/schedules", schedule_payload)
                schedules = _fetch_schedules(client)
                verified_schedule = next(
                    (
                        s
                        for s in schedules
                        if _schedule_is_verified(
                            s,
                            expected_key,
                            pre_padding,
                            post_padding,
                            filename,
                        )
                    ),
                    None,
                )
                if not verified_schedule:
                    result["skipped"] += 1
                    result["details"].append(
                        {
                            "recording_id": recording.id,
                            "status": "kept_in_dispatcharr",
                            "reason": "mustarrd_schedule_readback_failed",
                        }
                    )
                    continue
                result["mirrored"] += 1
                result["details"].append(
                    {
                        "recording_id": recording.id,
                        "mustarrd_schedule_id": verified_schedule.get("id"),
                        "channel": channel.name,
                        "title": program.get("title"),
                        "match": match_mode,
                        "status": "mirrored",
                        "filename": filename,
                    }
                )

            inside_final_window = recording.start_time <= final_end
            if not inside_final_window:
                continue

            if dry_run and verified_schedule is None:
                continue

            if final_catchup_channels is None and final_channel_error is None:
                try:
                    final_catchup_channels = _fetch_catchup_channels(client, account_id)
                except Exception as exc:
                    final_channel_error = str(exc)
                    log.warning(
                        "Mustarrd final catch-up channel check failed; "
                        "Dispatcharr recordings will be kept: %s",
                        exc,
                    )

            if final_channel_error:
                result["skipped"] += 1
                result["details"].append(
                    {
                        "recording_id": recording.id,
                        "status": "kept_in_dispatcharr",
                        "reason": "mustarrd_final_channel_check_failed",
                    }
                )
                continue

            if not final_catchup_channels or channel_id not in final_catchup_channels:
                result["skipped"] += 1
                result["details"].append(
                    {
                        "recording_id": recording.id,
                        "channel": channel.name,
                        "status": "kept_in_dispatcharr",
                        "reason": "channel_not_catchup_in_mustarrd_at_final_check",
                    }
                )
                continue

            schedules = _fetch_schedules(client)
            verified_schedule = next(
                (
                    s
                    for s in schedules
                    if _schedule_is_verified(
                        s,
                        expected_key,
                        pre_padding,
                        post_padding,
                        filename,
                    )
                ),
                None,
            )
            if not verified_schedule:
                result["skipped"] += 1
                result["details"].append(
                    {
                        "recording_id": recording.id,
                        "status": "kept_in_dispatcharr",
                        "reason": "mustarrd_final_schedule_verification_failed",
                    }
                )
                continue

            if dry_run:
                result["details"].append(
                    {
                        "recording_id": recording.id,
                        "mustarrd_schedule_id": verified_schedule.get("id"),
                        "status": "would_handoff",
                    }
                )
                continue

            deleted = _delete_dispatcharr_recording(
                recording.id,
                recording.start_time,
                recording.channel_id,
            )
            if not deleted:
                result["skipped"] += 1
                result["details"].append(
                    {
                        "recording_id": recording.id,
                        "mustarrd_schedule_id": verified_schedule.get("id"),
                        "status": "mustarrd_verified_dispatcharr_kept",
                        "reason": "dispatcharr_recording_changed_during_handoff",
                    }
                )
                continue

            result["handed_off"] += 1
            result["details"].append(
                {
                    "recording_id": recording.id,
                    "mustarrd_schedule_id": verified_schedule.get("id"),
                    "channel": channel.name,
                    "title": program.get("title"),
                    "match": match_mode,
                    "status": "handed_off",
                    "filename": filename,
                    "pre_padding": pre_padding,
                    "post_padding": post_padding,
                }
            )
            log.info(
                "Mustarrd handoff: Dispatcharr recording %s -> Mustarrd schedule %s "
                "(%s / %s)",
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
    version = "0.2.0"
    description = (
        "Mirrors catch-up-capable Dispatcharr DVR recordings to Mustarrd up to "
        "72 hours ahead and performs a final verified handoff shortly before airtime."
    )
    author = "matrix2669"

    SCHEDULE_TASK_NAME = "plugin-mustarrd-dvr-handoff"
    SCHEDULED_TASK_CELERY_NAME = "mustarrd_dvr_handoff.check"

    with open(
        __file__.replace("plugin.py", "plugin.json"),
        "r",
        encoding="utf-8",
    ) as _manifest_file:
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
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        cron_expr = str(
            settings.get("handoff_cron") or DEFAULTS["handoff_cron"]
        ).strip()
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
        return {
            "status": "ok",
            "message": f"{verb} handoff cron '{cron_expr}'.",
        }

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
                schedules = _fetch_schedules(client)
                return {
                    "status": "ok",
                    "message": (
                        "Connected to Mustarrd. "
                        f"Visible schedules: {len(schedules)}."
                    ),
                    "schedules": len(schedules),
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

                task = PeriodicTask.objects.filter(
                    name=self.SCHEDULE_TASK_NAME
                ).first()
                if not task:
                    return {
                        "status": "ok",
                        "message": "No automatic handoff cron is registered.",
                    }
                cron = task.crontab
                expression = (
                    f"{cron.minute} {cron.hour} {cron.day_of_month} "
                    f"{cron.month_of_year} {cron.day_of_week}"
                    if cron
                    else "none"
                )
                return {
                    "status": "ok",
                    "message": (
                        f"Cron: {expression}; enabled={task.enabled}; "
                        f"last_run={task.last_run_at or 'never'}; "
                        f"total_runs={task.total_run_count}"
                    ),
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        if action == "remove_schedule":
            try:
                from django_celery_beat.models import PeriodicTask

                deleted, _ = PeriodicTask.objects.filter(
                    name=self.SCHEDULE_TASK_NAME
                ).delete()
                return {
                    "status": "ok",
                    "message": (
                        "Handoff cron removed."
                        if deleted
                        else "No handoff cron was registered."
                    ),
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
