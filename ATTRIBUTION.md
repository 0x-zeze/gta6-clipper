# Attribution

This project is adapted from **op7418/Youtube-clipper-skill**
(https://github.com/op7418/Youtube-clipper-skill), licensed under the
**MIT License** (see LICENSE — the original license text is kept intact).

## What was kept from the original

- `scripts/download_video.py` — yt-dlp YouTube download
- `scripts/clip_video.py` — precise FFmpeg clipping
- `scripts/extract_subtitle_clip.py` — subtitle segment extraction
- `scripts/analyze_subtitles.py` — AI semantic chapter analysis
- `scripts/burn_subtitles.py` — subtitle burning (FFmpeg + libass)
- `scripts/merge_bilingual_subtitles.py` — bilingual SRT merge
- `scripts/utils.py` — time/filename helpers
- `references/ffmpeg-guide.md`, `references/yt-dlp-guide.md`,
  `references/subtitle-formatting.md`

## What was changed

- `scripts/translate_subtitles.py` — retargeted EN->ZH to **EN->Bahasa
  Indonesia** (new CLI: --prepare / --apply), English docs.
- `scripts/generate_summary.py` — Xiaohongshu/Douyin/WeChat copy replaced
  with **YouTube Shorts titles, descriptions & hashtags (EN+ID)**.

## What is new (written for this project)

- `scripts/twitch_chat_spikes.py` — viral-moment detection from Twitch
  chat velocity spikes (TwitchDownloader chat JSON in, ranked candidates out).
- `scripts/vertical_cut.py` — 9:16 vertical cutting (gameplay / facecam-top /
  facecam-bottom), optional subtitle burn.
- `scripts/caption_whisper.py` — faster-whisper transcription to word-level SRT.
- `SKILL.md` — 6-stage GTA VI clipper workflow (permission -> VOD+chat ->
  spike detection -> review -> vertical cut + caption -> upload).
- `README.md`, `streamers.md`, `references/twitch-guide.md`, `.env.example`.
