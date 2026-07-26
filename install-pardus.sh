#!/bin/sh
# Pardus / Debian tek adımlı kurulum.
#
# Sanal makinede ya da taze Pardus kurulumunda uygulamanın açılmamasının
# başlıca nedeni, pip'in KURAMADIĞI sistem kitaplıklarının (Qt xcb, PortAudio,
# OpenGL, konuşma) eksik olmasıdır. Bu betik önce onları apt ile kurar, sonra
# bir sanal ortam (venv) oluşturup Python bağımlılıklarını ve Türkçe ses
# modelini indirir.
#
# Kullanım:  sh install-pardus.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "== Pardus Erişim kurulumu =="
echo

# 1) Sistem kitaplıkları (yönetici izni ister) --------------------------------
if command -v apt >/dev/null 2>&1; then
    echo "[1/4] Sistem kitaplıkları kuruluyor (sudo parolası isteyebilir)..."
    sudo apt update -y || true
    sudo apt install -y \
        python3 python3-venv python3-pip \
        libxcb-cursor0 libxkbcommon-x11-0 libxcb-xinerama0 \
        libgl1 libegl1 libglib2.0-0 libdbus-1-3 \
        libportaudio2 \
        speech-dispatcher \
        tesseract-ocr tesseract-ocr-tur \
        v4l-utils \
        wget unzip
else
    echo "[1/4] 'apt' bulunamadı — Debian tabanlı değil. Sistem kitaplıklarını"
    echo "      elle kurman gerekebilir (libxcb-cursor0, libportaudio2 ...)."
fi

# 2) Python sanal ortamı ------------------------------------------------------
echo
echo "[2/4] Python sanal ortamı (.venv) hazırlanıyor..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt

# 3) Türkçe ses modeli (Vosk yedeği) ------------------------------------------
echo
echo "[3/4] Türkçe ses modeli denetleniyor..."
if [ ! -d "models/vosk-model-small-tr-0.3" ]; then
    mkdir -p models
    echo "      İndiriliyor (~46 MB)..."
    wget -q --show-progress -O /tmp/vosk-tr.zip \
        https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip
    unzip -q /tmp/vosk-tr.zip -d models/
    rm -f /tmp/vosk-tr.zip
    echo "      Tamam."
else
    echo "      Zaten var."
fi
echo "      Not: Whisper motoru (daha yüksek doğruluk) ilk kullanımda"
echo "      modelini kendisi indirir (~460 MB, internet gerekir)."

# 4) Wayland'da fare/imleç kontrolü için sanal aygıt izni --------------------
# Wayland, güvenlik gereği hiçbir uygulamanın ekran genelinde imleci
# sürmesine/tıklamasına izin vermez. Çözüm: çekirdek seviyesinde GERÇEK bir
# fare gibi görünen sanal aygıt (/dev/uinput) — bunun için tek seferlik izin
# gerekir. X11 oturumunda zararsızdır (kullanılmaz), bu yüzden koşulsuz kurulur.
echo
echo "[4/5] Wayland için sanal fare izni (uinput) ayarlanıyor..."
if [ "$(id -u)" -ne 0 ] && command -v udevadm >/dev/null 2>&1; then
    if [ ! -f /etc/udev/rules.d/99-pardus-erisim-uinput.rules ]; then
        echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' \
            | sudo tee /etc/udev/rules.d/99-pardus-erisim-uinput.rules >/dev/null
        sudo udevadm control --reload-rules
        sudo udevadm trigger
    fi
    if ! groups "$USER" | grep -qw input; then
        sudo usermod -aG input "$USER"
        echo "      '$USER' kullanıcısı 'input' grubuna eklendi."
        echo "      ÖNEMLİ: Bu değişikliğin etkili olması için OTURUMU KAPAT"
        echo "      ve tekrar aç (ya da yeniden başlat)."
    else
        echo "      Zaten '$USER' 'input' grubunda."
    fi
else
    echo "      atlandı (udevadm yok ya da root olarak çalıştırılıyor)"
fi

# 5) Masaüstü ve menü simgesi -------------------------------------------------
echo
echo "[5/5] Masaüstü/menü simgesi ekleniyor..."
sh "$DIR/install-desktop.sh" || echo "      (atlandı)"

echo
echo "== Kurulum bitti =="
echo "Denetim:   .venv/bin/python main.py --doctor"
echo "Başlat:    .venv/bin/python main.py"
echo "(Masaüstü simgesi de artık bu venv'i kullanır.)"
echo "Wayland'da fare kontrolü için: yukarıda 'input' grubuna eklendiysen"
echo "önce OTURUMU KAPATIP AÇ, sonra başlat."
