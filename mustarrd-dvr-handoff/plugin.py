"""Dispatcharr entry point for Mustarrd DVR Handoff.

The implementation lives in core.py. Keeping this entry point small lets
Dispatcharr's plugin.json remain the single source of truth for UI fields and
actions while preserving the stable Celery task implementation.
"""

from . import core as _core
from .annual_series import install_core_hooks

# v0.2.7 defaults. Filename templates intentionally omit the extension;
# Mustarrd appends .ts when scheduling a custom filename that has no .ts suffix.
_core.DEFAULT_TV_TEMPLATE = (
    "TV Shows/{show} {tmdb}/Season {season:02d}/"
    "{show} - S{season:02d}E{episode:02d} - {title}"
)
_core.DEFAULT_MOVIE_TEMPLATE = "Movies/{title} ({year}) {tmdb}/{title} ({year})"
_core.DEFAULT_SPORTS_TEMPLATE = "Sports/{title} - {date}"
_core.DEFAULT_GENERIC_TEMPLATE = "Other/{title} - {date}"

_core.DEFAULTS.update(
    {
        "tv_template": _core.DEFAULT_TV_TEMPLATE,
        "movie_template": _core.DEFAULT_MOVIE_TEMPLATE,
        "sports_template": _core.DEFAULT_SPORTS_TEMPLATE,
        "default_template": _core.DEFAULT_GENERIC_TEMPLATE,
    }
)

# Dispatcharr parses provider xmltv_ns season -1 as season 0. Install the
# filename/schedule normalization hook so recurring series use their airing year
# instead of being handed to Plex/Jellyfin as specials. Explicit onscreen S00
# episodes are intentionally preserved.
install_core_hooks(_core)

# Dispatcharr parses plugin.json during discovery. Leaving these empty makes the
# manifest the single source of truth for the settings/action UI.
_core.Plugin.version = "0.2.7"
_core.Plugin.fields = []
_core.Plugin.actions = []

Plugin = _core.Plugin

# Importing core registers the stable Celery shared task. Re-export it for
# tooling/introspection without registering a second task.
mustarrd_dvr_handoff_check = getattr(_core, "mustarrd_dvr_handoff_check", None)
