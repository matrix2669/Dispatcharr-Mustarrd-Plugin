# Architecture Decisions

This file preserves why the plugin works as it does. Release-by-release behavior belongs in `CHANGELOG.md`; operating instructions belong in `AGENT.md` and `README.md`.

## ADR-001: Use Dispatcharr for DVR intent and Mustarrd for catch-up recording

**Status:** Accepted
**Date:** 2026-08-11

Dispatcharr remains the user-facing DVR and series-pass system. For channels with catch-up, the plugin mirrors recording intent into Mustarrd, which owns archive access, scheduling, downloading, retries, and completed recordings. Dispatcharr `Channel.id` maps directly to the Xtream `stream_id` exposed by Dispatcharr and configured in Mustarrd, so the plugin must not introduce fuzzy channel matching.

This boundary retains Dispatcharr's scheduling experience while using Mustarrd's catch-up recorder. A dedicated Mustarrd download-only user is sufficient; the plugin uses Mustarrd's session and CSRF authentication.

## ADR-002: Keep the Dispatcharr recording as a fail-safe until final verification

**Status:** Accepted
**Date:** 2026-08-11

Mirror eligible schedules early—72 hours by default—but retain the native Dispatcharr recording until the final handoff window—60 minutes by default. The final transaction confirms that Mustarrd currently reports the channel as catch-up capable and that the Mustarrd schedule still matches account, channel, program window, padding, and filename. Re-read the Dispatcharr row immediately before deletion so a changed or already-started recording is never removed from stale state.

Any authentication, API, matching, validation, or race failure leaves Dispatcharr intact. Dry-run and diagnostic operations are always non-destructive. A schedule may therefore be counted as mirrored and skipped in the same pass: mirroring succeeded, but the fallback remains because final safety requirements were not satisfied.

## ADR-003: Treat manual and EPG-backed recordings differently

**Status:** Accepted
**Date:** 2026-08-11

Manual-time recordings may be handed off as an exact synthetic window. EPG-backed recordings require a confident match against current guide data. If matching is uncertain, retain the Dispatcharr fallback rather than risk recording the wrong program.

Padding is derived from the Dispatcharr recording window relative to the original EPG program and sent explicitly to Mustarrd. Mustarrd creates one padded catch-up request by shifting the start and extending duration; it does not fetch separate padding streams.

## ADR-004: Render Mustarrd filenames from Dispatcharr metadata

**Status:** Accepted
**Date:** 2026-08-11
**Amended:** 2026-08-14

The plugin renders TV, movie, sports, and generic filenames before creating the Mustarrd schedule. Templates omit an extension because Mustarrd appends `.ts`. Nested paths depend on Mustarrd's `sanitize_relative_path` behavior so `/` remains a directory separator.

Metadata tags use the media-server syntax `[tmdbid-#####]`, not `[tmdbid=#####]`. This contract is shared with Mustarrd and must be changed in both projects with regression coverage.

## ADR-005: Restore raw XMLTV before applying annual-series precedence

**Status:** Accepted
**Date:** 2026-08-14

For daily series, raw XMLTV season `-1` represents an unknown/annual season and takes precedence over onscreen `S00`; map it to the airing year. A genuine `S00` without raw `-1`, or with a nonnegative raw season, remains season zero.

Version 0.2.9 proved that normalization worked only when tests supplied pre-enriched raw XMLTV. Real Dispatcharr `ProgramData` retains normalized season, episode, and onscreen values but discards the raw namespace, so live plugin-created schedules still used `S00`. Version 0.2.10 corrected the data boundary: query Mustarrd's fresh EPG endpoint with `days_back=7&fresh=true`, match by program ID or timestamps, copy `episode_xmltv_ns`, then normalize both the schedule payload and rendered filename.

Regression controls include:

- First Things First: `S00E158` plus `-1.157.` becomes `S2026E158`.
- First Things First: OT: `S00E145` plus `-1.144.` becomes `S2026E145`.
- `S00E03` without raw `-1` remains a genuine special.

Lookup failure is fail-safe. Existing Mustarrd schedules are not silently rewritten; delete and recreate an older `S00` schedule after upgrading.

## ADR-006: Replace plugin Celery Beat scheduling with a plugin-owned scheduler

**Status:** Accepted
**Date:** 2026-08-17

Early versions registered a Celery Beat task. Version 0.2.4 moved it from Dispatcharr's `dvr` queue to the default `celery` queue because plugin task initialization was unreliable in the thread-based DVR worker. Dispatcharr 0.29 then exposed the opposite failure in the default prefork worker: the consumer could start before plugin task registration and report `Received unregistered task of type 'mustarrd_dvr_handoff.check'`. The failure occurred in both Docker and Proxmox LXC, so it was architectural rather than deployment-specific.

Version 0.2.12 replaced the Beat task with cron evaluation in enabled uWSGI plugin instances. A Redis minute lock elects one worker, which calls the same `run_handoff()` path as the manual action. Scheduler state is durable at `/data/plugins/.mustarrd-dvr-handoff-scheduler.json`. Upgrade imports the enabled state and cron from the legacy `plugin-mustarrd-dvr-handoff` Beat row, then removes that row. Preserve the existing Apply, Status, and Remove UI workflow.

Live validation confirmed automatic execution with an enabled `*/5 * * * *` schedule, removal of the legacy Beat row, and a successful pass that considered and mirrored six recordings without the former unregistered-task error.

## ADR-007: Keep plugin version metadata in the registry repository

**Status:** Accepted
**Date:** 2026-08-11
**Amended:** 2026-08-22

This repository owns source and immutable semantic tags. `matrix2669/dispatcharr-plugins` owns catalog manifests and archive URLs. Dispatcharr detects updates by manifest version, so every test publication needs a monotonically advancing beta tag.

Registry `dev` advertises the newest approved tag—beta while testing is active, otherwise the latest completed stable tag even if it is not a GitHub Release. Registry `main` changes only after explicit approval of a normal GitHub Release. A tag is not itself release approval.

## ADR-008: Rename only the source repository

**Status:** Accepted
**Date:** 2026-08-22

Rename GitHub from `matrix2669/Dispatcharr-Mustarrd-Plugin` to `matrix2669/Dispatcharr-Mustarrd-DVR-Plugin`. Preserve the Dispatcharr display name **Mustarrd DVR Handoff**, registry slug and source/install directory `mustarrd-dvr-handoff`, normalized installed key, field IDs, scheduler state path, and runtime contracts. GitHub redirects preserve historical URLs, while current metadata uses the canonical name.

## ADR-009: Replace permanent version branches with immutable tags

**Status:** Accepted
**Date:** 2026-08-22

Convert historical branches `v0.1.0` through `v0.2.12` to annotated tags at their exact commits, verify every mapping, and delete the branches. Future work uses `main`, `dev`, temporary feature/fix branches, beta tags, and completed stable tags. Published tags and archives are immutable.

## ADR-010: Use a square, crop-safe logo

**Status:** Accepted
**Date:** 2026-08-22

Dispatcharr center-cropped the prior wide asset so only “sta” was visible. Use a square dark canvas with the complete wordmark centered inside a conservative safe area. The change is visual only and does not alter plugin identity.

## ADR-011: Prefer upstream Mustarrd contracts and track fork-only requirements

**Status:** Accepted
**Date:** 2026-08-22

Treat `razzamatazm/mustarrd:main` as the production dependency and `matrix2669/mustarrd` as a development/maintenance fork. Record the exact reviewed refs and every required endpoint, response field, and behavioral contract in `DEPENDENCIES.md`.

The structured EPG work began in the fork and PR #408. That PR was closed unmerged. Upstream PRs #422–#424 incorporated selected parts but explicitly omitted other #408 behavior. Upstream uses `episode_num_xmltv` and `episode_num_onscreen`, while the fork implementation used `episode_xmltv_ns` and `episode_onscreen`; the plugin accepts both spellings. This resolves one known contract difference but does not establish that current upstream contains every dependency the plugin had in the fork.

Therefore the production status remains **dependency check required** until #408 is compared change-by-change with current upstream and the plugin completes live end-to-end validation against upstream Mustarrd. Any required omitted capability must receive a focused upstream PR or be removed/moved into the plugin before upstream-production readiness is declared.

If future plugin operation depends on fork-only Mustarrd code, production readiness is blocked until a focused upstream PR is tracked and merged, or the dependency is removed or moved into the plugin. Fork enhancements that do not participate in the plugin contract must not be listed as production requirements.

## History-review provenance

The 2026-08-22 recovery reviewed the complete local Git history, every tag and live branch, source, tests, manifests, current documentation, available memory, and the following available ChatGPT/Codex tasks through their available pages:

- `Simplify Plugin Versioning` (`6a898c9e-1ffc-83ea-8fcc-b44788fea3c0`)
- `Diagnose DVR Plugin Error` (`6a836032-667c-83ea-9455-85dc4364561e`)
- `Fix XMLTV season precedence` (`01a00079-27da-7622-8136-07e1381e3941`)
- `TMDBID Template Correction` (`6a7fb7d5-78cc-83ea-8700-dafa5a20cd69`)
- `Sonarr Radarr VOD Connector` (`6a7c763c-62d4-83ea-a2a6-0fddaab941e4`), including the original bootstrap/history requirements and shared Mustarrd integration context
- `Update standalone release workflow` (`01a02969-01f0-7803-8031-37f7f4f2803c`)

`Bootstrap repository project` (`6a88943c-c668-83ea-a341-6424daeb526a`) was inspected and excluded because it documents the separate VOD Newznab/Arr Stack Connector project. No archived Codex tasks or synced `sources/` files were available. GitHub-hosted issues and pull requests were represented only where captured in accessible history; no undocumented rationale is inferred from unavailable sources.
