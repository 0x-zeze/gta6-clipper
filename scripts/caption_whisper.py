#!/usr/bin/env python3
"""
caption_whisper.py — Transcribe a clip with faster-whisper, word-level
ASS captions out (reference format default).

Default output is a word-level .ass file: one Dialogue per word,
ALL-CAPS, big white bold with black outline, positioned just under the
facecam (top-center of the gameplay panel). That is the reference format
verified on Typical Gamer's Shorts "The Biggest Problem with GTA 6..."
(28s) and reproduced on a Kai Cenat clip (kai-ref2.mp4, 1080x1920).

The .ass style (do not change the numbers):
  PlayResX 1080, PlayResY 1920
  Style: Word, DejaVu Sans, 110, PrimaryColour white, OutlineColour black,
  Bold, BorderStyle 1, Outline 3, Alignment 8 (top-center), MarginV 890.
  Word duration minimum 0.12s.

DO NOT produce big captions via .srt + the FFmpeg subtitles filter: SRT
is converted to ASS with a default PlayRes of 384x288, so FontSize gets
scaled ~6.7x and the letters come out gigantic (proven by a failed first
render). Always burn a real .ass file (PlayRes 1080x1920) with the ass
filter — see scripts/vertical_cut.py --style ref.

PyAV note: faster-whisper calls av.open(..., metadata_errors=...),
which PyAV 19 rejects (TypeError). This script monkey-patches av.open
to drop that kwarg before transcribing. Harmless on older PyAV.

Requires: pip install faster-whisper   (and FFmpeg on PATH)
On this VM use the venv that already has it:
    ~/workspace/whisper-venv/bin/python scripts/caption_whisper.py ...
Model runs on CPU with int8 by default — slow on weak machines.
On this VM (~1 GB free RAM, no GPU) use --model tiny and short clips only;
for real work, run it on a PC/laptop with a GPU or at least 8 GB RAM.

Usage:
    python3 scripts/caption_whisper.py --input clip.mp4 --output clip.ass
    python3 scripts/caption_whisper.py --input clip.mp4 --output clip.srt
    python3 scripts/caption_whisper.py --input clip.mp4 --model base --language en
    python3 scripts/caption_whisper.py --input clip.mp4 --output clip.srt --word-level --max-words 3
"""

import argparse
import sys

# Reference-format .ass header — numbers verified, do not change.
ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,DejaVu Sans,110,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,8,40,40,890,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text

"""

ASS_MIN_WORD_DURATION = 0.12


def _patch_pyav_metadata_errors():
    """Drop the metadata_errors kwarg faster-whisper passes to av.open.

    PyAV 19 removed/never accepted that kwarg, so transcribe() dies with
    TypeError without this patch. Patching the av module attribute works
    because faster-whisper calls av.open through the same module object.
    """
    try:
        import av
    except ImportError:
        return
    orig_open = av.open

    def patched_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return orig_open(*args, **kwargs)

    av.open = patched_open


def fmt_srt_time(seconds):
    ms = int(round(seconds * 1000))
    h, rest = divmod(ms, 3600000)
    m, rest = divmod(rest, 60000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_ass_time(seconds):
    """ASS time: H:MM:SS.cc (centiseconds)."""
    cs = int(round(seconds * 100))
    h, rest = divmod(cs, 360000)
    m, rest = divmod(rest, 6000)
    s, cs = divmod(rest, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_safe(text):
    """Strip ASS override characters from a word (rare, but a stray
    '{' or backslash would corrupt the line)."""
    return text.replace("\\", "").replace("{", "").replace("}", "")


def write_ass(segments, path, min_duration=ASS_MIN_WORD_DURATION):
    """Write word-level segments as a reference-format .ass file.

    One Dialogue per word, uppercased, end clamped to at least
    min_duration after start.
    """
    cues = []
    for seg in segments:
        for w in (getattr(seg, "words", None) or []):
            text = _ass_safe(w.word.strip().upper())
            if not text:
                continue
            end = max(w.end, w.start + min_duration)
            cues.append((w.start, end, text))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ASS_HEADER)
        for start, end, text in cues:
            fh.write(f"Dialogue: 0,{fmt_ass_time(start)},"
                     f"{fmt_ass_time(end)},Word,,0,0,0,,{text}\n")
    return len(cues)


def write_srt(segments, path, word_level, max_words):
    """Write segments (faster-whisper output) as .srt.

    word_level=True: one caption per word group (max_words per cue),
    which is what makes karaoke-style Shorts captions.
    """
    cues = []
    for seg in segments:
        words = getattr(seg, "words", None)
        if word_level and words:
            group = []
            for w in words:
                group.append(w)
                if len(group) >= max_words:
                    cues.append((group[0].start, group[-1].end,
                                 " ".join(x.word.strip() for x in group)))
                    group = []
            if group:
                cues.append((group[0].start, group[-1].end,
                             " ".join(x.word.strip() for x in group)))
        else:
            cues.append((seg.start, seg.end, seg.text.strip()))
    with open(path, "w", encoding="utf-8") as fh:
        for i, (start, end, text) in enumerate(cues, 1):
            if not text:
                continue
            fh.write(f"{i}\n{fmt_srt_time(start)} --> {fmt_srt_time(end)}\n"
                     f"{text}\n\n")
    return len(cues)


def infer_format(output, explicit):
    """Output format: explicit --format wins, else the file extension,
    else 'ass' (the reference format default)."""
    if explicit:
        return explicit
    lower = output.lower()
    if lower.endswith(".ass"):
        return "ass"
    if lower.endswith(".srt"):
        return "srt"
    return "ass"


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe a clip with faster-whisper into word-level "
                    ".ass captions (reference format) or .srt.")
    parser.add_argument("--input", required=True, help="Audio/video file")
    parser.add_argument("--output", required=True,
                        help="Output path (.ass default, .srt also supported)")
    parser.add_argument("--format", default=None, choices=["ass", "srt"],
                        help="Caption format (default: from output extension, "
                             ".ass if unclear)")
    parser.add_argument("--model", default="tiny",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper model (default: tiny — fastest, weakest)")
    parser.add_argument("--language", default="en",
                        help="Spoken language code (default: en)")
    parser.add_argument("--device", default="auto",
                        help="cpu | cuda | auto (default: auto)")
    parser.add_argument("--word-level", action="store_true",
                        help="Emit word-group cues instead of sentence cues "
                             "(srt only; .ass is always one word per cue)")
    parser.add_argument("--max-words", type=int, default=3,
                        help="Words per cue with --word-level (default: 3)")
    args = parser.parse_args()

    fmt = infer_format(args.output, args.format)

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("faster-whisper is NOT installed for this Python.", file=sys.stderr)
        print("Install it with:  pip install faster-whisper", file=sys.stderr)
        print("On this VM use the venv that already has it:", file=sys.stderr)
        print("  ~/workspace/whisper-venv/bin/python "
              "scripts/caption_whisper.py ...", file=sys.stderr)
        print("Then re-run this script. (Needs FFmpeg on PATH too.)",
              file=sys.stderr)
        return 2

    _patch_pyav_metadata_errors()

    device = args.device
    if device == "auto":
        try:
            import torch  # noqa: F401  (only used for a CUDA probe)
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    compute = "float16" if device == "cuda" else "int8"

    print(f"Loading faster-whisper model {args.model} "
          f"(device={device}, compute={compute}) ...")
    model = WhisperModel(args.model, device=device, compute_type=compute)
    need_words = fmt == "ass" or args.word_level
    segments, _info = model.transcribe(
        args.input, language=args.language, word_timestamps=need_words)
    # segments is a generator: materialise it once for the writer.
    segments = list(segments)
    if fmt == "ass":
        count = write_ass(segments, args.output)
        print(f"Wrote {count} word cues -> {args.output}")
    else:
        count = write_srt(segments, args.output, args.word_level,
                          args.max_words)
        print(f"Wrote {count} cues -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
