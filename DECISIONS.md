# Architecture Decisions

## ADR-001: Keep Dispatcharr as the fail-safe recorder

**Status:** Accepted
**Date:** 2026-08-11

Mirror catch-up-capable recordings to Mustarrd in advance, but retain the Dispatcharr recording until Mustarrd's current catch-up availability and exact schedule pass final verification. Any failure leaves Dispatcharr intact.

## ADR-002: Preserve raw XMLTV unknown-season precedence

**Status:** Accepted
**Date:** 2026-08-14

When Dispatcharr's reduced payload normalizes raw XMLTV season `-1` to season zero, enrich it from Mustarrd fresh EPG data. Raw `-1` uses the airing year even when onscreen data says `S00`; absent or nonnegative raw XMLTV preserves a genuine special.

## ADR-003: Use a plugin-owned scheduler

**Status:** Accepted
**Date:** 2026-08-17

Run the handoff cron from enabled uWSGI plugin instances and use a Redis minute lock to select one worker. Persist scheduler state in `/data/plugins/.mustarrd-dvr-handoff-scheduler.json` and migrate away from the legacy plugin Celery Beat task.

## ADR-004: Rename only the source repository

**Status:** Accepted
**Date:** 2026-08-22

Rename the GitHub repository from `matrix2669/Dispatcharr-Mustarrd-Plugin` to `matrix2669/Dispatcharr-Mustarrd-DVR-Plugin`. Do not rename the plugin, slug, source/install directory, state file, configuration, or runtime identifiers. GitHub's redirect preserves historical archive URLs while active metadata moves to the canonical name.

## ADR-005: Replace version branches with tags

**Status:** Accepted
**Date:** 2026-08-22

Create annotated tags `v0.1.0` through `v0.2.12` at the exact corresponding historical branch commits, verify every mapping, then delete the version branches. Future development follows `main`/`dev`, beta tags, and completed stable tags.

## ADR-006: Use a square crop-safe logo

**Status:** Accepted
**Date:** 2026-08-22

Use a square dark canvas with the complete Mustarrd wordmark centered inside a conservative safe area. Dispatcharr crops the prior wide asset to its center, making only “sta” visible.
