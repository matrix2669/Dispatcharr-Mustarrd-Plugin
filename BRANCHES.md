# Branches

This ledger records why every current branch exists. GitHub remains authoritative for live refs, commits, pull requests, and checks.

Before deleting a branch, transfer user-visible results to `CHANGELOG.md` and durable rationale to `DECISIONS.md`, then remove its entry here.

## Branch index

| Branch | Type | Status | Base | Target | Purpose |
|---|---|---|---|---|---|
| `main` | long-lived | active | repository history | stable source | Production-ready source and explicitly approved Releases. |
| `dev` | long-lived | active | `main` | `main` | Integrate and validate the next plugin version; currently carries `0.2.13-beta.1`. |
| `docs/complete-history-review` | documentation | active | `dev` | `dev` | Recover the complete available chat, Codex, repository, and related-project history into durable project documentation. |

## Active records

### `main`

- Current plugin version: `0.2.12`.
- Purpose: production-ready source; no GitHub Releases currently exist.
- Verified head before this work: `64e0290efa6ee88375fa5399a9c5a9a4f5ac603a` on 2026-08-22.

### `dev`

- Purpose: integrate the next version under the standalone workflow.
- Current plugin version: `0.2.13-beta.1`.
- Current state: repository-only rename metadata, crop-safe logo, and tag-based workflow are integrated for development publication.
- Preserved identity: display name `Mustarrd DVR Handoff`, slug/source directory `mustarrd-dvr-handoff`, configuration, scheduler state, and runtime behavior.
- Validation: 16 unit tests pass; all plugin modules compile; JSON and version agreement pass; the logo is a 1254×1254 PNG; 14 historical tag mappings were verified before their version branches were deleted.
- Deployment validation: `0.2.13-beta.1` was published through the renamed repository and development registry; the user confirmed the installation and resized logo work correctly in Dispatcharr.

### `docs/complete-history-review`

- Purpose: correct the preliminary bootstrap by reviewing all available ChatGPT and Codex history, repository history, and related Mustarrd/Dispatcharr context before rebuilding the durable documentation.
- Scope: recover project documentation, add Mustarrd/Dispatcharr dependency tracking and a production-readiness TODO, and accept current upstream structured-EPG field names without changing plugin identity or published tags.
- Source: `dev` at `31dc8bc923ab533d30e7e1d2012e9feceb49998c`.
- Target: `dev`.
- Validation: documentation consistency; refreshed upstream/fork contract comparison; 82 targeted tests from an exact current-upstream archive; 18 plugin tests with upstream- and fork-shaped payloads; Python compilation; manifest parsing; and version agreement.
- Expected outcome: future agents can recover the plugin's design, failures, release evolution, and operating constraints without access to the original conversations.

## Historical branch conversion

All 14 branches from `v0.1.0` through `v0.2.12` were converted to annotated tags at their exact commits and deleted from GitHub on 2026-08-22. Their release history remains in `CHANGELOG.md`; the deleted branches are intentionally absent from the live branch index.
