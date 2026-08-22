# Branches

This ledger records why every current branch exists. GitHub remains authoritative for live refs, commits, pull requests, and checks.

Before deleting a branch, transfer user-visible results to `CHANGELOG.md` and durable rationale to `DECISIONS.md`, then remove its entry here.

## Branch index

| Branch | Type | Status | Base | Target | Purpose |
|---|---|---|---|---|---|
| `main` | long-lived | active | repository history | stable source | Production-ready source and explicitly approved Releases. |
| `dev` | long-lived | active | `main` | `main` | Integrate and validate the next plugin version; currently carries `0.2.13-beta.1`. |

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
- Remaining validation: publish the beta through the renamed repository and development registry, then confirm the Dispatcharr logo display.

## Historical branch conversion

All 14 branches from `v0.1.0` through `v0.2.12` were converted to annotated tags at their exact commits and deleted from GitHub on 2026-08-22. Their release history remains in `CHANGELOG.md`; the deleted branches are intentionally absent from the live branch index.
