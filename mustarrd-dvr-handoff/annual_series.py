"""Annual-season normalization for Dispatcharr EPG programmes.

XMLTV ``xmltv_ns`` season numbers are zero-based. Some providers use ``-1``
when the season is unknown but still supply a useful episode number. Dispatcharr
normalizes that value to season ``0`` and episode ``N+1``. Media servers then
interpret those ordinary episodes as specials.

Dispatcharr also preserves an explicit onscreen episode marker separately. That
lets the handoff distinguish a provider's unknown season from a genuine onscreen
``S00`` special without relying on categories or external IDs, which are often
missing on daily sports-talk programmes.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
import re
from typing import Any


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


def _has_explicit_special_season(program: dict[str, Any]) -> bool:
    onscreen = str(program.get("episode_onscreen") or "").strip()
    return bool(onscreen and _EXPLICIT_SPECIAL_RE.search(onscreen))


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
    """Return a copy with Dispatcharr's unknown season 0 replaced by airing year.

    Dispatcharr's XMLTV parser maps a provider ``xmltv_ns`` season of ``-1`` to
    season 0. A genuine onscreen season-zero episode is retained separately as
    ``episode_onscreen=S00...`` and is never rewritten. The input dict is never
    mutated.
    """
    season = _coerce_optional_int(program.get("season_number"))
    episode = _coerce_optional_int(program.get("episode_number"))
    if season != 0 or episode is None or episode <= 0:
        return program
    if _has_explicit_special_season(program):
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
