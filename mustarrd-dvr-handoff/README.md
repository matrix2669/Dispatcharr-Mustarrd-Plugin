# Mustarrd DVR Handoff for Dispatcharr

This plugin uses Dispatcharr as the DVR/series-pass UI and Mustarrd as the recorder for channels that support catch-up.

## Default flow

1. Dispatcharr creates its normal future `Recording` rows from **Record**, **Record Series**, or other DVR rules.
2. The plugin-owned scheduler runs every 5 minutes by default.
3. Catch-up-capable recordings up to **72 hours ahead** are mirrored into Mustarrd while the native Dispatcharr recording remains scheduled as a fallback.
4. The plugin uses Dispatcharr's own channel catch-up state and EPG metadata to build the Mustarrd schedule and filename.
5. When a recording enters the final **60-minute handoff window**, the plugin asks Mustarrd for its current catch-up channel list and confirms that Mustarrd still sees that channel.
6. It then reads the Mustarrd schedule back and verifies account, channel, program times, padding, and filename.
7. **Only after final verification succeeds** does it delete the Dispatcharr `Recording`. Dispatcharr's built-in `post_delete` signal revokes the native one-off DVR Celery task.
8. If any final check fails, the Dispatcharr recording remains intact and records normally.

Manual time recordings on catch-up channels are handed off as an exact synthetic time window. EPG-backed recordings that cannot be matched confidently against Dispatcharr's current guide are kept in Dispatcharr rather than risking the wrong Mustarrd program.

## Automatic scheduler

Version 0.2.12 no longer uses a plugin-defined Celery Beat task for automatic mirror/handoff checks. Dispatcharr 0.29 can load plugin tasks too late for the default prefork Celery consumer, causing `Received unregistered task` errors even though the task exists in child workers.

Instead, enabled uWSGI plugin instances check the configured 5-field UTC cron locally. A Redis minute lock ensures only one Dispatcharr worker runs a matching minute. The winning worker calls the same `run_handoff()` path used by **Run Mirror / Handoff Check Now**.

The scheduler's durable state is stored at:

```text
/data/plugins/.mustarrd-dvr-handoff-scheduler.json
```

On upgrade from an older release, an existing `plugin-mustarrd-dvr-handoff` Celery Beat row is migrated into that state file and deleted automatically. **Apply / Update Cron Schedule**, **Show Cron Status**, and **Remove Cron Schedule** keep the same UI workflow as before.

## Install

Add the central plugin registry to Dispatcharr:

```text
https://raw.githubusercontent.com/matrix2669/dispatcharr-plugins/main/manifest.json
```

Then install **Mustarrd DVR Handoff** from the Plugin Hub.

Plugin source and releases remain in `matrix2669/Dispatcharr-Mustarrd-DVR-Plugin`; registry/version metadata is maintained separately in `matrix2669/dispatcharr-plugins`.

## Mustarrd account

`Mustarrd Dispatcharr Account ID` must point to the Mustarrd Xtream account whose server is Dispatcharr.

Dispatcharr's Xtream implementation publishes:

```text
stream_id = Dispatcharr Channel.id
```

so the plugin can map a Dispatcharr DVR recording to Mustarrd without fuzzy channel matching.

## Authentication

The plugin uses Mustarrd's existing session + CSRF authentication.

A dedicated Mustarrd **download-only** user is sufficient when the plugin owns the schedules it creates.

## Default filename templates

The plugin renders filenames from Dispatcharr's EPG metadata before creating the Mustarrd schedule.

### TV

```text
TV Shows/{show} {tmdb}/Season {season:02d}/{show} - S{season:02d}E{episode:02d} - {title}
```

### Movies

```text
Movies/{title} ({year}) {tmdb}/{title} ({year})
```

### Sports

```text
Sports/{title} - {date}
```

### Other

```text
Other/{title} - {date}
```

Do **not** add a file extension to these templates. Mustarrd appends `.ts` to a scheduled custom filename when the value does not already end in `.ts`.

Nested templates require Mustarrd's template-subdirectory support (`sanitize_relative_path`) so `/` remains a directory separator instead of being flattened.

## Template tags

TV templates can use:

```text
{show} {season} {episode} {title} {date} {channel}
{tmdb} {tmdb_id} {tvdb_id} {imdb_id}
```

`{tmdb}` expands to both media-server identifiers:

```text
{tmdb-133532} [tmdbid-133532]
```

Movie templates additionally support `{year}`.

## Daily/yearly series season handling

Some XMLTV providers report an unknown season as `xmltv_ns` season `-1` while still supplying a useful episode sequence. Dispatcharr normalizes that provider value to season `0`, which Plex treats as **Specials**, and does not retain the raw XMLTV namespace in `ProgramData`.

When season `0` conflicts with an onscreen `S00`, the plugin restores the raw namespace from the matching fresh Mustarrd EPG entry. Raw season `-1` takes precedence and the handoff uses the airing year; otherwise onscreen `S00` remains a genuine special. Both the Mustarrd schedule payload and rendered filename use the corrected season.

Examples for **First Things First** airing in 2026:

```text
Dispatcharr EPG: season 0, episode 158
Mustarrd/Plex:    Season 2026 / S2026E158

Dispatcharr EPG: First Things First: OT, season 0, episode 145
Mustarrd/Plex:    Season 2026 / S2026E145
```

An explicit guide value such as `S00E03` remains season 0, so genuine specials are not rewritten.

After upgrading, any Mustarrd schedule that was already mirrored with an old `S00...` filename should be deleted once so the plugin can recreate it with the corrected yearly season.

## First setup

1. Save the Mustarrd URL, username/password, and Dispatcharr account ID.
2. Click **Test Mustarrd**.
3. Optional: enable **Dry Run**, then click **Run Mirror / Handoff Check Now**.
4. Disable Dry Run.
5. Click **Apply / Update Cron Schedule**.
6. Use **Show Cron Status** to confirm the plugin scheduler has begun running it.

Defaults:

```text
Mirror ahead: 72 hours
Final handoff: 60 minutes before Dispatcharr recording start
Cron: */5 * * * * UTC
```

## Fail-safe rules

The plugin never deletes a Dispatcharr recording when:

- Dispatcharr says the channel does not support catch-up;
- Mustarrd authentication or API access fails;
- an EPG-backed recording cannot be matched confidently against Dispatcharr's current guide;
- an existing or newly-created Mustarrd schedule does not match the expected program, padding, or filename;
- Mustarrd does not see the channel as catch-up capable during the final handoff check;
- the Dispatcharr recording changed or reached airtime during the handoff transaction.
