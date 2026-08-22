# Dependency Compatibility

This ledger tracks external contracts required for the plugin to work. GitHub and the dependency repositories remain authoritative for live state.

## Production gate

**Status: dependency check required.** Upstream production compatibility is not yet cleared.

Mustarrd PR #408 was closed and not merged. Upstream PRs #422–#424 incorporated selected parts of that work, but they explicitly did not contain all of #408. Their existence must not be treated as proof that every Mustarrd capability required by this plugin is upstream.

The plugin now accepts the field names observed in current upstream (`episode_num_xmltv`, `episode_num_onscreen`) and the historical fork aliases (`episode_xmltv_ns`, `episode_onscreen`). That resolves one identified contract difference only. A complete dependency-by-dependency comparison of the plugin's working fork environment against current upstream, followed by live end-to-end validation, is still required before declaring the plugin production-compatible with upstream Mustarrd.

## Last verified state

- Reviewed: 2026-08-22.
- Upstream: `razzamatazm/mustarrd:main` at `2b7ea998eb5918da9447488d148c526a77091497`.
- Fork production/integration reference reviewed: `matrix2669/mustarrd:dev` at `5c23b0805ed0ad3c8d30a2fce83571d790668695`.
- Historical dependency PR: `razzamatazm/mustarrd#408`, closed unmerged on 2026-08-21. Upstream PRs #422–#424 incorporated selected work from it but are not complete replacements.
- Required upstream PRs: **dependency check required because PR #408 was closed and not merged**. After the comparison, record each missing required capability and its focused upstream PR, or explicitly prove that no additional PR is required.
- Validation completed so far: 82 current-upstream tests covering metadata ingest, sparse live-guide enrichment, scheduled dispatch metadata, and filename handling passed from an exact `upstream/main` archive; all 18 plugin tests, including upstream- and fork-shaped EPG payloads, passed. These tests validate the inspected contracts but do not prove complete equivalence with the fork or replace live end-to-end dependency validation.

## Contract matrix

| Capability used by plugin | Upstream status | Fork history | Production conclusion |
|---|---|---|---|
| Session login through `/api/auth/csrf` and `/api/auth/login-credentials`, including download-only users | Native upstream | Also present in fork | No fork dependency. |
| List catch-up channels and map Mustarrd `stream_id` to Dispatcharr `Channel.id` | Native upstream | Also present in fork | No fork dependency. |
| Create/list `/api/schedules` with explicit program, custom filename, and pre/post padding | Native upstream | Also present in fork | No fork dependency. |
| Preserve nested custom filename paths | Merged upstream in PR #416 | Earlier fork work was proposed in PRs #406/#407 | No fork dependency; upstream is authoritative. |
| Preserve structured XMLTV metadata and fill sparse fresh EPG responses | Selected behavior merged in PRs #422/#423; schedule dispatch metadata changed in #424 | Broader implementation originated in the fork and unmerged PR #408 | Field-name compatibility is tested, but complete dependency equivalence remains unverified. |
| Annual unknown-season-to-airing-year support | Upstream intentionally omitted the policy portion of #408 | The fork carried related structured metadata and policy work | The plugin owns the policy, but its complete supporting-data dependency must be confirmed by the pending comparison. |
| `[tmdbid-#####]` formatting in the plugin's custom filename | Plugin-owned | Fork also corrected Mustarrd's own filename generators | The fork's TMDB formatting changes are not required by this plugin. |

## Upstream change review

Before publishing any plugin tag or after changing the deployed Mustarrd version:

1. Refresh `razzamatazm/mustarrd:main` and record the exact commit above.
2. Compare changes to authentication, channel/catch-up APIs, schedule request/response fields, guide metadata, custom filename sanitization, and padding behavior.
3. Run plugin tests with fixtures matching the current upstream response names and verify a live dry-run against the deployed Mustarrd build.
4. Update this matrix with the new upstream and fork refs.
5. If a required capability exists only in `matrix2669/mustarrd`, record its branch and commit, open or identify the focused upstream PR, and mark the plugin blocked from upstream-only production until that PR is merged or the dependency is moved into the plugin.

For closed, unmerged, split, or purportedly superseded dependency PRs, compare the original PR change-by-change against what actually merged. Never infer complete coverage from the maintainer's summary, shared ancestry, similar PR titles, or passing tests for only the merged subset.

Closed or superseded PRs remain historical evidence, not proof that their dependencies landed.
