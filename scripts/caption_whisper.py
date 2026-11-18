#!/usr/bin/env python3
"""
caption_whisper.py — Transcribe a clip with faster-whisper, word-level SRT out.

Produces an .srt with word-level timestamps so captions can be burned
word-by-word (karaoke style) by burn_subtitles.py / vertical_cut.py.

Requires: pip install faster-whisper   (and FFmpeg on PATH)
Model runs on CPU with int8 by default — slow on weak machines.
On this VM (~1 GB free RAM, no GPU) use --model tiny and short clips only;
for real work, run it on a PC/laptop with a GPU or at least 8 GB RAM.

Usage:
    python3 scripts/caption_whisper.py --input clip.mp4 --output clip.srt
    python3 scripts/caption_whisper.py --input clip.mp4 --model base --language en
    python3 scripts/caption_whisper.py --input clip.mp4 --word-level --max-words 3
"""

import argparse
import sys


def fmt_srt_time(seconds):
    ms = int(round(seconds * 1000))
    h, rest = divmod(ms, 3600000)
    m, rest = divmod(rest, 60000)
    s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


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


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe a clip with faster-whisper into .srt captions.")
    parser.add_argument("--input", required=True, help="Audio/video file")
    parser.add_argument("--output", required=True, help="Output .srt path")
    parser.add_argument("--model", default="tiny",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper model (default: tiny — fastest, weakest)")
    parser.add_argument("--language", default="en",
                        help="Spoken language code (default: en)")
    parser.add_argument("--device", default="auto",
                        help="cpu | cuda | auto (default: auto)")
    parser.add_argument("--word-level", action="store_true",
                        help="Emit word-group cues instead of sentence cues")
    parser.add_argument("--max-words", type=int, default=3,
                        help="Words per cue with --word-level (default: 3)")
    args = parser.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("faster-whisper is NOT installed on this machine.", file=sys.stderr)
        print("Install it with:  pip install faster-whisper", file=sys.stderr)
        print("Then re-run this script. (Needs FFmpeg on PATH too.)",
              file=sys.stderr)
        return 2

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
    segments, _info = model.transcribe(
        args.input, language=args.language, word_timestamps=args.word_level)
    # segments is a generator: materialise it once for the SRT writer.
    segments = list(segments)
    count = write_srt(segments, args.output, args.word_level, args.max_words)
    print(f"Wrote {count} cues -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
