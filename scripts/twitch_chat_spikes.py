#!/usr/bin/env python3
"""
twitch_chat_spikes.py — Detect viral moments in a Twitch stream from chat velocity.

Why chat, not pixels: when something crazy happens on stream, chat explodes
a few seconds AFTER the moment. So a spike in messages-per-10-seconds marks
the moment, and the clip must start ~20 seconds BEFORE the spike.

Input:  chat JSON exported by TwitchDownloader
        (TwitchDownloaderCLI.exe chatdownload --id <vod_id> -o chat.json -E)
        Format: {"video": {"start": "...", "end": "..."},
                 "comments": [{"created_at": "...",
                               "content_offset_seconds": 123.4,
                               "message": {"body": "..."}}]}
        `content_offset_seconds` is used when present, otherwise the offset is
        derived from `created_at` minus the video start (or first comment).

Output: JSON list of candidate moments + a human-readable table on stdout.
        Each candidate: {peak_time, clip_start, clip_end, duration,
                        peak_msgs_per_10s, baseline, spike_factor}

Usage:
    python3 scripts/twitch_chat_spikes.py --chat chat.json
    python3 scripts/twitch_chat_spikes.py --chat chat.json --output moments.json
    python3 scripts/twitch_chat_spikes.py --chat chat.json.gz --factor 2.5 --min-count 30

Typical GTA VI launch numbers: a big channel easily does 50-200 msgs/10s at
baseline and 3-10x that on a spike. Tune --factor / --min-count per channel.
"""

import argparse
import gzip
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_time(value):
    """Parse an ISO-8601 timestamp into epoch seconds (float)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def load_comments(path):
    """Load TwitchDownloader chat JSON (plain or .gz). Returns (comments, video_start)."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, dict):
        comments = data.get("comments") or data.get("messages") or []
        video = data.get("video") or {}
        video_start = parse_time(video.get("start"))
    elif isinstance(data, list):
        comments = data
        video_start = None
    else:
        comments = []
        video_start = None
    return comments, video_start


def comment_offset(comment, video_start, first_seen):
    """Seconds from video start for one comment."""
    offset = comment.get("content_offset_seconds")
    if offset is not None:
        try:
            return float(offset)
        except (TypeError, ValueError):
            pass
    created = parse_time(comment.get("created_at"))
    if created is None:
        return None
    anchor = video_start if video_start is not None else first_seen
    if anchor is None:
        return None
    return created - anchor


def bucket_counts(offsets, window):
    """Count messages per `window`-second bucket. Returns (buckets, max_offset)."""
    if not offsets:
        return {}, 0.0
    max_offset = max(offsets)
    buckets = {}
    for off in offsets:
        idx = int(off // window)
        buckets[idx] = buckets.get(idx, 0) + 1
    return buckets, max_offset


def detect_spikes(buckets, max_offset, window, baseline_minutes, factor,
                  min_count, min_delta):
    """Flag buckets whose count spikes above a rolling median baseline.

    Baseline = median of the previous `baseline_minutes` of buckets.
    A bucket is a spike when:
        count >= factor * baseline  AND  count >= baseline + min_delta
        AND count >= min_count
    Returns list of (bucket_index, count, baseline).
    """
    baseline_buckets = max(1, int(baseline_minutes * 60 // window))
    total_buckets = int(max_offset // window) + 1
    spikes = []
    for idx in range(total_buckets):
        count = buckets.get(idx, 0)
        if count < min_count:
            continue
        history = [buckets.get(j, 0)
                   for j in range(max(0, idx - baseline_buckets), idx)]
        if not history:
            continue
        baseline = statistics.median(history)
        if baseline <= 0:
            baseline = 1.0
        if count >= factor * baseline and count >= baseline + min_delta:
            spikes.append((idx, count, baseline))
    return spikes


def merge_spikes(spikes, window, pre_roll, min_duration, max_duration):
    """Merge adjacent spike buckets into candidate moments.

    clip_start = peak_time - pre_roll (chat reacts late, so start early).
    Duration is clamped to [min_duration, max_duration]; long regions are
    cut to a max_duration window centred on the peak.
    """
    if not spikes:
        return []
    # Group buckets that touch each other (gap of at most 1 bucket).
    groups = [[spikes[0]]]
    for spike in spikes[1:]:
        if spike[0] - groups[-1][-1][0] <= 2:
            groups[-1].append(spike)
        else:
            groups.append([spike])

    candidates = []
    for group in groups:
        peak_idx, peak_count, peak_base = max(group, key=lambda s: s[1])
        peak_time = peak_idx * window + window / 2.0
        region_start = group[0][0] * window
        region_end = (group[-1][0] + 1) * window
        region_len = region_end - region_start

        clip_start = max(0.0, peak_time - pre_roll)
        if region_len <= max_duration:
            clip_end = clip_start + max(min_duration, region_len)
        else:
            # Long hype region: keep a max_duration window around the peak.
            clip_end = clip_start + max_duration
        duration = clip_end - clip_start
        candidates.append({
            "peak_time": round(peak_time, 1),
            "peak_time_hms": fmt_hms(peak_time),
            "clip_start": round(clip_start, 1),
            "clip_start_hms": fmt_hms(clip_start),
            "clip_end": round(clip_end, 1),
            "clip_end_hms": fmt_hms(clip_end),
            "duration": round(duration, 1),
            "peak_msgs_per_10s": peak_count,
            "baseline_msgs_per_10s": round(peak_base, 1),
            "spike_factor": round(peak_count / max(peak_base, 1.0), 2),
        })
    # Strongest spikes first.
    candidates.sort(key=lambda c: c["spike_factor"], reverse=True)
    return candidates


def fmt_hms(seconds):
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(
        description="Detect viral moments in a Twitch VOD from chat velocity spikes.")
    parser.add_argument("--chat", required=True,
                        help="Chat JSON from TwitchDownloader (or .json.gz)")
    parser.add_argument("--output", default=None,
                        help="Output JSON path (default: <chat>_spikes.json)")
    parser.add_argument("--window", type=float, default=10.0,
                        help="Bucket size in seconds (default: 10)")
    parser.add_argument("--baseline-minutes", type=float, default=5.0,
                        help="Rolling baseline window in minutes (default: 5)")
    parser.add_argument("--factor", type=float, default=3.0,
                        help="Spike = count >= factor * baseline (default: 3.0)")
    parser.add_argument("--min-count", type=int, default=20,
                        help="Minimum messages per bucket to count (default: 20)")
    parser.add_argument("--min-delta", type=int, default=15,
                        help="Spike must exceed baseline by at least this many (default: 15)")
    parser.add_argument("--pre-roll", type=float, default=20.0,
                        help="Seconds before the peak to start the clip (default: 20)")
    parser.add_argument("--min-duration", type=float, default=15.0,
                        help="Minimum clip duration in seconds (default: 15)")
    parser.add_argument("--max-duration", type=float, default=60.0,
                        help="Maximum clip duration in seconds (default: 60)")
    args = parser.parse_args()

    comments, video_start = load_comments(args.chat)
    if not comments:
        print("No comments found in chat file.", file=sys.stderr)
        return 1

    # Anchor for created_at-derived offsets: first comment time.
    first_seen = None
    for c in comments:
        t = parse_time(c.get("created_at"))
        if t is not None:
            first_seen = t if first_seen is None else min(first_seen, t)

    offsets = []
    for c in comments:
        off = comment_offset(c, video_start, first_seen)
        if off is not None and off >= 0:
            offsets.append(off)

    if not offsets:
        print("Could not derive any message offsets (need content_offset_seconds "
              "or created_at timestamps).", file=sys.stderr)
        return 1

    buckets, max_offset = bucket_counts(offsets, args.window)
    spikes = detect_spikes(buckets, max_offset, args.window,
                           args.baseline_minutes, args.factor,
                           args.min_count, args.min_delta)
    candidates = merge_spikes(spikes, args.window, args.pre_roll,
                              args.min_duration, args.max_duration)

    out_path = args.output or str(Path(args.chat).with_suffix("")) + "_spikes.json"
    if out_path.endswith(".gz"):
        out_path = out_path[:-3]
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"chat": str(args.chat),
                   "total_messages": len(offsets),
                   "duration_seconds": round(max_offset, 1),
                   "candidates": candidates}, fh, indent=2, ensure_ascii=False)

    print(f"\nChat: {args.chat}")
    print(f"Messages: {len(offsets)} | VOD length: {fmt_hms(max_offset)} "
          f"| Spike buckets: {len(spikes)} | Candidates: {len(candidates)}")
    print(f"Output: {out_path}\n")
    print(f"{'#':>3}  {'CLIP START':>10}  {'DUR':>5}  {'PEAK/10s':>8}  "
          f"{'BASE':>5}  {'xBASE':>5}")
    for i, c in enumerate(candidates, 1):
        print(f"{i:>3}  {c['clip_start_hms']:>10}  {c['duration']:>4.0f}s  "
              f"{c['peak_msgs_per_10s']:>8}  {c['baseline_msgs_per_10s']:>5}  "
              f"{c['spike_factor']:>5.1f}x")
    if not candidates:
        print("No spikes found — try lowering --factor or --min-count.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
