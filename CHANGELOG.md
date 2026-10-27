# Changelog

All notable changes to VS Video Reader. Dates are the author's local time (GMT+7).

## 1.1 · 2026-10-27

- `examples/`: a real sample run on a public YouTube video (`sample-index.md` + `sample-verdict.md`) so you can see
  the output before installing anything.
- README: "Example output" and "About the author" sections; the chart-vs-speech example now quotes both frames exactly.
- Author lines in the scripts and the skill.

## 1.0 · 2026-10-20

First public release.

- `video_read.py`: link or file → audio, scene-change frames (at least one every 20 s), words from creator subtitles
  → local Whisper (mlx-whisper, large-v3-turbo) → YouTube captions; `index.md` pairs frames and words by time;
  `LIBRARY.md` remembers every link id and file hash so nothing is read twice.
- YouTube: the `live_chat` track is skipped when picking subtitles (it is a chat replay, not captions).
- Facebook: public page videos and Reels tested; private or group posts are never fetched with cookies.
- `cleanup.py`: free space by date (`--older-than`, `--before`, `--month`), dry run first, keeps each verdict and the
  text by default, marks the cleaned rows in `LIBRARY.md`.
- `setup.sh`: one-command install on macOS Apple Silicon; copies the skill into `~/.claude/skills/`.
