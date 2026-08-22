# Branches

This ledger records why every current branch exists. GitHub remains authoritative for live refs, commits, pull requests, and checks.

Before deleting a branch, transfer user-visible results to `CHANGELOG.md` and durable rationale to `DECISIONS.md`, then remove its entry here.

## Branch index

| Branch | Type | Status | Base | Target | Purpose |
|---|---|---|---|---|---|
| `main` | long-lived | active | repository history | stable source | Approved source baseline; production publication still requires every documented release and dependency gate. |
| `dev` | long-lived | active | `main` | `main` | Integrate and validate the next plugin version; synchronized for the `0.2.13-beta.2` dependency-audit build. |

## Active records

### `main`

- Current source version: `0.2.13-beta.2`; `v0.2.13-beta.2` identifies this dependency-audit test build, while `v0.2.13-beta.1` remains immutable at its original tested commit.
- Purpose: approved source baseline. No GitHub Releases currently exist, and `TODO.md` keeps production publication blocked until dependency readiness is proven.
- Integrated on 2026-08-22: repository rename/logo workflow, complete available-history documentation, dependency ledger, production-readiness TODO, and dual Mustarrd structured-EPG field compatibility.

### `dev`

- Purpose: integrate the next version under the standalone workflow.
- Current plugin version: `0.2.13-beta.2`.
- Current state: repository-only rename metadata, crop-safe logo, and tag-based workflow are integrated for development publication.
- Preserved identity: display name `Mustarrd DVR Handoff`, slug/source directory `mustarrd-dvr-handoff`, configuration, scheduler state, and runtime behavior.
- Validation: 18 unit tests pass, including upstream- and fork-shaped Mustarrd payloads; all plugin modules compile; JSON and version agreement pass; the logo is a 1254×1254 PNG; 14 historical tag mappings were verified before their version branches were deleted.
- Deployment validation: `0.2.13-beta.1` was published through the renamed repository and development registry; the user confirmed the installation and resized logo work correctly in Dispatcharr.

## Historical branch conversion

All 14 branches from `v0.1.0` through `v0.2.12` were converted to annotated tags at their exact commits and deleted from GitHub on 2026-08-22. Their release history remains in `CHANGELOG.md`; the deleted branches are intentionally absent from the live branch index.
