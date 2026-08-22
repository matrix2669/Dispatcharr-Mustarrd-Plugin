# Production Readiness TODO

This checklist tracks the work required to prove that Mustarrd DVR Handoff can run against authoritative upstream dependencies without relying on undocumented fork-only behavior.

**Current status: blocked — dependency check required.**

Do not publish a production GitHub Release or add the plugin to `dispatcharr-plugins:main` until every production-gate item is complete. Test tags may continue through `dispatcharr-plugins:dev` using the normal beta workflow.

## 1. Inventory every upstream dependency

- [ ] Record the exact deployed Dispatcharr version/commit and current `Dispatcharr/Dispatcharr` upstream commit.
- [ ] Record the exact deployed Mustarrd image/version/commit, `razzamatazm/mustarrd:main`, and `matrix2669/mustarrd:dev` commits.
- [ ] Inventory every plugin import and host-provided Python/runtime dependency; identify whether Dispatcharr, the plugin archive, or the base image owns it.
- [ ] Inventory every HTTP endpoint, request field, response field, authentication behavior, scheduler primitive, model field, and deletion signal used by the plugin.
- [ ] Update `DEPENDENCIES.md` with the complete inventory and observation date.

## 2. Audit Mustarrd PR #408 against current upstream

PR #408 was closed and not merged. PRs #422–#424 incorporated selected portions but must not be assumed to contain the full dependency set.

- [ ] Preserve the exact #408 base and final head commits used for comparison.
- [ ] Produce a complete file/function/behavior inventory for the #408 diff.
- [ ] Compare every #408 change with current `razzamatazm/mustarrd:main`.
- [ ] For every change, classify it as:
  - required by this plugin and merged upstream;
  - required by this plugin but still fork-only/missing;
  - moved into this plugin and therefore no longer a Mustarrd dependency;
  - optional Mustarrd enhancement unrelated to plugin production;
  - superseded by a different upstream implementation, with equivalence proven by tests.
- [ ] Explicitly audit the portions upstream said were omitted from #408:
  - sports/program-type reclassification;
  - TMDB/TVDB/IMDb behavior and the `{tmdb}` token;
  - airing-year season derivation;
  - raw XMLTV `-1` precedence;
  - any filename/template behavior not included in #424.
- [ ] Confirm whether #422 supplies every raw field the plugin needs and whether #423 supplies it through the `fresh=true` channel EPG path.
- [ ] Confirm whether #424 preserves required metadata when scheduled recordings rebuild their program snapshot at dispatch.
- [ ] Record evidence for every conclusion in `DEPENDENCIES.md`; do not use “superseded” without the comparison evidence.

## 3. Validate the Mustarrd contract end to end

Run these checks against a clean build from current upstream Mustarrd, not the maintained fork:

- [ ] Authenticate through `/api/auth/csrf` and `/api/auth/login-credentials` as a dedicated download-only user.
- [ ] List the configured Dispatcharr-backed account and catch-up channels.
- [ ] Confirm Dispatcharr `Channel.id` maps exactly to Mustarrd `stream_id`.
- [ ] Create and read back `/api/schedules` with explicit pre/post padding, custom filename, program timestamps, and account/channel IDs.
- [ ] Confirm nested custom paths survive sanitization and produce the intended `.ts` path.
- [ ] Confirm `fresh=true` EPG responses retain raw onscreen and XMLTV episode values for both stored and sparse live guide rows.
- [ ] Validate First Things First and First Things First: OT raw `-1` cases through the real HTTP API.
- [ ] Validate a genuine `S00` special remains season zero.
- [ ] Validate manual-time recordings and EPG-backed recordings separately.
- [ ] Validate schedule verification, catch-up availability recheck, padding, and filename comparison.
- [ ] Run a dry-run handoff pass and verify it cannot delete a Dispatcharr recording.
- [ ] Run a final-window handoff with a disposable recording and verify Dispatcharr deletion occurs only after exact Mustarrd schedule verification.
- [ ] Record Mustarrd logs, plugin result counters, and exact tested commits without credentials or provider-sensitive data.

## 4. Audit the Dispatcharr contract

- [ ] Review the matching official Dispatcharr revision whenever the deployed version changes.
- [ ] Validate `plugin.json` against current Dispatcharr manifest/schema requirements.
- [ ] Confirm plugin loading still provides Django models, settings storage, action registration, Redis access, and uWSGI worker lifecycle used by the plugin.
- [ ] Confirm `Recording`, `ProgramData`, `Channel.is_catchup`, `Channel.catchup_days`, custom properties, and time fields retain the expected meanings.
- [ ] Confirm Dispatcharr still discards or preserves the raw XMLTV fields as documented; update enrichment behavior if that contract changed.
- [ ] Confirm deleting the verified `Recording` still revokes the native one-off DVR task through Dispatcharr's supported deletion path.
- [ ] Confirm the plugin-owned scheduler remains necessary and compatible; do not restore the former plugin Celery Beat task without resolving task-registration timing.
- [ ] Run the full plugin test suite against fixtures captured from the current Dispatcharr API/model shapes.
- [ ] Perform installation, upgrade, action, scheduler, and removal checks in a disposable Dispatcharr instance.

## 5. Create required upstream PRs

For each capability classified as required but missing upstream:

- [ ] Create one focused Mustarrd or Dispatcharr branch from current upstream `main`.
- [ ] Review the complete current upstream contribution guidance immediately before implementation and again before submission.
- [ ] Add a regression test that fails without the required capability.
- [ ] Keep one behavior/change per PR and avoid carrying unrelated fork commits.
- [ ] Open the upstream PR and record its repository, number, branch, head commit, requirement, and status in `DEPENDENCIES.md`.
- [ ] Keep the production gate blocked while any required PR is open, closed unmerged, or otherwise absent from upstream.
- [ ] When a PR merges, refresh upstream, retest the complete plugin contract, and record the merge commit.

## PR tracker

| Dependency | PR | Status | Plugin requirement | Next action |
|---|---|---|---|---|
| Mustarrd | #408 | Closed, not merged | Original structured EPG and related behavior; complete dependency coverage is unknown | Finish the change-by-change audit against current upstream. |
| Mustarrd | #416 | Merged | Nested template/custom filename paths | Revalidate with a real plugin-created schedule. |
| Mustarrd | #422 | Merged, partial #408 scope | Structured metadata storage/ingest | Confirm all raw fields required by the plugin. |
| Mustarrd | #423 | Merged, partial #408 scope | Sparse live EPG enrichment | Confirm `fresh=true` API behavior end to end. |
| Mustarrd | #424 | Merged, partial #408 scope | Scheduled-recording metadata and filenames | Confirm the plugin's schedule payload/readback contract. |
| Mustarrd | TBD | Dependency check required | Any required #408 capability still missing after audit | Create one focused PR per missing capability. |
| Dispatcharr | TBD | Dependency check required | Any current manifest/model/plugin-runtime incompatibility | Create focused PRs only after the current-version contract audit. |

## 6. Production completion gate

- [ ] Every upstream dependency and contract is listed in `DEPENDENCIES.md`.
- [ ] Every #408 change is classified with evidence.
- [ ] No required capability exists only in `matrix2669/mustarrd` without a merged upstream PR.
- [ ] No required Dispatcharr change exists only in a local workaround without a merged upstream PR or documented plugin-owned implementation.
- [ ] All required upstream PRs are merged and their merge commits are recorded.
- [ ] Current upstream Mustarrd and Dispatcharr pass automated and live end-to-end tests.
- [ ] `AGENT.md`, `DECISIONS.md`, `DEPENDENCIES.md`, `README.md`, and `CHANGELOG.md` agree on production status.
- [ ] Prepare a new immutable beta tag for the compatibility changes and publish it only to `dispatcharr-plugins:dev` for installation testing.
- [ ] After successful beta validation, promote a completed stable tag according to `RELEASE.md`.
- [ ] Create a production GitHub Release and update `dispatcharr-plugins:main` only after explicit user approval.

When every item is complete, transfer durable findings into `DEPENDENCIES.md` and `DECISIONS.md`, release-visible results into `CHANGELOG.md`, then remove this completed checklist if it no longer has active work.
