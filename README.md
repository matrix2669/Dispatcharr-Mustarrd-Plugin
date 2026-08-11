# Mustarrd DVR Handoff for Dispatcharr

This plugin uses Dispatcharr as the DVR/series-pass UI and Mustarrd as the recorder for channels that support catch-up.

## Add this repository to Dispatcharr

Add this manifest URL under Dispatcharr's **Plugin Repositories**:

```text
https://raw.githubusercontent.com/matrix2669/Dispatcharr-Mustarrd-Plugin/main/manifest.json
```

Dispatcharr will discover **Mustarrd DVR Handoff** from that repository and install it through the Plugins UI.

The repository uses Dispatcharr's two-level manifest format:

- `manifest.json` is the repository index and advertises the current `latest_version`.
- `metadata/mustarrd-dvr-handoff/manifest.json` stores the plugin version history.
- Each published plugin version is pinned to an immutable `vX.Y.Z` branch and downloaded through GitHub's versioned `zipball` endpoint.

When a newer `latest_version` is published, Dispatcharr can detect it and offer the update in the Plugins UI.

## Source layout

The installable plugin lives under:

```text
mustarrd-dvr-handoff/
```

Keeping `plugin.py` under a fixed directory gives Dispatcharr a stable plugin key across GitHub-generated ZIP archives.

## Default flow

1. Dispatcharr creates its normal future `Recording` rows from **Record**, **Record Series**, or other DVR rules.
2. The plugin's cron runs every minute.
3. When a future recording reaches **T-60 minutes**:
   - If the Dispatcharr channel is **not catch-up capable**, the plugin ignores it. Dispatcharr records it normally.
   - If the channel **is catch-up capable**, the plugin verifies that the same channel is exposed as catch-up by the configured Mustarrd account.
4. For an EPG-backed recording, the plugin re-fetches Mustarrd's **fresh EPG** and matches the current program before scheduling it.
5. The plugin asks Mustarrd to render the filename so TV metadata, nested templates, Plex `{tmdb-ID}`, and Jellyfin `[tmdbid=ID]` naming are preserved.
6. It creates the Mustarrd schedule and reads `/api/schedules` back to verify:
   - account
   - channel
   - program start/stop
   - pre/post padding
   - rendered filename
7. **Only after that verification succeeds** does it delete the Dispatcharr `Recording`. Dispatcharr's built-in `post_delete` signal revokes the native one-off DVR Celery task.
8. If any step fails, the Dispatcharr recording is left untouched and the next cron run tries again. If Mustarrd never becomes healthy before airtime, Dispatcharr remains the fallback recorder.

Manual time recordings on catch-up channels are handed off as an exact synthetic time window. EPG-backed recordings that cannot be matched confidently are kept in Dispatcharr rather than risking the wrong Mustarrd program.

## Mustarrd account

`Mustarrd Dispatcharr Account ID` must point to the Mustarrd Xtream account whose server is Dispatcharr.

Dispatcharr's Xtream implementation publishes:

```text
stream_id = Dispatcharr Channel.id
```

so the plugin can map a Dispatcharr DVR recording to Mustarrd without fuzzy channel matching.

## Authentication

The plugin uses Mustarrd's existing session + CSRF authentication.

A dedicated Mustarrd **download-only** user is sufficient if the plugin owns the schedules it creates. If other Mustarrd users frequently schedule the same programs, using an admin account lets the plugin read and fully verify those existing schedules instead of failing safe on an invisible duplicate.

## First setup

1. Install the plugin from the repository above and enable it.
2. Save the Mustarrd URL, username/password, and Dispatcharr account ID.
3. Click **Test Mustarrd**.
4. Optional: enable **Dry Run**, then click **Run Handoff Check Now** while a catch-up DVR item is inside the handoff window.
5. Disable Dry Run.
6. Click **Apply / Update Cron Schedule**.
7. Use **Show Cron Status** to confirm Beat has begun running it.

Default cron:

```cron
* * * * *
```

Default handoff window:

```text
60 minutes before Dispatcharr recording start
```

## Publishing a new version

For a new version such as `0.2.0`:

1. Update `mustarrd-dvr-handoff/plugin.py` and `mustarrd-dvr-handoff/plugin.json`.
2. Set the plugin version to `0.2.0` in both the class metadata and `plugin.json`.
3. Commit the release source.
4. Create an immutable branch named `v0.2.0` at that release commit.
5. Add a `0.2.0` entry to `metadata/mustarrd-dvr-handoff/manifest.json` and move its `latest` / `latest_version` to `0.2.0`.
6. Update root `manifest.json` so `latest_version` and `latest_url` point to `v0.2.0`.

Existing Dispatcharr installations using this repository will then see the version change through the normal plugin repository refresh/update flow.

## Fail-safe rules

The plugin never deletes a Dispatcharr recording when:

- the channel does not support catch-up;
- the channel is not catch-up-capable through Mustarrd's configured Dispatcharr account;
- Mustarrd authentication or API access fails;
- an EPG-backed recording cannot be matched confidently to the current Mustarrd guide;
- filename preview fails;
- an existing Mustarrd schedule does not match the expected padding/filename;
- a newly-created Mustarrd schedule cannot be read back and verified;
- the Dispatcharr recording changed or reached airtime during the handoff transaction.
