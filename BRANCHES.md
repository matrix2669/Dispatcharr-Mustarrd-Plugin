# Branches

This ledger records why every current branch exists. GitHub remains authoritative for live refs, commits, pull requests, and checks.

Before deleting a branch, transfer user-visible results to `CHANGELOG.md` and durable rationale to `DECISIONS.md`, then remove its entry here.

## Branch index

| Branch | Type | Status | Base | Target | Purpose |
|---|---|---|---|---|---|
| `main` | long-lived | active | repository history | stable source | Production-ready source and explicitly approved Releases. |
| `dev` | long-lived | active locally | `main` | `main` | Integrate and validate the next plugin version. |
| `feature/repository-rename-logo-workflow` | feature | active | `main` | `dev` | Rename only the repository, fix the cropped logo, and adopt tag-based standalone workflow. |

## Active records

### `main`

- Current plugin version: `0.2.12`.
- Purpose: production-ready source; no GitHub Releases currently exist.
- Verified head before this work: `64e0290efa6ee88375fa5399a9c5a9a4f5ac603a` on 2026-08-22.

### `dev`

- Purpose: integrate the next version under the standalone workflow.
- State: created locally from `main`; it will receive the reviewed feature work and beta tag.

### `feature/repository-rename-logo-workflow`

- Base: `main` at `64e0290efa6ee88375fa5399a9c5a9a4f5ac603a`.
- Target: `dev`.
- In scope: canonical repository URLs, square crop-safe logo, `0.2.13-beta.1`, standalone documentation, exact tag conversion, and deletion of superseded version branches.
- Out of scope: plugin display name, slug, source/install directory, scheduler state, configuration, and functional handoff behavior.
- Validation required: full unit suite, compilation, JSON/version checks, image dimensions, exact tag mappings, archive layout, and live development-registry resolution.

## Historical branch conversion

All 14 branches from `v0.1.0` through `v0.2.12` were converted to annotated tags at their exact commits and deleted from GitHub on 2026-08-22. Their release history remains in `CHANGELOG.md`; the deleted branches are intentionally absent from the live branch index.
