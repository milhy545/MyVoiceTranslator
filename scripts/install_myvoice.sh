#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
PYTHON_BIN="${PYTHON_BIN:-3.11}"
INSTALL_BIN_DIR="${INSTALL_BIN_DIR:-$HOME/.local/bin}"
INSTALL_APP_DIR="${INSTALL_APP_DIR:-$HOME/.local/share/applications}"
INSTALL_ICON_DIR="${INSTALL_ICON_DIR:-$HOME/.local/share/icons/hicolor/scalable/apps}"
APP_ID="myvoice-translator"
APP_NAME="My Voice Translator"
VENV_DIR="$ROOT_DIR/.venv"
WRAPPER_PATH="$INSTALL_BIN_DIR/myvoice"
DESKTOP_PATH="$INSTALL_APP_DIR/$APP_ID.desktop"
ICON_SOURCE="$ROOT_DIR/assets/myvoice-translator.svg"
ICON_TARGET="$INSTALL_ICON_DIR/$APP_ID.svg"

ensure_uv() {
  if [[ -x "$UV_BIN" ]]; then
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
    return 0
  fi

  echo "uv was not found. Install uv first, for example:" >&2
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
}

install_python_env() {
  export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
  mkdir -p "$UV_CACHE_DIR"
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$UV_BIN" venv --python "$PYTHON_BIN" "$VENV_DIR"
  fi
  "$UV_BIN" pip install --python "$VENV_DIR/bin/python" -e "$ROOT_DIR"
}

write_wrapper() {
  mkdir -p "$INSTALL_BIN_DIR"
  cat >"$WRAPPER_PATH" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$ROOT_DIR"
VENV_PYTHON="\$ROOT_DIR/.venv/bin/python"
if [[ ! -x "\$VENV_PYTHON" ]]; then
  echo "My Voice Translator is not bootstrapped in \$ROOT_DIR/.venv" >&2
  echo "Run: $ROOT_DIR/scripts/install_myvoice.sh" >&2
  exit 1
fi
exec "\$VENV_PYTHON" "\$ROOT_DIR/shield.py" "\$@"
EOF
  chmod +x "$WRAPPER_PATH"
}

write_desktop_entry() {
  mkdir -p "$INSTALL_APP_DIR" "$INSTALL_ICON_DIR"
  install -m 0644 "$ICON_SOURCE" "$ICON_TARGET"
  cat >"$DESKTOP_PATH" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$APP_NAME
Comment=Real-time STT and EN to CS translation TUI
Exec=$WRAPPER_PATH run
Icon=$APP_ID
Terminal=true
Categories=AudioVideo;Utility;
Keywords=voice;translator;stt;interview;transcription;
StartupNotify=true
EOF
}

refresh_desktop_metadata() {
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$INSTALL_APP_DIR" >/dev/null 2>&1 || true
  fi
}

print_summary() {
  cat <<EOF
Installed $APP_NAME

CLI:
  $WRAPPER_PATH

Desktop entry:
  $DESKTOP_PATH

Icon:
  $ICON_TARGET

Run from terminal:
  myvoice doctor
  myvoice run

If '$INSTALL_BIN_DIR' is not on PATH yet, add this to your shell profile:
  export PATH="$INSTALL_BIN_DIR:\$PATH"
EOF
}

main() {
  ensure_uv
  install_python_env
  write_wrapper
  write_desktop_entry
  refresh_desktop_metadata
  print_summary
}

main "$@"
