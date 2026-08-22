# AGENT.md

## Purpose

This repository owns the **Mustarrd DVR Handoff** Dispatcharr plugin. The canonical GitHub repository is `matrix2669/Dispatcharr-Mustarrd-DVR-Plugin`.

The repository rename is intentionally limited to source-hosting identity. Preserve the Dispatcharr display name **Mustarrd DVR Handoff**, registry slug and source directory `mustarrd-dvr-handoff`, normalized installed key, scheduler state path, field IDs, job behavior, and runtime contracts.

Review `DECISIONS.md`, `BRANCHES.md`, and `RELEASE.md` before changing the project.

## Architecture and ownership

- `mustarrd-dvr-handoff/plugin.json` is the Dispatcharr manifest and UI schema.
- `plugin.py` composes the core handoff, annual-series correction, and plugin-owned scheduler.
- `core.py` mirrors eligible Dispatcharr recordings to Mustarrd and removes the Dispatcharr fallback only after final verification.
- `annual_series.py` restores raw Mustarrd XMLTV data when Dispatcharr's reduced EPG payload cannot distinguish unknown seasons from specials.
- `scheduler.py` owns UTC cron evaluation, Redis minute locking, durable scheduler state, and legacy Beat migration.
- Dispatcharr owns DVR rows, plugin loading, native channel/catch-up state, and deletion signals.
- Mustarrd owns authenticated scheduling, catch-up availability, downloading, retries, and completed recordings.

## Non-negotiable rules

- Never delete the Dispatcharr fallback recording unless Mustarrd catch-up availability and the exact schedule are verified inside the configured final handoff window.
- Preserve `mustarrd-dvr-handoff`, `/data/plugins/.mustarrd-dvr-handoff-scheduler.json`, existing configuration field IDs, and the plugin display name.
- Raw XMLTV season `-1` takes precedence over onscreen `S00` and maps to the airing year; a genuine `S00` without raw `-1` remains season zero.
- Keep validation and dry-run paths non-destructive.
- Do not mutate published tags or archives.

## Branch and distribution workflow

- `main` is production-ready source and explicitly approved GitHub Releases.
- `dev` integrates the next version.
- short-lived `feature/*` and `fix/*` branches begin from and return to `dev`.
- beta tags use `vMAJOR.MINOR.PATCH-beta.N` on tested `dev` commits.
- completed work uses normal Semantic Version tags; no permanent version branches.
- `dispatcharr-plugins:dev` advertises the newest approved tag. `dispatcharr-plugins:main` changes only after explicit approval of a normal GitHub Release.

Track every current branch in `BRANCHES.md`. Before deleting one, transfer user-visible results to `CHANGELOG.md` and durable rationale to `DECISIONS.md`, then remove its live record.

## Validation

Run the complete `tests/` suite, compile all plugin Python modules, parse `plugin.json`, verify version agreement, and inspect the exact tagged archive. Whenever the supported or deployed Dispatcharr version changes, validate the manifest and plugin contract against the matching official `Dispatcharr/Dispatcharr` revision before publication.

## Future agent checklist

- Read the project documentation and relevant history.
- Confirm source, registry, and related-project state from fresh refs.
- Preserve the fail-safe handoff and annual-season decisions.
- Update the branch ledger before substantive work.
- Validate behavior and immutable archive metadata before publishing.
