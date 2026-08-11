# Mustarrd DVR Handoff for Dispatcharr

This plugin uses Dispatcharr as the DVR/series-pass UI and Mustarrd as the recorder for channels that support catch-up.

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

## Install

Extract/copy this directory to:

```text
/app/data/plugins/mustarrd-dvr-handoff/
```

Then open Dispatcharr **Plugins**, refresh discovery, enable **Mustarrd DVR Handoff**, and configure it.

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

1. Save the Mustarrd URL, username/password, and Dispatcharr account ID.
2. Click **Test Mustarrd**.
3. Optional: enable **Dry Run**, then click **Run Handoff Check Now** while a catch-up DVR item is inside the handoff window.
4. Disable Dry Run.
5. Click **Apply / Update Cron Schedule**.
6. Use **Show Cron Status** to confirm Beat has begun running it.

Default cron:

```cron
* * * * *
```

Default handoff window:

```text
60 minutes before Dispatcharr recording start
```

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
