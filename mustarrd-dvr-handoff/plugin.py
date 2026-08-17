"""Dispatcharr entry point for Mustarrd DVR Handoff.

The handoff implementation lives in core.py. The plugin-owned scheduler lives
in scheduler.py so automatic checks do not depend on Dispatcharr registering a
plugin-defined Celery task in the default prefork worker.
"""

from . import core as _core
from .annual_series import install_core_hooks
from .scheduler import install_scheduler_hooks

# v0.2.12 defaults. Filename templates intentionally omit the extension;
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
# filename/schedule normalization hook so those episodes use their airing year
# instead of being handed to Plex/Jellyfin as specials. Explicit onscreen S00
# episodes are intentionally preserved.
install_core_hooks(_core)

# Replace the old Beat scheduling surface with a plugin-owned scheduler. The
# existing shared task in core.py remains inert for compatibility; v0.2.12
# removes the legacy PeriodicTask row and never submits that task automatically.
install_scheduler_hooks(_core)

# Dispatcharr parses plugin.json during discovery. Leaving these empty makes the
# manifest the single source of truth for the settings/action UI.
_core.Plugin.version = "0.2.12"
_core.Plugin.fields = []
_core.Plugin.actions = []

Plugin = _core.Plugin

# Re-export the legacy task symbol for compatibility/tooling. The plugin-owned
# scheduler calls run_handoff() directly and does not enqueue this task.
mustarrd_dvr_handoff_check = getattr(_core, "mustarrd_dvr_handoff_check", None)
