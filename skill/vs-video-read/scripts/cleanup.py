#!/usr/bin/env python3
"""VS Video Reader cleanup: free space in ~/VS-Video-Read by date. Nothing is ever deleted automatically.

    python3 cleanup.py --older-than 7            # folders read more than 7 days ago
    python3 cleanup.py --before 2026-11-01       # folders read before that date
    python3 cleanup.py --month 2026-10           # folders read in that month
    ... [--all-files] [--yes]

Without --yes it only LISTS what would go and how much space it frees (dry run).
Check that list, then run again with --yes.

Default: delete the heavy files (frames/, audio.m4a, source.*, subs*), keep the
small text history (verdict.md, transcript.txt, index.md, meta.json).
--all-files: delete the whole folder.
Either way the LIBRARY.md row stays (it is the permanent history) and gets a
"🗑️ cleaned <date>" mark. A folder's date is the YYYY-MM-DD its name starts with.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

HOME_DIR = Path(os.environ.get("VS_VIDEO_HOME", "~/VS-Video-Read")).expanduser()
LIBRARY = HOME_DIR / "library"
LIBRARY_MD = HOME_DIR / "LIBRARY.md"
HEAVY = ("frames", "audio.m4a")
HEAVY_PREFIX = ("source.", "subs")


def size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def heavy_parts(folder: Path) -> list[Path]:
    return [p for p in folder.iterdir()
            if p.name in HEAVY or p.name.startswith(HEAVY_PREFIX)]


def mark_row(folder: str, whole: bool) -> None:
    if not LIBRARY_MD.is_file():
        return
    tag = f" · 🗑️ {'folder deleted' if whole else 'cleaned (verdict kept)'} {date.today()}"
    out = []
    for line in LIBRARY_MD.read_text(encoding="utf-8").splitlines():
        if line.startswith("| 20") and f"library/{folder}/" in line and "🗑️" not in line:
            if whole:
                line = line.replace(f"[{folder}](library/{folder}/)", f"~~{folder}~~")
            line = line.rstrip().rstrip("|").rstrip() + tag + " |"
        out.append(line)
    LIBRARY_MD.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--older-than", type=int, metavar="DAYS")
    g.add_argument("--before", metavar="YYYY-MM-DD")
    g.add_argument("--month", metavar="YYYY-MM")
    ap.add_argument("--all-files", action="store_true", help="delete the whole folder, not just the heavy files")
    ap.add_argument("--yes", action="store_true", help="really delete (default is a dry run)")
    a = ap.parse_args()

    def chosen(d: date) -> bool:
        if a.older_than is not None:
            return d < date.today() - timedelta(days=a.older_than)
        if a.before:
            return d < date.fromisoformat(a.before)
        return d.strftime("%Y-%m") == a.month

    rows, total = [], 0
    for folder in sorted(LIBRARY.glob("20*")):
        m = re.match(r"(\d{4}-\d{2}-\d{2})_", folder.name)
        if not folder.is_dir() or not m or not chosen(date.fromisoformat(m.group(1))):
            continue
        parts = [folder] if a.all_files else heavy_parts(folder)
        if not parts:
            continue
        freed = sum(size(p) for p in parts)
        own = any(p.name.startswith("source.") for p in folder.iterdir())
        rows.append((folder, parts, freed, own))
        total += freed

    if not rows:
        print("Nothing to clean for that date range.")
        return
    mode = "whole folders" if a.all_files else "heavy files (verdict + text kept)"
    print(f"{'DELETING' if a.yes else 'DRY RUN, nothing deleted'}: {mode}\n")
    for folder, parts, freed, own in rows:
        note = "  ⚠️ includes YOUR OWN video file (source.*)" if own else ""
        print(f"  {folder.name:<70} {human(freed):>9}{note}")
    print(f"\n  {len(rows)} folder(s), frees {human(total)}")

    if not a.yes:
        print("\nRun again with --yes to delete.")
        return
    for folder, parts, _, _ in rows:
        for p in parts:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        mark_row(folder.name, a.all_files)
    print("\nDone. LIBRARY.md rows kept and marked 🗑️.")


if __name__ == "__main__":
    main()
