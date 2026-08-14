"""Annual-season normalization for recurring Dispatcharr EPG series.

Some XMLTV providers use an invalid/unknown season of ``-1`` while keeping a
useful zero-based episode number. Dispatcharr normalizes that to season ``0``
and episode ``N+1``. Media servers then interpret those ordinary episodes as
specials.

For clearly identified series, treat that season-zero-without-an-explicit-S00
case as an annual season and use the airing year. Explicit onscreen ``S00``
values remain specials.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
import re
from typing import Any


_SERIES_CATEGORIES = {
    "series",
    "tv series",
    "tv-series",
    "television series",
}
_SPORTS_CATEGORIES = {"sports", "sport", "deportes", "esports"}
_EXPLICIT_SPECIAL_RE = re.compile(
    r"(?:^|\b)S(?:eason)?\s*0+(?=\D|$)",
    re.IGNORECASE,
)


def _coerce_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _category_keys(program: dict[str, Any]) -> set[str]:
    raw = program.get("categories") or []
    if isinstance(raw, str):
        raw = [raw]
    elif not isinstance(raw, (list, tuple, set)):
        raw = []

    values = list(raw)
    if program.get("category"):
        values.append(program.get("category"))

    return {
        str(value).strip().casefold()
        for value in values
        if str(value or "").strip()
    }


def _has_explicit_special_season(program: dict[str, Any]) -> bool:
    onscreen = str(program.get("episode_onscreen") or "").strip()
    return bool(onscreen and _EXPLICIT_SPECIAL_RE.search(onscreen))


def _has_series_identity(program: dict[str, Any]) -> bool:
    categories = _category_keys(program)
    if categories & _SERIES_CATEGORIES:
        return True

    # Sports feeds sometimes attach series IDs to leagues/events. If the guide
    # gives us only Sports-style category evidence, do not infer a yearly season
    # from external IDs alone.
    if categories & _SPORTS_CATEGORIES:
        return False

    for key in ("tvdb_id", "tmdb_id"):
        value = str(program.get(key) or "").strip().casefold()
        if value.startswith("series/"):
            return True

    dd_progid = str(program.get("dd_progid") or "").strip().upper()
    return dd_progid.startswith("EP")


def _airing_year(program: dict[str, Any]) -> int | None:
    start_time = program.get("start_time")
    if start_time:
        try:
            text = str(start_time).strip().replace("Z", "+00:00")
            year = datetime.fromisoformat(text).year
            if 1900 <= year <= 2099:
                return year
        except (TypeError, ValueError):
            pass

    timestamp = _coerce_optional_int(program.get("start_timestamp"))
    if timestamp:
        if timestamp > 10_000_000_000:
            timestamp //= 1000
        try:
            year = datetime.fromtimestamp(timestamp, tz=dt_timezone.utc).year
            if 1900 <= year <= 2099:
                return year
        except (OverflowError, OSError, ValueError):
            pass

    return None


def normalize_annual_series_season(program: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with season 0 replaced by airing year when appropriate.

    Dispatcharr stores a provider ``xmltv_ns`` season of ``-1`` as season 0.
    A genuine explicit special retains ``episode_onscreen=S00...`` and is never
    rewritten. The input dict is never mutated.
    """
    season = _coerce_optional_int(program.get("season_number"))
    episode = _coerce_optional_int(program.get("episode_number"))
    if season != 0 or episode is None or episode <= 0:
        return program
    if _has_explicit_special_season(program):
        return program
    if not _has_series_identity(program):
        return program

    year = _airing_year(program)
    if year is None:
        return program

    updated = dict(program)
    updated["season_number"] = year
    return updated


def install_core_hooks(core_module) -> None:
    """Apply the annual-season policy to the DVR handoff core exactly once."""
    sentinel = "_annual_series_season_policy_installed"
    if getattr(core_module, sentinel, False):
        return

    original_program_to_payload = core_module._program_to_payload
    original_render_filename = core_module._render_filename

    def program_to_payload_with_annual_season(program_obj, recording):
        return normalize_annual_series_season(
            original_program_to_payload(program_obj, recording)
        )

    def render_filename_with_annual_season(program, channel_name, settings):
        return original_render_filename(
            normalize_annual_series_season(program),
            channel_name,
            settings,
        )

    core_module._program_to_payload = program_to_payload_with_annual_season
    core_module._render_filename = render_filename_with_annual_season
    setattr(core_module, sentinel, True)
