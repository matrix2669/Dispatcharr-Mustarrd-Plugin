"""Annual-season normalization for Dispatcharr EPG programmes.

XMLTV ``xmltv_ns`` season numbers are zero-based. Some providers use ``-1``
when the season is unknown but still supply a useful episode number. Dispatcharr
normalizes that value to season ``0`` and episode ``N+1``. Media servers then
interpret those ordinary episodes as specials.

Dispatcharr also preserves an explicit onscreen episode marker separately. That
lets the handoff distinguish a provider's unknown season from a genuine onscreen
``S00`` special. When both are present, raw XMLTV season ``-1`` is authoritative;
otherwise an onscreen ``S00`` remains a genuine special.
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


def _has_unknown_xmltv_season(program: dict[str, Any]) -> bool:
    xmltv_ns = str(program.get("episode_xmltv_ns") or "").strip()
    if not xmltv_ns:
        return False
    season_component = xmltv_ns.split(".", 1)[0].strip()
    return _coerce_optional_int(season_component) == -1


def needs_raw_xmltv_lookup(program: dict[str, Any]) -> bool:
    """Return whether Dispatcharr discarded data needed to classify an S00."""
    season = _coerce_optional_int(program.get("season_number"))
    episode = _coerce_optional_int(program.get("episode_number"))
    return bool(
        season == 0
        and episode is not None
        and episode > 0
        and _has_explicit_special_season(program)
        and not str(program.get("episode_xmltv_ns") or "").strip()
    )


def enrich_from_mustarrd_epg(
    program: dict[str, Any],
    epg_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Restore raw episode metadata from the matching Mustarrd EPG entry."""
    program_id = str(program.get("id") or "").strip()
    start_timestamp = _coerce_optional_int(program.get("start_timestamp"))
    stop_timestamp = _coerce_optional_int(program.get("stop_timestamp"))

    match = None
    if program_id:
        match = next(
            (
                entry
                for entry in epg_entries
                if str(entry.get("id") or "").strip() == program_id
            ),
            None,
        )
    if match is None and start_timestamp and stop_timestamp:
        match = next(
            (
                entry
                for entry in epg_entries
                if _coerce_optional_int(entry.get("start_timestamp")) == start_timestamp
                and _coerce_optional_int(entry.get("stop_timestamp")) == stop_timestamp
            ),
            None,
        )
    if match is None:
        return program

    raw_xmltv = str(match.get("episode_xmltv_ns") or "").strip()
    if not raw_xmltv:
        return program

    updated = dict(program)
    updated["episode_xmltv_ns"] = raw_xmltv
    if match.get("episode_onscreen"):
        updated["episode_onscreen"] = match["episode_onscreen"]
    return updated


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
    ``episode_onscreen=S00...``. A raw XMLTV season of ``-1`` overrides that
    onscreen value because the provider is explicitly marking the season as
    unknown. The input dict is never mutated.
    """
    season = _coerce_optional_int(program.get("season_number"))
    episode = _coerce_optional_int(program.get("episode_number"))
    if season != 0 or episode is None or episode <= 0:
        return program
    if (
        _has_explicit_special_season(program)
        and not _has_unknown_xmltv_season(program)
    ):
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
