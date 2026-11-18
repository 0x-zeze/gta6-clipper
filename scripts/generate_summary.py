#!/usr/bin/env python3
"""
generate_summary.py — Generate YouTube Shorts titles, descriptions & hashtags.

Adapted from op7418/Youtube-clipper-skill (MIT): the original generated
copy for Xiaohongshu / Douyin / WeChat. This version generates copy for
YouTube Shorts (EN + ID), which is what zeze posts.

The copy itself is written by the AI agent running the skill; this script
prints the moment's info as JSON and the copy rules, then saves the agent's
output as a Markdown file next to the clip.

Usage:
    python3 scripts/generate_summary.py --moment moments.json --index 0
    python3 scripts/generate_summary.py --title "Lacy's $12.5K clutch" \\
        --streamer Lacy --game "GTA VI" --output clip_01_summary.md

Rules the agent follows when writing the copy:
  - Title: <= 100 chars, hook first ("He did WHAT in GTA 6?!"), streamer name in it.
  - Description: 1-2 lines, credit the streamer + link to their Twitch,
    #GTA6 #GTAIV #Shorts.
  - Hashtags: 3-5, always include #GTA6 and #Shorts.
  - If the clip is for a paid campaign (Content Rewards / Reach): follow the
    campaign brief exactly (required tags, disclosure, account rules) — the
    brief overrides everything here.
  - Never claim the footage is yours. Always credit the streamer.
"""

import argparse
import json
import sys
from pathlib import Path


SHORTS_TEMPLATE = """# {title}

Streamer: {streamer} — {streamer_url}
Game: {game}
Moment: {moment_hms} ({duration:.0f}s)

## Title (YouTube Shorts, <=100 chars)
{title}

## Description
{description}

Credit: {streamer} on Twitch — {streamer_url}
#GTA6 #GTAIV #Shorts {extra_tags}

## Checklist before posting
- [ ] Streamer allows clipping (campaign rules or explicit permission — see streamers.md)
- [ ] Campaign brief followed (if any): tags, disclosure, account rules
- [ ] Clip is 15-60s, 1080x1920, captions burned in
- [ ] No licensed music that Content ID will claim
"""


def build_summary(moment, streamer, game="GTA VI"):
    title = moment.get("title") or f"{streamer} — GTA VI moment"
    description = moment.get("description") or (
        f"{streamer} playing GTA VI — watch the full stream on Twitch.")
    return SHORTS_TEMPLATE.format(
        title=title,
        streamer=streamer,
        streamer_url=f"https://www.twitch.tv/{streamer.lower()}",
        game=game,
        moment_hms=moment.get("clip_start_hms", "?"),
        duration=moment.get("duration", 0),
        description=description,
        extra_tags=moment.get("extra_tags", "#GTA6Clips"),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate YouTube Shorts copy for a clip.")
    parser.add_argument("--moment", help="moments JSON from twitch_chat_spikes.py")
    parser.add_argument("--index", type=int, default=0,
                        help="Which candidate in the JSON (default: 0)")
    parser.add_argument("--title", help="Shorts title (overrides JSON)")
    parser.add_argument("--streamer", required=True, help="Streamer channel name")
    parser.add_argument("--game", default="GTA VI")
    parser.add_argument("--output", help="Output .md path")
    args = parser.parse_args()

    moment = {}
    if args.moment:
        data = json.loads(Path(args.moment).read_text(encoding="utf-8"))
        candidates = data.get("candidates", [])
        if not candidates:
            print("No candidates in moments JSON.", file=sys.stderr)
            return 1
        moment = candidates[min(args.index, len(candidates) - 1)]
    if args.title:
        moment["title"] = args.title
    moment.setdefault("title", f"{args.streamer} — GTA VI moment")
    moment.setdefault("description",
                      f"{args.streamer} playing GTA VI — full stream on Twitch.")

    text = build_summary(moment, args.streamer, args.game)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote -> {args.output}")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
