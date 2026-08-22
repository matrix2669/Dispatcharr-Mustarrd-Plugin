# Changelog

All notable user-visible changes are documented here. Architecture rationale belongs in `DECISIONS.md`.

## Unreleased

### Added

- Track required Mustarrd API/data contracts, upstream/fork ownership, reviewed refs, and any required upstream pull requests in `DEPENDENCIES.md`; retain `dependency check required` when a dependency PR was closed unmerged and replacement work covered only part of it.
- Add `TODO.md` with the complete Mustarrd #408 comparison, Mustarrd and Dispatcharr contract audits, live validation, upstream PR creation, and production completion gates.

### Fixed

- Accept current upstream Mustarrd's `episode_num_xmltv` and `episode_num_onscreen` guide fields while retaining compatibility with the historical fork aliases, so annual-season correction no longer requires fork-only field names.

### Documentation

- Recover the complete available ChatGPT, Codex, repository, and related-project history into durable documentation.

## [0.2.13-beta.1] - 2026-08-22

- Rename only the GitHub repository to `matrix2669/Dispatcharr-Mustarrd-DVR-Plugin`; preserve the display name, `mustarrd-dvr-handoff` slug/directory, settings, scheduler state, and runtime behavior.
- Replace the wide logo with a square, crop-safe asset so Dispatcharr shows the complete wordmark.
- Adopt the standalone `main`/`dev` workflow and replace permanent version branches with immutable tags at the exact historical commits.

## [0.2.12] - 2026-08-17

- Replace the unreliable plugin-defined Celery Beat task with cron evaluation in enabled plugin workers and a Redis minute lock.
- Preserve the manual and automatic `run_handoff()` path, durable status, and existing schedule-management actions.
- Migrate the legacy Beat row into `/data/plugins/.mustarrd-dvr-handoff-scheduler.json`, then remove it.
- Eliminate Dispatcharr 0.29's `Received unregistered task` failure across Docker and LXC deployments.

## [0.2.11] - 2026-08-14

- Correct Plex/Jellyfin TMDB tags from `[tmdbid=#####]` to `[tmdbid-#####]` in rendered handoff filenames and documentation.
- Add regression coverage for the corrected shared Mustarrd/plugin template contract.

## [0.2.10] - 2026-08-14

- Fetch fresh Mustarrd EPG data when Dispatcharr's reduced payload lacks raw XMLTV metadata.
- Restore `episode_xmltv_ns`, then apply the annual-season correction to both the schedule and filename.
- Preserve genuine specials and safely continue when enrichment is unavailable.

## [0.2.9] - 2026-08-14

- Give raw XMLTV season `-1` precedence over onscreen `S00` when raw XMLTV is already present.
- Expose a live integration gap: Dispatcharr removes the raw namespace before its normal plugin payload; 0.2.10 added the enrichment path.

## [0.2.8] - 2026-08-14

- Expand documentation, examples, and tests for annual season handling in the schedule payload and filename.

## [0.2.7] - 2026-08-14

- Introduce airing-year seasons for recurring series whose normalized season is unknown.

## [0.2.6] - 2026-08-12

- Normalize plugin logging through Dispatcharr's plugin logger and improve scheduler diagnostics.

## [0.2.5] - 2026-08-12

- Improve cron status reporting and diagnostics for scheduled handoff checks.

## [0.2.4] - 2026-08-12

- Move the Beat task from the `dvr` queue to the default `celery` queue to address execution failures in the DVR thread worker. Version 0.2.12 later replaced plugin Celery scheduling after a separate prefork registration failure.

## [0.2.3] - 2026-08-11

- Remove the temporary release marker used during packaging cleanup; retain the normal plugin loader layout.

## [0.2.2] - 2026-08-11

- Add the Mustarrd logo and plugin metadata, then remove the one-time asset import workflow.

## [0.2.1] - 2026-08-11

- Move version/download metadata into the central `dispatcharr-plugins` registry.
- Complete the Dispatcharr settings UI and default filename templates.

## [0.2.0] - 2026-08-11

- Mirror eligible catch-up recordings up to 72 hours ahead while leaving the native Dispatcharr recording scheduled.
- Add the final 60-minute catch-up and exact-schedule verification before removing the fallback.

## [0.1.0] - 2026-08-11

- Initial Mustarrd DVR Handoff implementation, Dispatcharr manifest/UI, stable installable directory, and registry packaging.
- Hand off catch-up-capable DVR recordings one hour before airtime only after verifying the matching Mustarrd schedule; leave all other recordings in Dispatcharr.
