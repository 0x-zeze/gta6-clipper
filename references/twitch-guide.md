# Twitch Guide — VOD + Chat with TwitchDownloader

TwitchDownloader (lay295/TwitchDownloader, MIT) is the standard free tool
for downloading Twitch VODs, clips, and — most importantly for this skill —
**chat logs as JSON**. The chat JSON is what `twitch_chat_spikes.py` reads.

## Install

- **Windows**: download the GUI + CLI release from the repo's Releases page.
- **Linux/macOS**: download the CLI release (or `dotnet` build from source).
  The GUI is Windows-only; the CLI is cross-platform.
- FFmpeg must be on PATH (needed to finalize downloads).

## Download a VOD + its chat

```bash
# Find the VOD id in the URL: twitch.tv/videos/<vod_id>
TwitchDownloaderCLI videodownload --id 2468000000 -o vod.mp4
TwitchDownloaderCLI chatdownload  --id 2468000000 -o chat.json -E
```

- `-E` embeds emote metadata (optional, makes rendered chat prettier).
- Chat can also be saved as `.html` or `.txt`; this skill needs **JSON**.
- Gzipped chat (`chat.json.gz`) also works — the spike script reads it.

## Chat JSON format (what the spike script expects)

```json
{
  "streamer": {"name": "Lacy"},
  "video": {"id": "2468000000",
            "start": "2026-11-18T17:00:00Z",
            "end": "2026-11-18T23:00:00Z"},
  "comments": [
    {"_id": "...",
     "created_at": "2026-11-18T17:23:45.123Z",
     "content_offset_seconds": 1425.1,
     "message": {"body": "POGGERS"}}
  ]
}
```

- `content_offset_seconds` (seconds from VOD start) is preferred when present.
- Otherwise the offset is derived from `created_at` minus `video.start`
  (or the first comment's time if no video start is given).

## Sub-only VODs (OAuth)

Some VODs need authentication. Extract an OAuth token from your browser
(logged in to Twitch) and pass it:

```bash
TwitchDownloaderCLI videodownload --id <vod_id> --oauth <token> -o vod.mp4
TwitchDownloaderCLI chatdownload  --id <vod_id> --oauth <token> -o chat.json -E
```

See the TwitchDownloader README for how to get the token. Never paste the
token into chat or commit it — keep it in `.env` (`TWITCHDL_OAUTH_TOKEN`).

## Live alternative (no VOD wait)

- **Streamlink** records a live stream the moment it goes live:
  `streamlink twitch.tv/<channel> best -o live.ts`
- Read chat live via anonymous IRC (`justinfan` login, no token) and run
  the same 10-second bucket counting as `twitch_chat_spikes.py`.
- This is Rute B in the README — fastest to post, but needs a machine
  that stays on while the stream runs.

## Limits

- Deleted/expired VODs cannot be recovered by any downloader.
- Very long VODs are multi-GB — download and process on a real PC, not a
  thin VM.
- Respect the streamer's rules: downloading for personal clipping is only
  half the story — posting requires their permission (see streamers.md).
