#!/usr/bin/env bash
# MyVoiceTranslator - Desktop Integration Installer
# Creates .desktop file and installs it to ~/.local/share/applications/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"

DESKTOP_FILE_NAME="MyVoiceTranslator.desktop"
APPLICATIONS_DIR="${HOME}/.local/share/applications"
ICONS_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
ICON_SOURCE="${PROJECT_ROOT}/assets/myvoice-translator.svg"
DESKTOP_TARGET="${APPLICATIONS_DIR}/${DESKTOP_FILE_NAME}"
ICON_TARGET="${ICONS_DIR}/myvoice-translator.svg"

echo "=== MyVoiceTranslator Desktop Integration Installer ==="
echo "Project root: ${PROJECT_ROOT}"
echo ""

# Create directories
mkdir -p "${APPLICATIONS_DIR}"
mkdir -p "${ICONS_DIR}"

# Copy icon
if [[ -f "${ICON_SOURCE}" ]]; then
    cp "${ICON_SOURCE}" "${ICON_TARGET}"
    echo "✓ Icon installed to ${ICON_TARGET}"
else
    echo "⚠ Warning: Icon source not found at ${ICON_SOURCE}"
fi

# Create .desktop file
cat > "${DESKTOP_TARGET}" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=MyVoiceTranslator
GenericName=Interview Shield
Comment=Real-time STT and translation with Chrome extension support
Exec=${PROJECT_ROOT}/.venv/bin/python ${PROJECT_ROOT}/shield.py
Icon=myvoice-translator
Terminal=true
Categories=AudioVideo;Audio;Utility;
Keywords=transcription;translation;speech;voice;chrome;
StartupNotify=true
EOF

echo "✓ Desktop file created at ${DESKTOP_TARGET}"

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APPLICATIONS_DIR}" 2>/dev/null || true
    echo "✓ Desktop database updated"
fi

# Update icon cache
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
    echo "✓ Icon cache updated"
fi

echo ""
echo "=== Installation Complete ==="
echo "You can now launch MyVoiceTranslator from your application menu."
echo "Or run directly: ${PROJECT_ROOT}/.venv/bin/python ${PROJECT_ROOT}/shield.py"
echo ""
echo "To uninstall, run: rm -f ${DESKTOP_TARGET} ${ICON_TARGET}"