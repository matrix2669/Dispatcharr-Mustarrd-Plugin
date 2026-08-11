# Mustarrd DVR Handoff for Dispatcharr

This plugin uses Dispatcharr as the DVR/series-pass UI and source of truth for channel catch-up state, EPG metadata, and filename templates, while Mustarrd performs the actual catch-up recording.

## Default flow

1. Dispatcharr creates its normal future `Recording` rows from **Record**, **Record Series**, or other DVR rules.
2. The plugin's cron runs every 5 minutes.
3. Any future recording within the next **72 hours** is considered for mirroring.
4. If the Dispatcharr channel is not catch-up capable (`channel.is_catchup` / `catchup_days`), the plugin ignores it and Dispatcharr records normally.
5. For catch-up-capable channels, the plugin uses Dispatcharr's own `ProgramData` and `custom_properties` for title, subtitle, season/episode, category, TMDB/TVDB/IMDb IDs, and timestamps.
6. The plugin renders the filename locally from its configured TV/movie/sports/default templates and creates or verifies the Mustarrd schedule. The Dispatcharr recording remains scheduled as a fallback.
7. Inside the final **T-60 minute** window, the plugin asks Mustarrd for the configured account's catch-up-capable channel list and confirms that the Dispatcharr channel ID is still visible there.
8. It then reads `/api/schedules` back and verifies account, channel, start/stop timestamps, pre/post padding, filename, and active schedule state.
9. **Only after the final channel and schedule checks succeed** does it delete the Dispatcharr `Recording`. Dispatcharr's existing `post_delete` handling removes the native one-off DVR Celery task.
10. If any final check fails, the Dispatcharr recording is left untouched and remains the fallback recorder.

Manual time recordings on catch-up channels are mirrored using their exact requested time window.

## Mustarrd compatibility

The scheduling API, schedule-list API, authentication flow, and catch-up channel endpoint used by this plugin exist on upstream Mustarrd `main`.

The plugin's default filename templates intentionally contain subdirectories, for example:

```text
TV Shows/{show} {tmdb}/Season {season:02d}/{show} - S{season:02d}E{episode:02d} - {title}
```

Therefore Mustarrd also needs support for preserving `/` hierarchy in `custom_filename`. Until that template-subdirectory support is merged upstream, stock upstream Mustarrd will sanitize a nested custom filename as a single flat filename and the plugin's strict schedule verification will fail safe rather than delete the Dispatcharr recording.

## Mustarrd account

`Mustarrd Dispatcharr Account ID` must point to the Mustarrd Xtream account whose server is Dispatcharr.

Dispatcharr's Xtream output uses:

```text
stream_id = Dispatcharr Channel.id
```

so no fuzzy channel-name mapping is required.

## Filename templates

The plugin renders filenames from Dispatcharr EPG metadata rather than asking Mustarrd to re-fetch EPG or preview a filename.

Default TV template:

```text
TV Shows/{show} {tmdb}/Season {season:02d}/{show} - S{season:02d}E{episode:02d} - {title}
```

`{tmdb}` expands to both media-server tags when a TMDB ID exists:

```text
{tmdb-133532} [tmdbid=133532]
```

Available template fields include:

```text
{show}
{season}
{episode}
{title}
{date}
{channel}
{year}
{tmdb}
{tmdb_id}
{tvdb_id}
{imdb_id}
```

## Authentication

The plugin uses Mustarrd's existing session + CSRF authentication.

A dedicated Mustarrd **download-only** user is sufficient for normal operation.

## First setup

1. Save the Mustarrd URL, username/password, and Dispatcharr account ID.
2. Review the filename templates.
3. Click **Test Mustarrd**.
4. Optional: enable **Dry Run**, then click **Run Mirror / Handoff Check Now**.
5. Disable Dry Run.
6. Click **Apply / Update Cron Schedule**.
7. Use **Show Cron Status** to confirm Beat is running it.

Default cron:

```cron
*/5 * * * *
```

Default mirror window:

```text
72 hours ahead
```

Default final handoff window:

```text
60 minutes before Dispatcharr recording start
```

## Fail-safe rules

The plugin never deletes a Dispatcharr recording when:

- Dispatcharr says the channel does not support catch-up;
- Dispatcharr cannot confidently resolve the current EPG program;
- Mustarrd authentication or schedule API access fails;
- the Mustarrd schedule does not match the expected channel/timestamps/padding/filename;
- Mustarrd does not expose the channel as catch-up capable during the final T-60 check;
- the Mustarrd schedule cannot be read back and verified during the final check;
- the Dispatcharr recording changed or reached airtime during the handoff transaction.
