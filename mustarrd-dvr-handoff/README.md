# Mustarrd DVR Handoff for Dispatcharr

This plugin uses Dispatcharr as the DVR/series-pass UI and Mustarrd as the recorder for channels that support catch-up.

## Default flow

1. Dispatcharr creates its normal future `Recording` rows from **Record**, **Record Series**, or other DVR rules.
2. The plugin cron runs every 5 minutes by default.
3. Catch-up-capable recordings up to **72 hours ahead** are mirrored into Mustarrd while the native Dispatcharr recording remains scheduled as a fallback.
4. The plugin uses Dispatcharr's own channel catch-up state and EPG metadata to build the Mustarrd schedule and filename.
5. When a recording enters the final **60-minute handoff window**, the plugin asks Mustarrd for its current catch-up channel list and confirms that Mustarrd still sees that channel.
6. It then reads the Mustarrd schedule back and verifies account, channel, program times, padding, and filename.
7. **Only after final verification succeeds** does it delete the Dispatcharr `Recording`. Dispatcharr's built-in `post_delete` signal revokes the native one-off DVR Celery task.
8. If any final check fails, the Dispatcharr recording remains intact and records normally.

Manual time recordings on catch-up channels are handed off as an exact synthetic time window. EPG-backed recordings that cannot be matched confidently against Dispatcharr's current guide are kept in Dispatcharr rather than risking the wrong Mustarrd program.

## Install

Add the central plugin registry to Dispatcharr:

```text
https://raw.githubusercontent.com/matrix2669/dispatcharr-plugins/main/manifest.json
```

Then install **Mustarrd DVR Handoff** from the Plugin Hub.

Plugin source and releases remain in `matrix2669/Dispatcharr-Mustarrd-Plugin`; registry/version metadata is maintained separately in `matrix2669/dispatcharr-plugins`.

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
{tmdb-133532} [tmdbid=133532]
```

Movie templates additionally support `{year}`.

## First setup

1. Save the Mustarrd URL, username/password, and Dispatcharr account ID.
2. Click **Test Mustarrd**.
3. Optional: enable **Dry Run**, then click **Run Mirror / Handoff Check Now**.
4. Disable Dry Run.
5. Click **Apply / Update Cron Schedule**.
6. Use **Show Cron Status** to confirm Beat has begun running it.

Defaults:

```text
Mirror ahead: 72 hours
Final handoff: 60 minutes before Dispatcharr recording start
Cron: */5 * * * *
```

## Fail-safe rules

The plugin never deletes a Dispatcharr recording when:

- Dispatcharr says the channel does not support catch-up;
- Mustarrd authentication or API access fails;
- an EPG-backed recording cannot be matched confidently to Dispatcharr's current guide;
- an existing or newly-created Mustarrd schedule does not match the expected program, padding, or filename;
- Mustarrd does not see the channel as catch-up capable during the final handoff check;
- the Dispatcharr recording changed or reached airtime during the handoff transaction.
