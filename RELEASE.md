# Release Process

## Version and channel rules

- Keep `VERSION`, `mustarrd-dvr-handoff/plugin.json`, `Plugin.version`, `CHANGELOG.md`, and the Git tag synchronized.
- Use `vMAJOR.MINOR.PATCH-beta.N` tags for testing and normal `vMAJOR.MINOR.PATCH` tags for completed work.
- Never create a permanent version branch or move a published tag.
- Publish beta and completed tags through `dispatcharr-plugins:dev`.
- Create a GitHub Release and update `dispatcharr-plugins:main` only with explicit user approval.

## Required validation

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile mustarrd-dvr-handoff/*.py
python3 -m json.tool mustarrd-dvr-handoff/plugin.json >/dev/null
```

Also verify version agreement, the exact tag commit, the archive's `mustarrd-dvr-handoff/` layout, the logo URL, and a Dispatcharr install/update. Recheck the official Dispatcharr plugin contract whenever its supported or deployed version changes.

## Beta publication

Integrate the versioned change into `dev`, tag the tested commit, push the tag without creating a GitHub Release, and update only `dispatcharr-plugins:dev` to the exact tag and commit. Dispatcharr updates are version-driven.

## Stable completion and release

After testing, finalize the stable version, promote the exact code to `main`, tag it, and point the registry `dev` channel to that completed tag. A normal tag does not authorize a Release. When the user explicitly approves a Release, attach a clean ZIP containing only the `mustarrd-dvr-handoff/` plugin directory plus a checksum, then make a focused registry `main` update.
