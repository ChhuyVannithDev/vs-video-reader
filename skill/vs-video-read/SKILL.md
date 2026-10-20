---
name: vs-video-read
description: Watch a trading video and explain its logic. Works on a link (YouTube, public Facebook videos and Reels, anything yt-dlp opens) or a downloaded video file dropped in ~/VS-Video-Read/inbox/. Local Whisper turns the speech into words on the user's own Mac (audio never leaves it); chart frames are taken on every scene change, at least every 20 s, and paired with the words by time. Claude reads both and writes verdict.md in that video's folder (the strategy written out literally, where the chart disagrees with the speech, strong points to catch, weak points and video tricks, a verdict per trading style) and adds a row to LIBRARY.md. Use when the user drops a video link or file, or says "read this video", "watch this", "read my inbox", "explain the logic in this video", "what is this trader's strategy", "catch the strong points".
---

# VS Video Reader: read a trading video

A trading video's logic lives **on the chart**. A transcript that says "this candle here, we enter here" means nothing
without the picture, so this skill gives Claude both: the words, and the chart frames on screen while they were said.

This skill **studies** a video. It doesn't place trades or change any trading system.

## The folder: `~/VS-Video-Read/` (override with `VS_VIDEO_HOME`)

| Path | What |
|---|---|
| `LIBRARY.md` | one row per video: date · title · source + key · folder · **one-line verdict** |
| `inbox/` | **the user drops downloaded videos here** ("read my inbox" = every file in it) |
| `library/<date>_<name>/` | per video: `source.*` (user's own files only) · `audio.m4a` · `transcript.txt` · `frames/` · `index.md` · `meta.json` · **`verdict.md`** |
| `_engine/` | local Whisper: Python venv + `mlx-community/whisper-large-v3-turbo`. Never touch |

## Step 1: extract

```bash
python3 -I ~/.claude/skills/vs-video-read/scripts/video_read.py "<link | /path/file.mp4>"
# "read my inbox":
for f in ~/VS-Video-Read/inbox/*; do python3 -I ~/.claude/skills/vs-video-read/scripts/video_read.py "$f"; done
```

- **"Already read?" is built in.** It checks `LIBRARY.md` by link id or file sha256 (renamed copies are caught too).
  On `{"already_read": true}`, give the user the verdict on file and stop.
- An inbox file is **moved** into its library folder (inbox = to-do list). A file elsewhere is read in place. A video
  downloaded from a link is deleted after the frames are taken (`--keep-video` keeps it).
- Words: **creator subtitles if the video has them → else local Whisper → else YouTube auto-captions.**
  A `.vtt`/`.srt` beside a local file is used.
- Speed on an M-series Mac: a 6-min video takes ~20–30 s in total.

| Option | Use |
|---|---|
| `--from 720 --to 1500` | only that part (seconds): long videos, or the one setup the user points at |
| `--language th` | force Whisper's spoken language (auto-detect by default) |
| `--transcript whisper\|yt\|none` | force a source |
| `--every 20` / `--scene 0.12` / `--max-frames 60` | frame density |
| `--no-frames` | words only, for a fast "what is this video about" |
| `--force` | read again even if `LIBRARY.md` has it |

## Step 2: read

1. Read `index.md` whole. Each frame carries the words spoken **while it was on screen**.
2. Open the frames at the moments that carry the rule: indicator setup, each timeframe's read, the entry candle, the
   position box (SL/TP), the result. A frame landing on the talking head is normal (scene cut), so open its neighbour.
3. **When the chart and the speech disagree, the chart wins and the gap is reported.** Presenters often say one stop
   size while the position tool on screen shows another.
4. Read the description in `meta.json` (settings, links, the paid course behind it).
5. Name the video tricks: TP moved after the fact, one hand-picked example, no losing trades shown, "95 % accuracy"
   with no sample size.

Non-English video: read it in its own language, write in the user's language.

## Step 3: write `verdict.md` in the video's folder, then update its `LIBRARY.md` row

Follow `templates/verdict-template.md`. Replace the row's `⏳ reading` with the one-line verdict.

1. **Source:** title · channel · date · length · link (or "own file").
2. **One line:** what it is + whether the video actually proves it.
3. **The strategy, literally** (table): indicators · bias timeframes · entry trigger · SL · TP · management · filters.
   Give stops and targets in **price units** (e.g. "$4.67" on gold), not just ticks or pips.
4. **Chart vs speech** gaps.
5. **Strong points to catch:** what is worth taking even if the whole system isn't.
6. **Weak points / video tricks.**
7. **Verdict per trading style:** Swing · Intraday · Scalping. What each style can take, "not measured yet", and the
   test that would measure it. Never a flat "no".
8. **Next step** if the user wants to go further (e.g. backtest the setup on their own data).

Then give the user the short version in chat.

## Cleanup: only when the user asks

`LIBRARY.md` is the permanent history; its rows are never deleted. Never clean on your own.

```bash
C=~/.claude/skills/vs-video-read/scripts/cleanup.py
python3 -I $C --older-than 7      # or --before 2026-11-01, or --month 2026-10  (dry run: lists folders + space)
python3 -I $C --older-than 7 --yes                 # after the user's OK on that list
```

- Default: delete the heavy files (`frames/`, `audio.m4a`, `source.*`) and keep `verdict.md` + the text (~50 KB).
  `--all-files` deletes the whole folder.
- **Always show the dry-run list first.** A line marked ⚠️ `source.*` is the user's own downloaded video: name it and
  get a clear yes.
- Cleaned rows in `LIBRARY.md` are marked `🗑️ cleaned (verdict kept) <date>` or `🗑️ folder deleted <date>`.

## Limits

- **Private / members-only / login-only** videos can't be read from a link; this skill never uses login cookies.
  The user downloads them and drops them in `inbox/`.
- YouTube and public Facebook videos / Reels are tested. X / TikTok public links usually work through yt-dlp.
- A video with no sound gives frames only. On music-only clips Whisper may print a stray "Thank you.": treat it as no speech.
- Local Whisper needs an Apple Silicon Mac (MLX). Elsewhere the tool still works with creator subtitles or YouTube captions.
