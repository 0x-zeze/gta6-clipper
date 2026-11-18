---
name: gta6-clipper
description: >
  GTA VI stream clipper: turn long Twitch streams into 25-35s vertical
  YouTube Shorts in the verified reference format (facecam-top, orange
  border, big word-by-word captions). Detect viral moments from Twitch
  chat velocity spikes, cut 9:16 vertical clips with FFmpeg, caption with
  faster-whisper (.ass), translate captions EN->ID, and prepare Shorts
  copy. Use when the user wants to clip a GTA VI streamer, find highlights
  in a Twitch VOD, or make Shorts from stream footage. Keywords: gta 6,
  gta vi, clipper, twitch, chat spike, vertical video, youtube shorts,
  9:16, caption.
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
   + layout per clip. **Default layout is `ref`** (reference format:
   facecam-top + orange border + big word-by-word captions, 25-35s);
   legacy layouts `gameplay` / `facecam-top` / `facecam-bottom` still
   exist. `ref` needs the streamer's facecam region in source pixels
   (find it once per streamer, e.g. Kai Cenat 15:520:255:198 in a
   1280x720 source — x:y:w:h).
3. Confirm the plan before cutting. Do not cut all spikes blindly —
   3-10 best moments per VOD is the sweet spot for launch week.

## Stage 5 — Cut vertical + caption

**Goal**: 1080x1920 Shorts with burned captions, EN->ID.

For each chosen candidate:

### 5.1 Vertical cut (reference format = default)

```bash
# Reference format: facecam-top + orange border + .ass captions.
# --start must match the segment the .ass was transcribed from (usually 0).
python3 scripts/vertical_cut.py --input clip.mp4 --start 0 \
    --duration 30 --style ref --facecam 15:520:255:198 --ass clip.ass \
    --output clip_01.mp4
# Legacy layouts (still work):
python3 scripts/vertical_cut.py --input vod.mp4 --start <clip_start> \
    --duration 30 --layout gameplay --output clip_01.mp4
python3 scripts/vertical_cut.py --input vod.mp4 --start <clip_start> \
    --duration 30 --layout facecam-top --facecam 1620:20:280:160 \
    --output clip_01.mp4
```

- Default target: **25-35s** per clip; the hook is the first spoken
  words (no static title text on top). `--style ref` implies
  `--layout facecam-top` and needs `--facecam x:y:w:h` + `--ass`.
- Output: 1080x1920, 30 fps, H.264 + AAC.
- `--dry-run` prints the FFmpeg command without rendering.
- **Timestamp rule:** the .ass must be transcribed from the SAME segment
  file passed to `vertical_cut.py`, with the same `--start`. A .ass made
  from the full VOD has VOD-relative timestamps that do not match the
  `-ss` seek — the captions would not show at all.

### 5.2 Captions (word-by-word .ass = default)

```bash
# Option A — faster-whisper (needs: pip install faster-whisper;
# on this VM use the venv that already has it)
~/workspace/whisper-venv/bin/python scripts/caption_whisper.py \
    --input clip.mp4 --output clip.ass --model tiny --language en
# Option B — YouTube auto-subtitles + translate (no .ass word timings)
python3 scripts/translate_subtitles.py --prepare clip_01_en.srt
# ... agent translates batches EN->ID ...
python3 scripts/translate_subtitles.py --apply clip_01_en.srt \
    --translations translated.json --output clip_01_id.srt
```

- **Default output is .ass, one word per event, ALL-CAPS** (reference
  format: DejaVu Sans 110, white bold, black outline, Alignment 8,
  MarginV 890, min word duration 0.12s). `.srt` output is still
  available (`--output clip.srt`, `--word-level` for word groups).
- **Never burn big captions via the subtitles filter + .srt**: SRT is
  converted to ASS with a default PlayRes of 384x288, so FontSize gets
  scaled ~6.7x and the letters come out gigantic (proven by a failed
  first render). Always use a real .ass file (PlayRes 1080x1920) with
  the `ass` filter — that is what `--style ref` does.
- PyAV 19 note: `caption_whisper.py` monkey-patches `av.open` to drop
  the `metadata_errors` kwarg faster-whisper passes (PyAV 19 rejects
  it). If faster-whisper is missing, the script prints install
  instructions and exits 2 — do NOT pretend it worked. Document it
  and use Option B.
- Caption rules: colloquial Indonesian, short lines, keep game terms in
  English (kill, clutch, NPC, Wasted, drive-by).

### 5.3 Burn captions + bilingual file (optional)

```bash
# Reference format burns the .ass in the SAME vertical_cut call
# (see 5.1) — no separate burn step needed.
# Legacy layouts only: burn ID subtitles into the vertical clip:
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

1. Upload with the `youtube-upload` supporting skill (YouTube Data API v3,
   CLI `yt-upload`, installed at `~/workspace/yt-upload-venv/`):
   dry-run the metadata plan first, show it to the user, then
   `--execute` only after their go-ahead for that video. Uploads land
   **private** — the user publishes in YouTube Studio. If the one-time
   Google Cloud OAuth setup has not been done (`yt-upload status` says
   `needs_auth`), fall back to manual upload in YouTube Studio and tell
   the user the setup is still pending.
2. If in a paid campaign: submit the Shorts link within the brief's
   deadline (usually ≤30 min after posting) on Content Rewards.
3. Record the clip: streamer, VOD id, clip start/duration, Shorts URL,
   views after 24h. Keep it in the repo's `clips/` log (or tell the user).
4. Ask whether to cut more moments from the same VOD (back to Stage 4).

---

## Supporting skills (installed 2026-11-19, ~/workspace/custom-skills/)

These sit next to this skill and sharpen specific stages. They do NOT
replace this pipeline — use the named part only.

- **viral-hooks** (`rediumvex/viral-hooks-skill`, MIT) — 100 hook formulas
  across 10 psychology triggers. Stage 5.4: after the moment is picked,
  pull 3 hook variants from `hooks-database.md` and use the best one for
  the Shorts title + first line of the description. The video hook stays
  the first spoken words (reference format) — this skill writes the
  *packaging* text, it does not change the video.
- **video-to-shorts** (`social-media-skills/video-to-shorts-skill`, MIT) —
  clip rubric (`references/clip-rubric.md`): hard gates + 100-point score
  (hook in first 3s 25, stands alone 20, payoff 20, energy 15,
  specifics 10, last line 10). Stage 4: score spike candidates from the
  transcript and ship 70+, review 55–69, drop the rest. Also
  `references/shorts-specs.md`: caption safe areas, audio -14 LUFS,
  remove pauses over 0.45s. Do NOT swap in its render/post scripts —
  this skill's FFmpeg ref format and permission rules stay. Posting via
  WoopSocial needs a WoopSocial account.
- **tiktok-video-skills** (`iart-ai/tiktok-video-skills`, MIT) —
  `skills/short-form-video/SKILL.md`: retention grammar (hook → setup →
  body → payoff/loop), one pattern interrupt every 2–4s (cheapest:
  punch-in zoom 1.0→1.12 on the beat), 9:16 safe area (center 900×1400,
  bottom 320px clear, top 120px, right 120px), loop techniques.
  `skills/caption-animation/SKILL.md`: word-by-word timing + karaoke
  highlight. Its delivery is Remotion-based — take the grammar, not the
  renderer; this pipeline stays FFmpeg.
- **youtube-upload** (`grapeot/youtube-upload-skill`, MIT) — Stage 6:
  official YouTube Data API v3 upload, private by default, dry-run
  first, never publishes/schedules/deletes. CLI `yt-upload` (venv
  `~/workspace/yt-upload-venv/`). Needs one-time setup by the user:
  Google Cloud project + Desktop OAuth client + `yt-upload auth`.
  Quota ~550 units per upload with thumbnail + caption track.

---

## Key technical notes

### Reference format (default) — verified numbers, do not change
From Typical Gamer's Shorts "The Biggest Problem with GTA 6…" (28s),
reproduced on a Kai Cenat clip (kai-ref2.mp4, 1080x1920):
- Facecam panel top 45% (1080x864), gameplay bottom 55% (1080x1056).
- Orange border: `drawbox x=0 y=0 w=1080 h=864 color 0xFF6B00 thickness 8`.
- Captions: 1 word per event, ALL-CAPS, DejaVu Sans 110, white bold,
  black outline, BorderStyle 1, Outline 3, Alignment 8, MarginV 890,
  min word duration 0.12s, PlayRes 1080x1920.
- Duration 25-35s; hook = first spoken words.
- **TODO (not this round):** rounded corners + glow on the facecam
  panel (the original has them; `drawbox` is square).
- Facecam crop is per-streamer (Kai Cenat 1280x720 source:
  `15:520:255:198` as x:y:w:h). Find it once per streamer and reuse.

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
