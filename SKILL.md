---
name: gta6-clipper
description: >
  GTA VI stream clipper: turn long Twitch streams into 15-60s vertical
  YouTube Shorts. Detect viral moments from Twitch chat velocity spikes,
  cut 9:16 vertical clips with FFmpeg, caption with faster-whisper,
  translate captions EN->ID, and prepare Shorts copy. Use when the user
  wants to clip a GTA VI streamer, find highlights in a Twitch VOD, or
  make Shorts from stream footage. Keywords: gta 6, gta vi, clipper,
  twitch, chat spike, vertical video, youtube shorts, 9:16, caption.
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - AskUserQuestion
model: claude-sonnet-4-5-20250514
---

# GTA VI Clipper Skill

> **Install**: `npx skills add https://github.com/0x-zeze/gta6-clipper`
> or copy this folder to `~/.claude/skills/gta6-clipper/`.
> Adapted from op7418/Youtube-clipper-skill (MIT) — see ATTRIBUTION.md.

You turn a long GTA VI Twitch stream into ready-to-post YouTube Shorts.
Follow the 6 stages in order. **Never skip Stage 1 (permission).**

---

## Stage 1 — Pick the streamer (permission first)

**Goal**: choose a target with big live views AND verified clip permission.

1. Read `streamers.md` for the launch-day shortlist (live viewer counts +
   permission status per streamer).
2. Rules:
   - **Only clip streamers who allow it.** Permission = an active paid
     campaign whose rules you follow (e.g. Lacy GTA VI Marathon Pool on
     Content Rewards), or an explicit statement from the streamer.
   - If status is `TIDAK TAHU` (unknown), do NOT clip. Ask the user to
     verify the streamer's rules first, or pick another streamer.
   - If the user joins a paid campaign, read the campaign brief first:
     required tags, disclosure, account rules, submit-link deadline
     (usually ≤30 min after posting). The brief overrides everything.
3. Confirm with the user: streamer name + campaign (if any) before
   downloading anything.

## Stage 2 — Download VOD + chat

**Goal**: get the video and the chat log. Prefer TwitchDownloaderCLI.

```bash
# Twitch VOD + chat (recommended)
TwitchDownloaderCLI videodownload --id <vod_id> -o vod.mp4
TwitchDownloaderCLI chatdownload --id <vod_id> -o chat.json -E
```

- `<vod_id>` is the number in the Twitch VOD URL
  (`twitch.tv/videos/<vod_id>`).
- `-E` embeds emotes metadata; chat JSON is the input for Stage 3.
- Sub-only VODs need an OAuth token (see references/twitch-guide.md).
- **Do NOT download multi-GB VODs on a thin VM** (~1 GB free RAM, no GPU).
  Download and process on the user's PC/laptop. On this VM, only test
  with small files.
- YouTube source instead? Use `scripts/download_video.py <youtube_url>`
  (yt-dlp, up to 1080p) — but then there is no Twitch chat for Stage 3;
  fall back to subtitle analysis (`scripts/analyze_subtitles.py`).

## Stage 3 — Detect moments (chat spikes)

**Goal**: find viral moments from chat velocity, not by watching hours.

```bash
python3 scripts/twitch_chat_spikes.py --chat chat.json --output moments.json
```

- Buckets messages per 10 seconds; baseline = rolling 5-minute median.
- A bucket is a spike when count >= 3x baseline (and >= baseline + 15,
  and >= 20 messages). Tune `--factor` / `--min-count` per channel:
  huge channels need higher `--min-count`.
- Each candidate: `clip_start = peak_time - 20s` (chat reacts late),
  duration clamped to 15-60s.
- Output: `moments.json` + a ranked table (strongest spike first).
- If no spikes: lower `--factor` to 2.0-2.5 or `--min-count` to 10.

**No Twitch chat available?** Fall back to `scripts/analyze_subtitles.py`
on the subtitle file — but note this only finds *spoken* moments and
misses pure gameplay reactions. Prefer chat spikes for GTA VI.

## Stage 4 — Review candidates (user picks)

**Goal**: let the user choose which moments become Shorts.

1. Show the ranked candidate list: clip start (HMS), duration,
   peak msgs/10s, spike factor.
2. Ask the user (AskUserQuestion, multi-select) which candidates to cut
   + layout per clip (`gameplay` or `facecam-top`/`facecam-bottom`).
3. Confirm the plan before cutting. Do not cut all spikes blindly —
   3-10 best moments per VOD is the sweet spot for launch week.

## Stage 5 — Cut vertical + caption

**Goal**: 1080x1920 Shorts with burned captions, EN->ID.

For each chosen candidate:

### 5.1 Vertical cut

```bash
python3 scripts/vertical_cut.py --input vod.mp4 --start <clip_start> \
    --duration 30 --layout gameplay --output clip_01.mp4
# facecam layout needs the webcam region in source pixels:
python3 scripts/vertical_cut.py --input vod.mp4 --start <clip_start> \
    --duration 30 --layout facecam-top --facecam 1620:20:280:160 \
    --output clip_01.mp4
```

- Layouts: `gameplay` (center-crop), `facecam-top` (cam top 45%),
  `facecam-bottom`. Output: 1080x1920, 30 fps, H.264 + AAC.
- `--dry-run` prints the FFmpeg command without rendering.

### 5.2 Captions

```bash
# Option A — faster-whisper (needs: pip install faster-whisper)
python3 scripts/caption_whisper.py --input clip_01.mp4 --output clip_01.srt \
    --model tiny --language en --word-level
# Option B — YouTube auto-subtitles + translate
python3 scripts/translate_subtitles.py --prepare clip_01_en.srt
# ... agent translates batches EN->ID ...
python3 scripts/translate_subtitles.py --apply clip_01_en.srt \
    --translations translated.json --output clip_01_id.srt
```

- Caption rules: colloquial Indonesian, short lines, keep game terms in
  English (kill, clutch, NPC, Wasted, drive-by).
- If faster-whisper is missing, the script prints install instructions
  and exits 2 — do NOT pretend it worked. Document it and use Option B.

### 5.3 Burn captions + bilingual file (optional)

```bash
# Burn ID subtitles into the vertical clip:
python3 scripts/vertical_cut.py --input vod.mp4 --start <clip_start> \
    --duration 30 --layout gameplay --srt clip_01_id.srt --output clip_01_cap.mp4
# Or burn with the original helper (needs FFmpeg with libass):
python3 scripts/burn_subtitles.py clip_01.mp4 clip_01_id.srt clip_01_cap.mp4
# Bilingual EN+ID .srt for the record:
python3 scripts/merge_bilingual_subtitles.py clip_01_en.srt clip_01_id.srt \
    clip_01_bilingual.srt
```

### 5.4 Shorts copy

```bash
python3 scripts/generate_summary.py --moment moments.json --index 0 \
    --streamer Lacy --output clip_01_summary.md
```

- Title <=100 chars, hook first, streamer name in it. Description credits
  the streamer + Twitch link. Hashtags: #GTA6 #Shorts + campaign tags.
- If a campaign brief exists, its tags/disclosure override the template.

## Stage 6 — Upload + record

**Goal**: post to YouTube Shorts and keep a record.

1. Upload via YouTube Studio (manual) or YouTube Data API.
   No auto-upload is wired in yet — upload is a manual step for now.
2. If in a paid campaign: submit the Shorts link within the brief's
   deadline (usually ≤30 min after posting) on Content Rewards.
3. Record the clip: streamer, VOD id, clip start/duration, Shorts URL,
   views after 24h. Keep it in the repo's `clips/` log (or tell the user).
4. Ask whether to cut more moments from the same VOD (back to Stage 4).

---

## Key technical notes

### Chat reacts late — always pre-roll 20s
The spike marks when chat *reacted*. The moment happened ~20s earlier.
`twitch_chat_spikes.py` already subtracts the pre-roll; never "fix" it to 0.

### FFmpeg libass (subtitle burning)
Standard FFmpeg builds sometimes lack the `subtitles` filter. Check with
`ffmpeg -filters 2>&1 | grep subtitles`. On macOS use `ffmpeg-full`
(Homebrew); on Ubuntu install `libass-dev`. See references/ffmpeg-guide.md.

### Thin-VM rule
This VM has ~1 GB free RAM and no GPU. Heavy work (multi-GB VOD
downloads, Whisper transcription, vertical renders) belongs on the user's
PC/laptop. On the VM: write/test scripts, run the spike detector on chat
JSON, and dry-run FFmpeg commands only.

### Filenames
Sanitize (see `scripts/utils.py`): strip `/ \ : * ? " < > |`, spaces to
underscores, max 100 chars.

## Error handling

- No chat file / empty chat -> ask for the right file; check the
  TwitchDownloader command from Stage 2.
- No spikes found -> lower `--factor` / `--min-count`; or the VOD's chat
  is unusually quiet (small channel) — say so honestly.
- faster-whisper missing -> print install steps, use Option B captions.
- FFmpeg subtitles filter missing -> guide to ffmpeg-full / libass-dev.
- Upload/API errors -> report the exact error; never re-upload blindly
  (duplicate Shorts hurt the channel).
