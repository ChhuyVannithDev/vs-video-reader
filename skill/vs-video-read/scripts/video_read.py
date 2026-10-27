#!/usr/bin/env python3
"""VS Video Reader: turn a trading video into words + chart frames an AI can read.

Author: Chhuy Vannith (VSDev) · https://vincentchhuy.com · https://github.com/ChhuyVannithDev/vs-video-reader · MIT

    python3 video_read.py SOURCE [OUT_DIR] [options]

SOURCE is a video link (YouTube, Facebook, X ... anything yt-dlp opens) or a
video file on your computer (e.g. your own downloads dropped in ~/VS-Video-Read/inbox).

Everything lands in ONE folder (override with the VS_VIDEO_HOME env var):

    ~/VS-Video-Read/
        LIBRARY.md            one row per video read (date, title, source, verdict)
        inbox/                drop downloaded videos here
        library/<date>_<name>/
            source.<ext>      the video (moved here from inbox/; links: deleted after frames unless --keep-video)
            audio.m4a         mono 16 kHz speech track, never leaves the Mac
            transcript.txt    "[mm:ss] text"
            index.md          every frame + the words spoken while it was on screen -> READ FIRST
            frames/           f_0001.jpg ... 1280 px
            meta.json         title, channel, chapters, description, transcript source, sha256
            verdict.md        the AI's write-up (written after reading)
        _engine/              local Whisper (venv + model). Don't touch.

Transcript order (--transcript auto): the creator's own subtitles when the video
has them, else local Whisper (mlx-whisper, large-v3-turbo, runs on the Mac GPU,
audio stays on the Mac). YouTube's auto-captions are only the fallback when
Whisper is unavailable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

HOME_DIR = Path(os.environ.get("VS_VIDEO_HOME", "~/VS-Video-Read")).expanduser()
INBOX = HOME_DIR / "inbox"
LIBRARY = HOME_DIR / "library"
LIBRARY_MD = HOME_DIR / "LIBRARY.md"
ENGINE = HOME_DIR / "_engine"
WHISPER_PY = ENGINE / "venv" / "bin" / "python"
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".flv", ".3gp", ".ts"}
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".flac"}

LIBRARY_HEADER = """# VS Video Read: library

Every video read so far. Newest at the bottom. Each folder in `library/` holds the video's words,
chart frames, audio and the verdict (`verdict.md`).

| Date | Video | Source | Folder | Verdict |
|---|---|---|---|---|
"""


def run(cmd: list[str], timeout: int = 1800, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout, env=env)


def ytdlp_base() -> list[str]:
    base = ["yt-dlp", "--no-playlist", "--quiet", "--no-warnings"]
    if shutil.which("node") and not shutil.which("deno"):
        base += ["--js-runtimes", "node"]
    return base


def fmt(t: float) -> str:
    t = int(t)
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def slug(text: str, n: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text or "video").encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return (text[:n].rstrip("-")) or "video"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ── library ledger ──────────────────────────────────────────────────────────

def already_read(key: str) -> str | None:
    if not key or not LIBRARY_MD.is_file():
        return None
    for line in LIBRARY_MD.read_text(encoding="utf-8").splitlines():
        if line.startswith("| 20") and key in line:
            return line
    return None


def add_library_row(meta: dict, folder: Path) -> None:
    if not LIBRARY_MD.is_file():
        LIBRARY_MD.write_text(LIBRARY_HEADER, encoding="utf-8")
    title = (meta.get("title") or folder.name).replace("|", "/")[:80]
    src = meta.get("url") or ""
    key = meta.get("id") or (meta.get("sha256") or "")[:12]
    source = f"[link]({src}) `{key}`" if src.startswith("http") else f"own file `{key}`"
    row = f"| {date.today()} | {title} | {source} | [{folder.name}](library/{folder.name}/) | ⏳ reading |\n"
    with LIBRARY_MD.open("a", encoding="utf-8") as fh:
        fh.write(row)


# ── subtitles ───────────────────────────────────────────────────────────────

def vtt_time(s: str) -> float:
    parts = [float(p) for p in s.replace(",", ".").split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def clean_vtt(path: Path) -> list[tuple[float, str]]:
    """Parse a .vtt/.srt into (start, text) lines.

    YouTube auto-subs roll: each cue shows the previous line again above the
    new one. A line equal to one of the last two emitted is dropped, which
    leaves each spoken line once.
    """
    out: list[tuple[float, str]] = []
    start = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        m = re.match(r"(\d[\d:.,]+)\s+-->\s+(\d[\d:.,]+)", line)
        if m:
            start = vtt_time(m.group(1))
            continue
        if start is None or not line or line.isdigit() or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        text = re.sub(r"<[^>]+>", "", line)
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text in (x[1] for x in out[-2:]):
            continue
        out.append((start, text))
    return out


def pick_track(meta: dict, lang: str, allow_auto: bool) -> tuple[list[str], str] | None:
    """Choose exactly ONE subtitle track. Asking for several at once (en.*)
    makes YouTube answer HTTP 429 on the timedtext endpoint."""
    # "live_chat" is a past livestream's chat replay (JSON), not subtitles.
    manual = [c for c in (meta.get("_manual") or []) if c != "live_chat"]
    for code in manual:
        if code == lang or code.startswith(lang + "-"):
            return ["--write-subs"], code
    if manual:
        return ["--write-subs"], manual[0]
    if not allow_auto:
        return None
    # The "-orig" auto track is the speech recognised in a spoken audio track;
    # the rest are machine translations. A video with YouTube auto-dubs has
    # one "-orig" per dubbed language (ar-orig, de-DE-orig ...), so match the
    # video's own language first, never just the first in the list.
    auto = meta.get("_auto") or []
    orig = [c for c in auto if c.endswith("-orig")]
    spoken = (meta.get("language") or "").split("-")[0]
    for base in (meta.get("language"), spoken, lang):
        for code in orig:
            if base and (code == f"{base}-orig" or code.split("-")[0] == base):
                return ["--write-auto-subs"], code
    if len(orig) == 1:
        return ["--write-auto-subs"], orig[0]
    for code in (meta.get("language"), lang):
        if code and code in auto:
            return ["--write-auto-subs"], code
    return None


def get_subs(url: str, out: Path, lang: str, meta: dict, allow_auto: bool) -> list[tuple[float, str]]:
    track = pick_track(meta, lang, allow_auto)
    if not track:
        return []
    flags, code = track
    for attempt in range(2):
        p = run(ytdlp_base() + flags + ["--sub-langs", code, "--sub-format", "vtt",
                "--sleep-subtitles", "2", "--skip-download",
                "-o", str(out / "subs.%(ext)s"), "--", url], timeout=180)
        files = sorted(out.glob("subs*.vtt"))
        if files:
            lines = clean_vtt(files[0])
            if lines:
                meta["transcript_source"] = ("creator subtitles" if "--write-subs" in flags
                                             else "YouTube auto-captions") + f" ({code})"
            return lines
        if "429" in p.stderr and attempt == 0:
            time.sleep(15)
            continue
        meta["subtitle_error"] = p.stderr.strip()[:300]
        break
    return []


# ── whisper (local) ─────────────────────────────────────────────────────────

WHISPER_CODE = r"""
import json, sys, mlx_whisper
audio, model, lang, out = sys.argv[1:5]
r = mlx_whisper.transcribe(audio, path_or_hf_repo=model,
                           language=None if lang == "auto" else lang,
                           condition_on_previous_text=False)
json.dump({"language": r.get("language"),
           "segments": [[s["start"], s["text"].strip()] for s in r["segments"]]},
          open(out, "w"), ensure_ascii=False)
"""


def whisper_ready() -> bool:
    return WHISPER_PY.is_file()


def run_whisper(audio: Path, out: Path, lang: str, meta: dict) -> list[tuple[float, str]]:
    env = dict(os.environ, HF_HOME=str(ENGINE / "models"), HF_HUB_DISABLE_TELEMETRY="1")
    # Once the model is on disk, load it offline: nothing leaves the Mac.
    if any((ENGINE / "models").rglob("*.safetensors")) or any((ENGINE / "models").rglob("*.npz")):
        env["HF_HUB_OFFLINE"] = "1"
    res = out / "transcript.whisper.json"
    t0 = time.time()
    p = run([str(WHISPER_PY), "-c", WHISPER_CODE, str(audio), WHISPER_MODEL, lang, str(res)],
            timeout=7200, env=env)
    if p.returncode != 0 or not res.is_file():
        meta["whisper_error"] = p.stderr.strip()[-400:]
        return []
    data = json.loads(res.read_text(encoding="utf-8"))
    meta["transcript_source"] = f"local Whisper large-v3-turbo ({data.get('language')}, {time.time() - t0:.0f}s)"
    meta["spoken_language"] = data.get("language")
    # Whisper loops on music/silence ("thank you thank you ..."): drop a
    # segment identical to the one before it.
    lines: list[tuple[float, str]] = []
    for start, text in data.get("segments", []):
        if text and (not lines or text != lines[-1][1]):
            lines.append((float(start), text))
    return lines


# ── media ───────────────────────────────────────────────────────────────────

def get_meta(url: str) -> dict:
    p = run(ytdlp_base() + ["--dump-json", "--skip-download", "--", url], timeout=120)
    if p.returncode != 0:
        sys.exit(f"yt-dlp could not open the link: {p.stderr.strip()[:400]}")
    info = json.loads(p.stdout)
    return {
        "url": info.get("webpage_url") or url,
        "id": info.get("id"),
        "site": info.get("extractor_key"),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "upload_date": info.get("upload_date"),
        "duration_s": info.get("duration"),
        "language": info.get("language"),
        "chapters": [{"start": fmt(c.get("start_time", 0)), "title": c.get("title")}
                     for c in (info.get("chapters") or [])],
        "description": (info.get("description") or "")[:3000],
        "_manual": sorted((info.get("subtitles") or {}).keys()),
        "_auto": sorted((info.get("automatic_captions") or {}).keys()),
    }


def download_video(url: str, out: Path) -> Path:
    # Video AND audio in one file: frames come from the picture, Whisper from the sound.
    p = run(ytdlp_base() + ["-f", "bv*[height<=720]+ba/b[height<=720]/b",
            "--merge-output-format", "mp4", "-o", str(out / "source.%(ext)s"), "--", url])
    files = [f for f in out.glob("source.*") if f.suffix not in (".part", ".ytdl")]
    if p.returncode != 0 or not files:
        sys.exit(f"yt-dlp video download failed: {p.stderr.strip()[:400]}")
    return files[0]


def has_stream(path: Path, kind: str) -> bool:
    p = run(["ffprobe", "-v", "error", "-select_streams", kind[0], "-show_entries",
             "stream=codec_type", "-of", "csv=p=0", str(path)], timeout=30)
    return kind in p.stdout


def duration(path: Path) -> float:
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)], timeout=30)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def extract_audio(src: Path, out: Path, t_from: float, t_to: float) -> Path | None:
    if not has_stream(src, "audio"):
        return None
    dst = out / "audio.m4a"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if t_from:
        cmd += ["-ss", str(t_from)]
    cmd += ["-i", str(src)]
    if t_to:
        cmd += ["-t", str(t_to - t_from)]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(dst)]
    p = run(cmd)
    return dst if p.returncode == 0 and dst.is_file() else None


def get_frames(video: Path, out: Path, every: float, scene: float, max_frames: int,
               t_from: float, t_to: float) -> list[float]:
    fdir = out / "frames"
    fdir.mkdir(exist_ok=True)
    for old in fdir.glob("f_*.jpg"):
        old.unlink()
    sel = (f"select='isnan(prev_selected_t)+gt(scene\\,{scene})"
           f"+gte(t-prev_selected_t\\,{every})',showinfo,scale=1280:-2")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-y"]
    if t_from:
        cmd += ["-ss", str(t_from)]
    cmd += ["-i", str(video)]
    if t_to:
        cmd += ["-t", str(t_to - t_from)]
    cmd += ["-vf", sel, "-fps_mode", "vfr", "-q:v", "3", str(fdir / "f_%04d.jpg")]
    p = run(cmd)
    times = [float(m) + t_from for m in re.findall(r"pts_time:([\d.]+)", p.stderr)]
    frames = sorted(fdir.glob("f_*.jpg"))
    times = times[: len(frames)]
    if len(frames) > max_frames:
        # Thin evenly, keep first and last, renumber so the index stays simple.
        keep = {round(i * (len(frames) - 1) / (max_frames - 1)) for i in range(max_frames)}
        kept_t = []
        for i, f in enumerate(frames):
            if i in keep:
                kept_t.append(times[i] if i < len(times) else 0.0)
            else:
                f.unlink()
        for n, f in enumerate(sorted(fdir.glob("f_*.jpg")), 1):
            f.rename(fdir / f"k_{n:04d}.jpg")
        for f in sorted(fdir.glob("k_*.jpg")):
            f.rename(fdir / f.name.replace("k_", "f_"))
        times = kept_t
    return times


def write_index(out: Path, meta: dict, lines: list[tuple[float, str]], times: list[float]) -> None:
    md = [f"# {meta.get('title')}", "",
          f"- Channel: {meta.get('channel')} · uploaded {meta.get('upload_date')} · "
          f"length {fmt(meta.get('duration_s') or 0)}",
          f"- Source: {meta.get('url')}",
          f"- Words from: {meta.get('transcript_source') or 'none'} · lines: {len(lines)} · frames: {len(times)}", ""]
    if meta.get("chapters"):
        md += ["## Chapters", ""] + [f"- {c['start']} {c['title']}" for c in meta["chapters"]] + [""]
    if not lines:
        why = meta.get("whisper_error") or meta.get("subtitle_error") or "no speech track / no subtitles"
        md += [f"> ⚠️ No words: {why[:300]}. Frames only.", ""]
    if not times:
        md += ["## Transcript", "", " ".join(l[1] for l in lines), ""]
    else:
        # A frame owns the words spoken while it is on screen: from its own
        # time until the next frame. Words before the first frame go to it.
        md += ["## Frames with what was said while each was on screen", ""]
        li = 0
        for n, t in enumerate(times, 1):
            nxt = times[n] if n < len(times) else float("inf")
            said = []
            while li < len(lines) and lines[li][0] < nxt:
                said.append(lines[li][1])
                li += 1
            md += [f"### [{fmt(t)}] frames/f_{n:04d}.jpg", "", " ".join(said) or "(no speech)", ""]
    (out / "index.md").write_text("\n".join(md), encoding="utf-8")


# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="video link, or a video/audio file on the Mac")
    ap.add_argument("out_dir", nargs="?", help="default: ~/VS-Video-Read/library/<date>_<name>/")
    ap.add_argument("--transcript", choices=["auto", "whisper", "yt", "none"], default="auto",
                    help="auto = creator subs, else local Whisper, else YouTube auto-captions")
    ap.add_argument("--language", default="auto", help="Whisper spoken language (en, th, km, zh ...); auto-detect by default")
    ap.add_argument("--lang", default="en", help="preferred subtitle language when several exist")
    ap.add_argument("--every", type=float, default=20, help="max seconds between frames")
    ap.add_argument("--scene", type=float, default=0.12, help="scene-change threshold (lower = more frames)")
    ap.add_argument("--max-frames", type=int, default=60)
    ap.add_argument("--from", dest="t_from", type=float, default=0, help="start second")
    ap.add_argument("--to", dest="t_to", type=float, default=0, help="end second (0 = end)")
    ap.add_argument("--no-frames", action="store_true", help="words only")
    ap.add_argument("--keep-video", action="store_true", help="keep a downloaded video (files from inbox are always kept)")
    ap.add_argument("--force", action="store_true", help="read again even if LIBRARY.md has it")
    a = ap.parse_args()

    for tool in ("yt-dlp", "ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} missing: brew install {'ffmpeg' if tool == 'ffprobe' else tool}")
    for d in (INBOX, LIBRARY):
        d.mkdir(parents=True, exist_ok=True)

    local = Path(a.source).expanduser()
    is_local = local.is_file()

    # Step 0: already read? (link id, or file content hash)
    if is_local:
        meta = {"url": str(local), "title": local.stem, "channel": "(own file)",
                "sha256": sha256(local)}
        key = meta["sha256"][:12]
    else:
        meta = get_meta(a.source)
        key = meta.get("id") or ""
    hit = already_read(f"`{key}`") if key else None
    if hit and not a.force:
        print(json.dumps({"already_read": True, "row": hit}, ensure_ascii=False))
        return

    out = Path(a.out_dir).expanduser().resolve() if a.out_dir else \
        LIBRARY / f"{date.today()}_{slug(meta.get('title') or 'video')}"
    if out.exists() and not a.out_dir and any(out.iterdir()):
        out = out.with_name(out.name + f"_{key[:6] or int(time.time())}")
    out.mkdir(parents=True, exist_ok=True)

    # The media file
    if is_local:
        if local.resolve().parent == INBOX.resolve():
            # A user drop: move it into its own folder so inbox/ stays a to-do list.
            video = out / f"source{local.suffix.lower()}"
            shutil.move(str(local), video)
            meta["moved_from_inbox"] = local.name
        else:
            video = local
        meta["duration_s"] = duration(video)
    else:
        video = download_video(a.source, out)
    is_video = video.suffix.lower() not in AUDIO_EXT and has_stream(video, "video")

    # Words
    lines: list[tuple[float, str]] = []
    audio = extract_audio(video, out, a.t_from, a.t_to)
    if not is_local and a.transcript in ("auto", "yt"):
        lines = get_subs(a.source, out, a.lang, meta, allow_auto=(a.transcript == "yt"))
    if is_local and not lines:
        for side in (local.with_suffix(".vtt"), local.with_suffix(".srt")):
            if side.is_file():
                lines = clean_vtt(side)
                meta["transcript_source"] = f"subtitle file {side.name}"
                break
    if not lines and a.transcript in ("auto", "whisper") and audio:
        if whisper_ready():
            lines = [(t + a.t_from, x) for t, x in run_whisper(audio, out, a.language, meta)]
        else:
            meta["whisper_error"] = f"local Whisper not installed at {ENGINE}"
    if not lines and not is_local and a.transcript == "auto":
        lines = get_subs(a.source, out, a.lang, meta, allow_auto=True)
    if a.t_from or a.t_to:
        lines = [l for l in lines if l[0] >= a.t_from and (not a.t_to or l[0] <= a.t_to)]
    (out / "transcript.txt").write_text("\n".join(f"[{fmt(t)}] {x}" for t, x in lines), encoding="utf-8")

    # Frames
    times: list[float] = []
    if is_video and not a.no_frames:
        times = get_frames(video, out, a.every, a.scene, a.max_frames, a.t_from, a.t_to)
    if not is_local and not a.keep_video:
        video.unlink(missing_ok=True)

    (out / "meta.json").write_text(json.dumps(
        {k: v for k, v in meta.items() if not k.startswith("_")}, indent=2, ensure_ascii=False))
    write_index(out, meta, lines, times)
    if not a.out_dir:
        add_library_row(meta, out)
    print(json.dumps({"out": str(out), "title": meta.get("title"),
                      "duration": fmt(meta.get("duration_s") or 0),
                      "words_from": meta.get("transcript_source"),
                      "transcript_lines": len(lines), "frames": len(times),
                      "index": str(out / "index.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
