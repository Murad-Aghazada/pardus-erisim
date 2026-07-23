#!/bin/sh
# Pardus/Linux: uygulamayı menüye ve masaüstüne ekler (paket kurulumu gerekmez).
set -e
DIR="$(dirname "$(readlink -f "$0")")"

# başlatıcı betiğe tam yol yaz
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$APPS" "$ICONS"

# venv varsa onu kullan; başlatıcı betik bu seçimi kendisi yapar
EXEC="sh $DIR/pardus-erisim"

sed "s|^Exec=.*|Exec=$EXEC|; s|^Icon=.*|Icon=$ICONS/tr.org.pardus.erisim.png|" \
    "$DIR/data/tr.org.pardus.erisim.desktop" > "$APPS/tr.org.pardus.erisim.desktop"
cp "$DIR/assets/icon.png" "$ICONS/tr.org.pardus.erisim.png"

# masaüstü simgesi
DESKTOP="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP" ]; then
    cp "$APPS/tr.org.pardus.erisim.desktop" "$DESKTOP/"
    chmod +x "$DESKTOP/tr.org.pardus.erisim.desktop"
fi

update-desktop-database "$APPS" 2>/dev/null || true
echo "Kuruldu: menü + masaüstü simgesi (Pardus Erişim)"
