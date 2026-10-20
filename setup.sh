#!/usr/bin/env bash
# VS Video Reader: one-command setup for macOS on Apple Silicon.
#
#   ./setup.sh               install tools, local Whisper, the model and the Claude Code skill
#   ./setup.sh --no-skill    skip copying the skill into ~/.claude/skills
#   ./setup.sh --skip-model  don't pre-download the Whisper model (~1.5 GB, fetched on first use instead)
#
# Touches only: Homebrew packages (yt-dlp, ffmpeg, deno if no JS runtime), ~/VS-Video-Read/,
# and ~/.claude/skills/vs-video-read/. Safe to run again.
set -euo pipefail

INSTALL_SKILL=1
FETCH_MODEL=1
for arg in "$@"; do
  case "$arg" in
    --no-skill)   INSTALL_SKILL=0 ;;
    --skip-model) FETCH_MODEL=0 ;;
    -h|--help)    sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="${VS_VIDEO_HOME:-$HOME/VS-Video-Read}"
ENGINE="$HOME_DIR/_engine"
MODEL="mlx-community/whisper-large-v3-turbo"

step() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$1"; }
fail() { printf '    \033[31m✗\033[0m %s\n' "$1" >&2; exit 1; }

step "Checking the system"
[ "$(uname -s)" = "Darwin" ] || fail "setup.sh is for macOS. On Linux/Windows see the README (captions-only mode)."
[ "$(uname -m)" = "arm64" ] || fail "Local Whisper (MLX) needs an Apple Silicon Mac (M1 or newer)."
command -v brew >/dev/null || fail "Homebrew is missing. Install it from https://brew.sh first."
command -v python3 >/dev/null || fail "python3 is missing."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || fail "Python 3.9+ is needed."
ok "macOS on Apple Silicon, Homebrew, $(python3 --version)"

step "Installing yt-dlp and ffmpeg"
for pkg in yt-dlp ffmpeg; do
  if brew list --formula "$pkg" >/dev/null 2>&1; then ok "$pkg already installed"; else brew install "$pkg"; ok "$pkg installed"; fi
done
if command -v node >/dev/null || command -v deno >/dev/null; then
  ok "JS runtime found (YouTube needs one)"
else
  brew install deno; ok "deno installed (YouTube needs a JS runtime)"
fi

step "Creating $HOME_DIR"
mkdir -p "$HOME_DIR/inbox" "$HOME_DIR/library" "$ENGINE/models"
ok "inbox/  library/  _engine/"

step "Installing local Whisper (mlx-whisper) in its own Python environment"
if [ ! -x "$ENGINE/venv/bin/python" ]; then
  python3 -m venv "$ENGINE/venv"
fi
"$ENGINE/venv/bin/pip" install -q --upgrade pip
"$ENGINE/venv/bin/pip" install -q mlx-whisper
"$ENGINE/venv/bin/python" -c "import mlx_whisper" && ok "mlx-whisper ready"

if [ "$FETCH_MODEL" = 1 ]; then
  step "Downloading the Whisper model ($MODEL, ~1.5 GB, one time)"
  HF_HOME="$ENGINE/models" HF_HUB_DISABLE_TELEMETRY=1 "$ENGINE/venv/bin/python" - "$MODEL" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download(sys.argv[1])
PY
  ok "model stored in $ENGINE/models"
fi

if [ "$INSTALL_SKILL" = 1 ]; then
  step "Installing the Claude Code skill"
  DEST="$HOME/.claude/skills/vs-video-read"
  mkdir -p "$HOME/.claude/skills"
  if [ -d "$DEST" ] && ! diff -rq "$HERE/skill/vs-video-read" "$DEST" >/dev/null 2>&1; then
    BACKUP="$DEST.bak-$(date +%Y%m%d-%H%M%S)"
    mv "$DEST" "$BACKUP"
    ok "existing skill backed up to $BACKUP"
  fi
  mkdir -p "$DEST"
  cp -R "$HERE/skill/vs-video-read/." "$DEST/"
  ok "skill installed at $DEST"
fi

step "Done"
cat <<EOF
    Try it:
      python3 "$HERE/skill/vs-video-read/scripts/video_read.py" "https://www.youtube.com/watch?v=<id>"
    Or in Claude Code just say:  read this video <link>   ·   read my inbox
    Your videos, words and verdicts live in: $HOME_DIR
EOF
