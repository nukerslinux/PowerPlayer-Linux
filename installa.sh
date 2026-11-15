
#!/usr/bin/env bash
set -e

APP_NAME="PowerPlayer Linux"
APP_FILE="PowerPlayer-Linux-1.0-x86_64.AppImage"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_DIR="$HOME/.local/opt/PowerPlayer"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "Installazione di $APP_NAME..."

if [ ! -f "$SCRIPT_DIR/$APP_FILE" ]; then
    echo "ERRORE: AppImage non trovata."
    echo "Metti $APP_FILE nella stessa cartella di installa.sh"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/powerplayer.png" ]; then
    echo "ERRORE: icona powerplayer.png non trovata."
    exit 1
fi

mkdir -p "$APP_DIR" "$ICON_DIR" "$DESKTOP_DIR"

cp "$SCRIPT_DIR/$APP_FILE" "$APP_DIR/"
chmod +x "$APP_DIR/$APP_FILE"

cp "$SCRIPT_DIR/powerplayer.png" "$ICON_DIR/powerplayer.png"

cat > "$DESKTOP_DIR/powerplayer.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=PowerPlayer Linux
Comment=Lettore multimediale per Linux
Exec=$APP_DIR/$APP_FILE
Icon=powerplayer
Terminal=false
Categories=AudioVideo;Video;Player;
StartupNotify=true
EOF

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi

echo ""
echo "Installazione completata!"
echo "PowerPlayer Linux è disponibile nel menu delle applicazioni."
