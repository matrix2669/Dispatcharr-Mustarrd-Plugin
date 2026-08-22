# Mustarrd DVR Handoff for Dispatcharr

Dispatcharr plugin that mirrors catch-up-capable DVR recordings into Mustarrd and keeps Dispatcharr as a fail-safe recorder until the final handoff check.

## Install from the Dispatcharr plugin registry

Add this registry under **Plugins → Plugin Repositories**:

```text
https://raw.githubusercontent.com/matrix2669/dispatcharr-plugins/dev/manifest.json
```

Then install **Mustarrd DVR Handoff** from the Plugin Hub. The plugin is currently distributed through the development catalog for testing. The production `main` catalog is used only after explicit GitHub Release approval.

The registry and release metadata live separately in:

```text
https://github.com/matrix2669/dispatcharr-plugins
```

This repository contains the plugin source. Immutable semantic tags preserve published versions.

## Source layout

The installable plugin lives under:

```text
mustarrd-dvr-handoff/
```

Keeping the plugin under a fixed directory gives Dispatcharr a stable plugin key across GitHub-generated release ZIPs.

## Default flow

1. Dispatcharr creates its normal DVR `Recording` rows.
2. Every 5 minutes, the plugin considers catch-up-capable recordings up to 72 hours ahead.
3. Missing schedules are mirrored to Mustarrd using Dispatcharr's own EPG metadata and filename templates.
4. Dispatcharr's recording remains scheduled as a fallback.
5. Inside the final 60-minute window, the plugin confirms Mustarrd currently exposes the same channel as catch-up capable and verifies the Mustarrd schedule.
6. Only after those checks pass does the plugin delete the Dispatcharr recording.
7. Any failure leaves the Dispatcharr recording intact.

## Default filename templates

TV:

```text
TV Shows/{show} {tmdb}/Season {season:02d}/{show} - S{season:02d}E{episode:02d} - {title}
```

Movies:

```text
Movies/{title} ({year}) {tmdb}/{title} ({year})
```

Sports:

```text
Sports/{title} - {date}
```

Other:

```text
Other/{title} - {date}
```

Do not include a file extension. Mustarrd appends `.ts` to scheduled custom filenames that do not already end in `.ts`.

Nested paths require Mustarrd's template-subdirectory support so `/` is preserved as a directory separator.

Dispatcharr does not retain the raw XMLTV namespace in `ProgramData`, so the plugin restores it from the matching fresh Mustarrd EPG entry before applying season precedence. Raw XMLTV season `-1` uses the airing year even if the provider also emits onscreen `S00`. For example, **First Things First** airing in 2026 is handed to Mustarrd/Plex as `S2026E158` rather than `S00E158`. An explicit `S00` without raw XMLTV season `-1` remains a genuine special.

## Mustarrd account

`Mustarrd Dispatcharr Account ID` must point to the Mustarrd Xtream account whose server is Dispatcharr. Dispatcharr's Xtream output uses its `Channel.id` as the Xtream `stream_id`, so no fuzzy channel mapping is required.

A dedicated Mustarrd download-only user is sufficient for normal plugin operation.

The plugin accepts both current-upstream and historical-fork structured-guide field names. This is not yet a complete upstream-production compatibility determination: Mustarrd PR #408 was closed unmerged, and PRs #422–#424 contained only selected portions. `DEPENDENCIES.md` records the required comparison and current production gate.

Production readiness is currently blocked on the dependency audit in `TODO.md`, including the complete #408 comparison, live upstream Mustarrd and Dispatcharr contract validation, and any focused upstream PRs the audit identifies.

## Publishing

Plugin source/releases stay in this repository. Registry metadata is updated separately in `matrix2669/dispatcharr-plugins`.

For a new version:

1. Update the plugin source and `plugin.json` version.
2. Commit the release source.
3. Create an immutable `vX.Y.Z-beta.N` test tag or `vX.Y.Z` completed tag at that commit.
4. Update `dispatcharr-plugins/manifest.json` and `dispatcharr-plugins/plugins/mustarrd-dvr-handoff/manifest.json`.

Dispatcharr will then detect the new version through the registry refresh/update flow. See `RELEASE.md` for the complete `main`/`dev` workflow.

## Project history

`DECISIONS.md` records the recovered rationale, failed approaches, related-project contracts, and the exact ChatGPT/Codex sources reviewed. `CHANGELOG.md` records the corrected version-by-version history. Future bootstrap reviews must follow the workspace history gate rather than relying only on the current conversation or code state.
