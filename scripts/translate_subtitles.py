#!/usr/bin/env python3
"""
translate_subtitles.py — Batch-translate subtitles EN -> Bahasa Indonesia.

Adapted from op7418/Youtube-clipper-skill (MIT): the original targeted
Chinese (EN->ZH for Xiaohongshu/Douyin). This version targets Bahasa
Indonesia for zeze's Indonesian audience on YouTube Shorts.

Design note (same as the original): the translation itself is done by the
AI agent running the skill, in batches of ~20 subtitle lines at a time
(95% fewer API calls than one-by-one). This script prepares the batches,
merges the agent's translations back, and writes the translated .srt.

Usage (agent-driven):
    1. python3 scripts/translate_subtitles.py --prepare clip_en.srt
       -> prints batches of 20 lines as JSON for the agent to translate.
    2. Agent translates each batch (colloquial Indonesian, keep game terms
       in English: "kill", "clutch", "NPC", "Wasted", "drive-by", ...).
    3. python3 scripts/translate_subtitles.py --apply clip_en.srt \\
           --translations translated.json --output clip_id.srt

Or, in one step inside the skill, the agent can call
translate_subtitles_batch() directly (see below) and fill translations.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import seconds_to_time  # noqa: E402


def parse_srt(path):
    """Parse a simple .srt into [{start, end, text}]."""
    entries = []
    block = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.strip() == "":
                if block:
                    entries.append(block)
                    block = []
            else:
                block.append(line)
    if block:
        entries.append(block)
    out = []
    for block in entries:
        if len(block) < 3:
            continue
        times = block[1].split(" --> ")
        if len(times) != 2:
            continue
        out.append({
            "start": times[0].strip(),
            "end": times[1].strip(),
            "text": " ".join(block[2:]).strip(),
        })
    return out


def srt_time_to_seconds(text):
    hms, ms = text.replace(",", ".").split(".")
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s + int(ms) / 1000.0


def make_batches(subtitles, batch_size=20):
    return [subtitles[i:i + batch_size]
            for i in range(0, len(subtitles), batch_size)]


def write_srt(subtitles, path, field="translation"):
    with open(path, "w", encoding="utf-8") as fh:
        for i, sub in enumerate(subtitles, 1):
            text = sub.get(field) or sub["text"]
            fh.write(f"{i}\n{sub['start']} --> {sub['end']}\n{text}\n\n")


def translate_subtitles_batch(subtitles, batch_size=20,
                              target_lang="Bahasa Indonesia"):
    """Prepare batches for the agent to translate.

    Returns a list of batches; the agent translates each batch's `text`
    into `translation`, then the caller writes the result with write_srt().
    """
    print(f"\nTranslating {len(subtitles)} lines -> {target_lang} "
          f"(batch size {batch_size})")
    print("Rules: colloquial Indonesian, short lines for Shorts, keep game "
          "terms in English (kill, clutch, NPC, Wasted, drive-by).")
    return make_batches(subtitles, batch_size)


def main():
    parser = argparse.ArgumentParser(
        description="Batch-translate subtitles EN -> Bahasa Indonesia.")
    parser.add_argument("--prepare", help="Input .srt: print batches as JSON")
    parser.add_argument("--apply", help="Input .srt to apply translations to")
    parser.add_argument("--translations",
                        help="JSON file: list of translated strings, same "
                             "order as the .srt entries")
    parser.add_argument("--output", help="Output .srt path")
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()

    if args.prepare:
        subs = parse_srt(args.prepare)
        batches = translate_subtitles_batch(subs, args.batch_size)
        print(json.dumps(batches, ensure_ascii=False, indent=2))
        return 0

    if args.apply:
        if not args.translations or not args.output:
            print("--apply needs --translations and --output", file=sys.stderr)
            return 1
        subs = parse_srt(args.apply)
        translated = json.loads(Path(args.translations).read_text(encoding="utf-8"))
        if len(translated) != len(subs):
            print(f"Count mismatch: {len(translated)} translations vs "
                  f"{len(subs)} subtitle entries", file=sys.stderr)
            return 1
        for sub, text in zip(subs, translated):
            sub["translation"] = text
        write_srt(subs, args.output)
        print(f"Wrote {len(subs)} translated lines -> {args.output}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
