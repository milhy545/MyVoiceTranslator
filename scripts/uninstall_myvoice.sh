#!/usr/bin/env bash
set -euo pipefail

INSTALL_BIN_DIR="${INSTALL_BIN_DIR:-$HOME/.local/bin}"
INSTALL_APP_DIR="${INSTALL_APP_DIR:-$HOME/.local/share/applications}"
INSTALL_ICON_DIR="${INSTALL_ICON_DIR:-$HOME/.local/share/icons/hicolor/scalable/apps}"
APP_ID="myvoice-translator"

rm -f "$INSTALL_BIN_DIR/myvoice"
rm -f "$INSTALL_APP_DIR/$APP_ID.desktop"
rm -f "$INSTALL_ICON_DIR/$APP_ID.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$INSTALL_APP_DIR" >/dev/null 2>&1 || true
fi

cat <<EOF
Removed My Voice Translator launcher artifacts from:
  $INSTALL_BIN_DIR/myvoice
  $INSTALL_APP_DIR/$APP_ID.desktop
  $INSTALL_ICON_DIR/$APP_ID.svg
EOF
