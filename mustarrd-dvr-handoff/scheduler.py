"""Plugin-owned scheduler for Mustarrd DVR Handoff.

Dispatcharr 0.29 loads plugin Celery tasks after the default prefork consumer has
already built its task strategy map. Beat-delivered plugin tasks can therefore
be rejected as unregistered. This module keeps scheduling inside enabled uWSGI
plugin instances and uses Redis ``SET NX`` semantics (via Django's cache.add)
to ensure only one worker executes a matching cron minute.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone as dt_timezone
from typing import Any

STATE_FILENAME = ".mustarrd-dvr-handoff-scheduler.json"
STATUS_CACHE_KEY = "mustarrd-dvr-handoff:scheduler:status"
LOCK_CACHE_PREFIX = "mustarrd-dvr-handoff:scheduler:minute"
LOCK_TTL_SECONDS = 10 * 60
STATUS_TTL_SECONDS = 7 * 24 * 60 * 60
POLL_SECONDS = 15


def _process_role() -> str:
    """Return Dispatcharr's process role without making it a hard dependency."""
    try:
        from dispatcharr.db.process_label import get_process_role

        return str(get_process_role())
    except Exception:
        return "unknown"


def _is_scheduler_process() -> bool:
    # Enabled plugins are also imported in Daphne and Celery processes. Only
    # uWSGI request workers own scheduler loops; Redis deduplicates those workers.
    return _process_role() == "uwsgi"


def _state_path() -> str:
    override = os.environ.get("MUSTARRD_DVR_SCHEDULER_STATE", "").strip()
    if override:
        return override
    try:
        from apps.plugins.loader import PluginManager

        return os.path.join(PluginManager.get().plugins_dir, STATE_FILENAME)
    except Exception:
        return os.path.join("/data/plugins", STATE_FILENAME)


def _read_state() -> dict[str, Any]:
    path = _state_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Scheduler state file must contain a JSON object")
    return payload


def _write_state(*, enabled: bool, cron_expr: str) -> dict[str, Any]:
    path = _state_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {
        "version": 1,
        "enabled": bool(enabled),
        "cron": str(cron_expr).strip(),
        "updated_at": datetime.now(dt_timezone.utc).isoformat(),
    }
    temp_path = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except OSError:
            pass
    return payload


def _parse_cron(expression: str):
    parts = str(expression or "").strip().split()
    if len(parts) != 5:
        raise ValueError("Cron expression must have exactly 5 fields")

    minute, hour, dom, month, dow = parts
    from celery.schedules import crontab

    # Celery remains a Dispatcharr dependency. We only use its parser here so
    # existing cron syntax stays compatible; no Celery task is registered/sent.
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=dom,
        month_of_year=month,
        day_of_week=dow,
    )


def cron_matches(expression: str, when: datetime) -> bool:
    """Return whether *when* matches the 5-field Celery cron expression."""
    schedule = _parse_cron(expression)
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt_timezone.utc)
    when = when.astimezone(dt_timezone.utc)
    # Celery cron uses Sunday=0; datetime.isoweekday() uses Monday=1..Sunday=7.
    day_of_week = when.isoweekday() % 7
    return (
        when.minute in schedule.minute
        and when.hour in schedule.hour
        and when.day in schedule.day_of_month
        and when.month in schedule.month_of_year
        and day_of_week in schedule.day_of_week
    )


def _cron_from_legacy_task(task) -> str | None:
    cron = getattr(task, "crontab", None)
    if not cron:
        return None
    return (
        f"{cron.minute} {cron.hour} {cron.day_of_month} "
        f"{cron.month_of_year} {cron.day_of_week}"
    )


def _legacy_task(core):
    from django_celery_beat.models import PeriodicTask

    return PeriodicTask.objects.filter(name=core.Plugin.SCHEDULE_TASK_NAME).first()


def _delete_legacy_task(core) -> int:
    from django_celery_beat.models import PeriodicTask

    deleted, _ = PeriodicTask.objects.filter(
        name=core.Plugin.SCHEDULE_TASK_NAME
    ).delete()
    return int(deleted or 0)


def _migrate_legacy_schedule(core, action_logger) -> bool:
    """Convert the old Beat row to scheduler state, then remove the Beat row."""
    task = _legacy_task(core)
    if not task:
        return False

    state = _read_state()
    if not state:
        cron_expr = _cron_from_legacy_task(task) or core.DEFAULTS["handoff_cron"]
        _parse_cron(cron_expr)
        state = _write_state(enabled=bool(task.enabled), cron_expr=cron_expr)

    task.delete()
    action_logger.info(
        "Migrated legacy Celery Beat handoff schedule to plugin scheduler: "
        "enabled=%s cron=%s",
        bool(state.get("enabled", False)),
        state.get("cron") or core.DEFAULTS["handoff_cron"],
    )
    return True


def _read_status_cache() -> dict[str, Any]:
    try:
        from django.core.cache import cache

        value = cache.get(STATUS_CACHE_KEY)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_status_cache(payload: dict[str, Any]):
    try:
        from django.core.cache import cache

        cache.set(STATUS_CACHE_KEY, payload, timeout=STATUS_TTL_SECONDS)
    except Exception:
        pass


def _claim_minute(when: datetime) -> bool:
    from django.core.cache import cache

    minute = when.astimezone(dt_timezone.utc).strftime("%Y%m%d%H%M")
    key = f"{LOCK_CACHE_PREFIX}:{minute}"
    owner = f"{os.getpid()}:{threading.current_thread().name}"
    # django-redis implements cache.add with Redis SET NX semantics.
    return bool(cache.add(key, owner, timeout=LOCK_TTL_SECONDS))


def _scheduled_status(result: dict[str, Any], when: datetime) -> dict[str, Any]:
    return {
        "last_run": when.astimezone(dt_timezone.utc).isoformat(),
        "status": str(result.get("status") or "ok"),
        "worker_pid": os.getpid(),
        "considered": int(result.get("considered") or 0),
        "mirrored": int(result.get("mirrored") or 0),
        "already_mirrored": int(result.get("already_mirrored") or 0),
        "handed_off": int(result.get("handed_off") or 0),
        "skipped": int(result.get("skipped") or 0),
        "errors": int(result.get("errors") or 0),
    }


class _Scheduler:
    def __init__(self, core, plugin):
        self.core = core
        self.plugin = plugin
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self):
        if not _is_scheduler_process() or self.thread is not None:
            return
        self.thread = threading.Thread(
            target=self._loop,
            name="mustarrd-dvr-handoff-scheduler",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        thread = self.thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)

    def _loop(self):
        from django.db import close_old_connections

        log = self.core.logger
        while not self.stop_event.is_set():
            try:
                close_old_connections()
                _migrate_legacy_schedule(self.core, log)

                cfg = None
                from apps.plugins.models import PluginConfig

                for key in ("mustarrd-dvr-handoff", "mustarrd_dvr_handoff"):
                    try:
                        cfg = PluginConfig.objects.get(key=key)
                        break
                    except PluginConfig.DoesNotExist:
                        continue
                if cfg is None or not bool(cfg.enabled):
                    return

                state = _read_state()
                if bool(state.get("enabled", False)):
                    expression = str(
                        state.get("cron") or self.core.DEFAULTS["handoff_cron"]
                    ).strip()
                    now = datetime.now(dt_timezone.utc).replace(second=0, microsecond=0)
                    if cron_matches(expression, now) and _claim_minute(now):
                        settings = {**self.core.DEFAULTS, **dict(cfg.settings or {})}
                        _write_status_cache(
                            {
                                "last_run": now.isoformat(),
                                "status": "running",
                                "worker_pid": os.getpid(),
                            }
                        )
                        result = self.core.run_handoff(settings, log)
                        _write_status_cache(_scheduled_status(result, now))
            except Exception as exc:
                log.exception("Plugin scheduler check failed: %s", exc)
                _write_status_cache(
                    {
                        "last_run": datetime.now(dt_timezone.utc).isoformat(),
                        "status": "error",
                        "worker_pid": os.getpid(),
                        "message": str(exc),
                    }
                )
            finally:
                close_old_connections()

            self.stop_event.wait(POLL_SECONDS)


def _apply_schedule(core, settings: dict[str, Any], action_logger):
    cron_expr = str(settings.get("handoff_cron") or core.DEFAULTS["handoff_cron"]).strip()
    _parse_cron(cron_expr)
    _write_state(enabled=True, cron_expr=cron_expr)
    _delete_legacy_task(core)
    action_logger.info("Enabled plugin-owned handoff cron schedule: %s", cron_expr)
    return {
        "status": "ok",
        "message": f"Enabled plugin scheduler with cron '{cron_expr}'.",
    }


def _remove_schedule(core, action_logger):
    state = _read_state()
    cron_expr = str(state.get("cron") or core.DEFAULTS["handoff_cron"]).strip()
    _write_state(enabled=False, cron_expr=cron_expr)
    _delete_legacy_task(core)
    action_logger.info("Disabled plugin-owned handoff cron schedule")
    return {
        "status": "ok",
        "message": "Automatic handoff schedule disabled.",
    }


def _schedule_status(core):
    state = _read_state()
    enabled = bool(state.get("enabled", False))
    cron_expr = str(state.get("cron") or core.DEFAULTS["handoff_cron"]).strip()
    cached = _read_status_cache()
    last_run = cached.get("last_run") or "never"
    last_status = cached.get("status") or "never"
    summary = ""
    if cached:
        summary = (
            f"; considered={cached.get('considered', 0)}"
            f"; mirrored={cached.get('mirrored', 0)}"
            f"; already_mirrored={cached.get('already_mirrored', 0)}"
            f"; handed_off={cached.get('handed_off', 0)}"
            f"; skipped={cached.get('skipped', 0)}"
            f"; errors={cached.get('errors', 0)}"
        )
    return {
        "status": "ok",
        "message": (
            f"Cron: {cron_expr}; enabled={enabled}; scheduler=plugin; "
            f"last_run={last_run}; last_status={last_status}{summary}"
        ),
    }


def install_scheduler_hooks(core):
    """Replace only the old Beat scheduling surface; handoff logic is untouched."""
    if getattr(core.Plugin, "_mustarrd_scheduler_hooks_installed", False):
        return

    original_init = getattr(core.Plugin, "__init__", None)
    original_run = core.Plugin.run
    original_stop = getattr(core.Plugin, "stop", None)

    def __init__(self):
        if callable(original_init):
            original_init(self)
        self._mustarrd_scheduler = _Scheduler(core, self)
        self._mustarrd_scheduler.start()

    def run(self, action: str, params: dict, context: dict):
        settings = {**core.DEFAULTS, **(context.get("settings") or {})}
        action_logger = core._plugin_logger(context.get("logger"))

        if action == "apply_schedule":
            try:
                return _apply_schedule(core, settings, action_logger)
            except Exception as exc:
                action_logger.exception("Failed to apply Mustarrd plugin scheduler")
                return {"status": "error", "message": str(exc)}

        if action == "schedule_status":
            try:
                _migrate_legacy_schedule(core, action_logger)
                return _schedule_status(core)
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        if action == "remove_schedule":
            try:
                return _remove_schedule(core, action_logger)
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

        return original_run(self, action, params, context)

    def stop(self, context=None):
        scheduler = getattr(self, "_mustarrd_scheduler", None)
        if scheduler is not None:
            scheduler.stop()
        if callable(original_stop):
            try:
                return original_stop(self, context)
            except TypeError:
                return original_stop(self)
        return None

    core.Plugin.__init__ = __init__
    core.Plugin.run = run
    core.Plugin.stop = stop
    core.Plugin._mustarrd_scheduler_hooks_installed = True
