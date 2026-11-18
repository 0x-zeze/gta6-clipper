#!/usr/bin/env python3
"""
vertical_cut.py — Cut a 16:9 stream segment into a 9:16 vertical Short.

Layouts (output is always 1080x1920, 30 fps, H.264 + AAC):
  gameplay       Center-crop the game to 9:16. Best for pure gameplay moments.
  facecam-top    Facecam on the top 45%, gameplay on the bottom 55%.
                 Needs --facecam x:y:w:h (region of the webcam in source pixels).
  facecam-bottom Facecam on the bottom 45%, gameplay on top.

Styles:
  default  Layout as above. Optional .srt burn-in via --srt.
  ref      REFERENCE FORMAT (default for GTA VI Shorts, verified):
           facecam-top + orange border around the facecam panel +
           word-by-word BIG captions from a .ass file (see
           scripts/caption_whisper.py). Implies --layout facecam-top.
           Needs --facecam x:y:w:h AND --ass clip.ass.
           Target duration 25-35s; hook = the first spoken words
           (no static title text on top).

Reference format, verified on Typical Gamer's Shorts
"The Biggest Problem with GTA 6..." (28s) and reproduced on a
Kai Cenat clip (kai-ref2.mp4, 1080x1920):
  - Facecam panel top 45% (1080x864), gameplay bottom 55% (1080x1056).
  - Orange border around the facecam panel:
    drawbox x=0 y=0 w=1080 h=864 color 0xFF6B00 thickness 8.
    (Rounded corners + glow in the original are a TODO, not this round.)
  - Captions: one word per event, ALL-CAPS, big white bold with black
    outline, positioned just under the facecam (top-center of the
    gameplay panel). See caption_whisper.py for the exact .ass style.
  - DO NOT burn big captions via the subtitles filter + .srt: SRT is
    converted to ASS with a default PlayRes of 384x288, so FontSize
    gets scaled ~6.7x and the letters come out gigantic (proven by a
    failed first render). Always use a real .ass file (PlayRes
    1080x1920) with the ass filter.

Optional: burn an .srt subtitle file into the video (needs FFmpeg with libass).
See references/ffmpeg-guide.md if the subtitles filter is missing.

Usage:
    python3 scripts/vertical_cut.py --input vod.mp4 --start 01:23:45 --duration 30 \\
        --layout gameplay --output clip_01.mp4
    python3 scripts/vertical_cut.py --input vod.mp4 --start 5025 --duration 45 \\
        --layout facecam-top --facecam 1620:20:280:160 --srt clip_01.srt \\
        --output clip_01.mp4
    python3 scripts/vertical_cut.py --input kai-vod.mp4 --start 5025 --duration 30 \\
        --style ref --facecam 15:520:255:198 --ass kai-words.ass \\
        --output clip_01.mp4
    python3 scripts/vertical_cut.py --input vod.mp4 --start 5025 --duration 30 \\
        --layout gameplay --dry-run

Works with any input FFmpeg reads (Twitch VOD, YouTube download, local file).
Heavy renders belong on a real PC/laptop — this VM has ~1 GB free RAM and no GPU.
"""

import argparse
import shutil
import subprocess
import sys


def parse_time(value):
    """Accept seconds (5025, 5025.5) or HH:MM:SS / MM:SS. Returns float seconds."""
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise argparse.ArgumentTypeError(f"Bad time value: {value!r}")
    total = 0.0
    for n in nums:
        total = total * 60 + n
    return total


def fmt_time(seconds):
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def escape_sub_path(path):
    """Escape a path for the FFmpeg subtitles filter."""
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def build_filter(layout, facecam, srt_path, style="default", ass_path=None):
    """Return the -filter_complex string for the chosen layout/style."""
    if layout == "gameplay":
        vf = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
        return f"[0:v]{vf},fps=30,format=yuv420p[v]"
    if layout not in ("facecam-top", "facecam-bottom"):
        raise ValueError(f"Unknown layout: {layout}")
    if not facecam:
        raise ValueError(f"Layout {layout} needs --facecam x:y:w:h")
    x, y, w, h = facecam
    # Top panel 1080x864 (45%), bottom panel 1080x1056 (55%).
    game = (f"crop=ih*1080/1056:ih:(iw-ih*1080/1056)/2:0,"
            f"scale=1080:1056")
    cam = f"crop={w}:{h}:{x}:{y},scale=1080:864"
    if layout == "facecam-top":
        stack = "[cam][game]vstack"
    else:
        stack = "[game][cam]vstack"
    if style == "ref":
        # Reference format (verified): facecam-top + orange border
        # around the facecam panel + word-by-word .ass captions.
        # The .ass file must be a real .ass (PlayRes 1080x1920) —
        # never the subtitles filter + .srt for these big captions
        # (SRT converts with PlayRes 384x288, fonts scale ~6.7x).
        if layout != "facecam-top":
            raise ValueError("Style 'ref' needs --layout facecam-top")
        if not ass_path:
            raise ValueError("Style 'ref' needs --ass <word-level .ass file>")
        vf = (f"[0:v]split[a][b];[a]{game}[game];[b]{cam}[cam];"
              f"{stack},drawbox=x=0:y=0:w=1080:h=864:color=0xFF6B00:t=8,"
              f"ass='{escape_sub_path(ass_path)}',fps=30,format=yuv420p[v]")
        return vf
    vf = (f"[0:v]split[a][b];[a]{game}[game];[b]{cam}[cam];"
          f"{stack},fps=30,format=yuv420p[v]")
    if srt_path:
        # Subtitles are burned after stacking so they sit over the final frame.
        style = ("FontSize=26,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                 "BorderStyle=1,Outline=2,MarginV=40")
        vf = vf[:-3] + f",subtitles='{escape_sub_path(srt_path)}':force_style='{style}'[v]"
    return vf


def build_filter_gameplay_with_subs(srt_path):
    vf = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,fps=30"
    if srt_path:
        style = ("FontSize=26,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
                 "BorderStyle=1,Outline=2,MarginV=40")
        vf += f",subtitles='{escape_sub_path(srt_path)}':force_style='{style}'"
    return f"[0:v]{vf},format=yuv420p[v]"


def main():
    parser = argparse.ArgumentParser(
        description="Cut a 16:9 stream segment into a 9:16 vertical Short.")
    parser.add_argument("--input", required=True, help="Source video file")
    parser.add_argument("--start", required=True, type=parse_time,
                        help="Clip start (seconds or HH:MM:SS)")
    parser.add_argument("--duration", required=True, type=float,
                        help="Clip duration in seconds (15-60 for Shorts)")
    parser.add_argument("--layout", default="gameplay",
                        choices=["gameplay", "facecam-top", "facecam-bottom"],
                        help="Vertical layout (default: gameplay)")
    parser.add_argument("--style", default="default",
                        choices=["default", "ref"],
                        help="Render style: 'ref' = reference format "
                             "(facecam-top + orange border + .ass captions; "
                             "implies --layout facecam-top, needs --ass)")
    parser.add_argument("--ass", default=None,
                        help="Word-level .ass caption file to burn in "
                             "(required with --style ref)")
    parser.add_argument("--facecam", default=None,
                        help="Facecam region in source pixels: x:y:w:h")
    parser.add_argument("--srt", default=None,
                        help="Optional .srt subtitle file to burn in "
                             "(default style only — never for big captions, "
                             "see module docstring)")
    parser.add_argument("--output", required=True, help="Output .mp4 path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the FFmpeg command and exit")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg binary")
    args = parser.parse_args()

    if shutil.which(args.ffmpeg) is None:
        print(f"FFmpeg not found: {args.ffmpeg}", file=sys.stderr)
        return 1
    if not 5 <= args.duration <= 90:
        print("Warning: Shorts work best at 15-60s; "
              f"got {args.duration}s. Continuing anyway.", file=sys.stderr)
    if args.style == "ref":
        # Reference format implies facecam-top; .ass + facecam are mandatory.
        if args.layout != "facecam-top":
            print("Note: --style ref implies --layout facecam-top.",
                  file=sys.stderr)
            args.layout = "facecam-top"
        if not args.ass:
            print("Style 'ref' needs --ass <word-level .ass file> "
                  "(make one with scripts/caption_whisper.py).",
                  file=sys.stderr)
            return 1
        if not 25 <= args.duration <= 35:
            print("Note: the reference format targets 25-35s clips; "
                  f"got {args.duration}s.", file=sys.stderr)

    facecam = None
    if args.facecam:
        try:
            facecam = tuple(int(v) for v in args.facecam.split(":"))
            assert len(facecam) == 4
        except (ValueError, AssertionError):
            print("--facecam must be x:y:w:h, e.g. 1620:20:280:160",
                  file=sys.stderr)
            return 1

    if args.layout == "gameplay":
        filt = build_filter_gameplay_with_subs(args.srt)
    else:
        try:
            filt = build_filter(args.layout, facecam, args.srt,
                                style=args.style, ass_path=args.ass)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    cmd = [
        args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(args.start), "-i", args.input,
        "-t", str(args.duration),
        "-filter_complex", filt,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        args.output,
    ]

    if args.dry_run:
        print(" ".join(f"'{c}'" if " " in c else c for c in cmd))
        return 0

    print(f"Cutting {fmt_time(args.start)} + {args.duration:.0f}s "
          f"({args.layout}" + (", ref style" if args.style == "ref" else "") +
          f") -> {args.output}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("FFmpeg failed. If the error mentions the subtitles filter, "
              "your FFmpeg lacks libass — see references/ffmpeg-guide.md.",
              file=sys.stderr)
        return result.returncode
    print(f"Done: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
