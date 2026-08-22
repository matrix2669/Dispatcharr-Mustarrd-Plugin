# Changelog

All notable user-visible changes are documented here. Architecture decisions belong in `DECISIONS.md`.

## [0.2.13-beta.1] - 2026-08-22

### Changed

- Rename only the GitHub repository to `matrix2669/Dispatcharr-Mustarrd-DVR-Plugin`; preserve the Mustarrd DVR Handoff display name, `mustarrd-dvr-handoff` slug, installed directory, scheduler state, settings, and runtime behavior.
- Replace the wide logo with a square, crop-safe asset so Dispatcharr shows the complete Mustarrd wordmark instead of only its center.
- Adopt the standalone `main`/`dev` workflow and replace permanent version branches with immutable tags at the exact same commits.

## [0.2.12] - 2026-08-17

- Replace plugin-defined Celery Beat scheduling with a plugin-owned cron scheduler guarded by a Redis minute lock.
- Migrate and remove the legacy Beat schedule while preserving the existing UI workflow.

## [0.2.11] - 2026-08-14

- Preserve the annual-series XMLTV correction through the complete handoff workflow.

## [0.2.10] - 2026-08-14

- Enrich reduced Dispatcharr EPG payloads from Mustarrd fresh EPG data so raw XMLTV season `-1` overrides onscreen `S00`; preserve genuine specials.

## [0.2.9] - 2026-08-14

- Correct annual-series season normalization for tested pre-enriched guide data.

## [0.2.8] - 2026-08-14

- Document and test airing-year handling for recurring season-zero series.

## [0.2.7] - 2026-08-14

- Use the airing year for recurring series whose normalized season is unknown.

## [0.2.6] - 2026-08-12

- Normalize plugin logging and diagnostics.

## [0.2.5] - 2026-08-12

- Improve scheduled-handoff status and cron diagnostics.

## [0.2.4] - 2026-08-12

- Fix the scheduled handoff queue.

## [0.2.3] - 2026-08-11

- Correct plugin loader behavior and remove temporary release markers.

## [0.2.2] - 2026-08-11

- Add the Mustarrd logo and plugin metadata.

## [0.2.1] - 2026-08-11

- Adopt Dispatcharr manifest UI fields, filename defaults, and the central registry.

## [0.2.0] - 2026-08-11

- Mirror eligible recordings up to 72 hours ahead while retaining Dispatcharr as fallback until final verification.

## [0.1.0] - 2026-08-11

- Initial Mustarrd DVR Handoff plugin and stable registry packaging.
