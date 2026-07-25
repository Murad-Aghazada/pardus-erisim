# Pardus Erişim · Bakış ve Ses

Gözle ve sesle bilgisayar kullanımı. Fare ya da klavye gerektirmeden Pardus'u
kullanmayı sağlayan bir erişilebilirlik uygulaması.

**TEKNOFEST · Pardus İşletim Sistemi kategorisi** için geliştirildi.

Dört katman:

- **Kafa ile Kontrol** — Kamera kafa duruşunu izler (MediaPipe
  FaceLandmarker): kafanı hafifçe sağa çevir, imleç sağa gider. Kalibrasyon
  YOKTUR; açılışta ~1 saniyede nötr duruş öğrenilir, "merkeze al" komutu
  istediğin an yeniden ortalar. **Jest ile tıklama**: gözlerini ~yarım saniye
  kapalı tut, tıklar (doğal göz kırpma çok kısa olduğundan tıklamaz).
  Üç katmanlı "hedeften kaçmama" güvencesi: (1) kafa pozu, mimiklerle
  OYNAMAYAN yanak-çerçevesinden ölçülür — göz kapama/ağız açma imleci
  kıpırdatmaz; (2) jest sinyali yükselmeye başlar başlamaz imleç donar;
  (3) tıklama, jestin başlamasından 0.35 sn ÖNCEKİ nişan noktasına gider
  (geri sarma tamponu). **Sol/sağ/orta tık bağımsız jestlere atanabilir**
  (Ayarlar → Kafa ile Kontrol); varsayılan yalnız sol tık = iki gözü
  kapatmadır, sağ/orta tık isteğe bağlı kapalı başlar — ör. sağ tık için
  yalnız sağ gözü kırpma (wink) seçilebilir. Aynı jest iki eyleme birden
  atanamaz, çakışma arayüzde engellenir. Diğer seçenekler: kaş kaldırma, ağız açma,
  gülümseme; ayrıca bekleyerek (dwell) tıklama.
  **Köşe mıknatısı**: imleç köşeye yaklaşınca hedefe kendiliğinden oturur —
  sağ üst köşeye yönel, kapat düğmesine yerleşir, gözlerini kapat, kapanır.
- **Ses ile Kontrol** — Türkçe komutlar cihazda, çevrimdışı çözülür.
  **Whisper motoru** (faster-whisper, 'small', int8) yüksek doğruluk sağlar;
  küçük sözlük sınırı yoktur ("tarayıcı", "kaydır" gibi kelimeleri tam duyar)
  ve komut sözcükleriyle yönlendirilir. Whisper yoksa hafif **Vosk** motoruna
  düşer (Ayarlar → Tanıma motoru: otomatik/whisper/vosk).
  Listeye uymayan HER doğal ifadeyi Gemini **eylem planına** çevirir ve
  uygulama adım adım yürütür: "youtube'da kedi videoları aç" → arama
  sayfası açılır; "yeni belge aç, içine merhaba yaz" → editör açılır,
  beklenir, metin yazılır; "ekranda ne yazıyor" → imlecin altı sesli okunur.
  Tehlikeli istekler ("dosyaları sil") modele değil beyaz listeye çarpar ve
  reddedilir; adımlar en fazla 6 tanedir ve yalnız güvenli türlerden oluşur.
- **Otomatik Sesli Okuma** — İmleç bir metnin üzerinde kısa süre durunca
  ekrandaki metin (OCR) sesli okunur; tarayıcı, PDF, menü fark etmez.
  Yerel tesseract varsa çevrimdışı, yoksa Gemini görüntü okumasıyla çalışır.
  Sesle: "oku", "okumayı durdur", "otomatik okumayı aç/kapat".
- **Asistan** — Gemini destekli Türkçe sohbet. Yazarak ya da "asistan …"
  diyerek soru sorulur; yanıt ekranda belirir ve sesli okunur (TTS).
- **Büyük ÇIKIŞ düğmesi** — Kenar çubuğunun altında, kafa ile kolayca
  hedeflenebilen iri bir kırmızı düğme. Kullanan kişi her an, yardımsız
  çıkabilir (sesle de: "çıkış").

## Doğrulama (bu depoda çalıştırılabilir)

| Test | Sonuç |
|---|---|
| `tests/test_gestures.py` — jest tıklaması (doğal kırpma reddi, yarım sn kapama, soğuma, kaş/ağız) + plan temizleme | 17/17 geçti |
| `tests/test_head.py` — kafa işaretçisi: yön kesinliği, nötr/ortala, hassasiyet, köşe mıknatısı | 11/11 geçti (mıknatıs köşeye 0.2 px kala oturur) |
| `tests/test_direction.py` — göz modu yön kilidi (sol→sol, kapak bağımsızlığı, ayna güvenliği) | 7/7 geçti |
| `tests/test_gaze.py` — göz modu 5 sentetik senaryo | tıklama hatası ort. 28–48 px, eşik altında |
| `tests/test_commands.py` — 48+ Türkçe söyleyiş + devretme + niyetler + güvenlik reddi | tümü geçti |
| `tests/test_filters.py` — One Euro davranışı | 3.3× titreme bastırma, <0.1 sn oturma |
| `tests/probe_camera.py` — gerçek webcam + FaceLandmarker | 20+ fps, %100 yüz bulma |
| Whisper vs Vosk (canlı, sentez Türkçe ses) | Whisper "tarayıcıyı aç", "kaydır"ı tam duyar; Vosk "tarihi aç", "kaydı" der. Whisper→komut: 5/6 |
| `python3 main.py --doctor` (sistem doktoru) | 12 bileşen tek tek denetlenir; eksikler için Türkçe çözüm komutu |
| Sesli Okuma canlı testi — ekran yakalama → OCR → metin | gerçek ekrandan doğru metin çıkarıldı |

## Mimari

Tek süreç, PySide6 (Qt) masaüstü uygulaması. Ağır kütüphaneler tembel
yüklenir; biri kurulu değilse uygulama çökmez, ilgili özellik Ayarlar'da
"Eksik" görünür.

```
main.py                    Giriş noktası (--doctor bayrağı dahil)
pardus-erisim              Başlatıcı betik (venv/paket düzeni)
install-pardus.sh          Tek adımlı sistem + Python kurulumu
install-desktop.sh         Menü/masaüstü simgesi
data/                      tr.org.pardus.erisim.desktop
debian/                    Paketleme iskeleti (gbp buildpackage)
app/
  theme.py                 Tasarım sistemi (renk, tipografi, QSS)
  state.py                 Merkezi durum + ayar kalıcılığı
  application.py           Denetleyici: motorlar, katmanlar, Gemini köprüsü
  doctor.py                Sistem teşhisi (--doctor)
  ui/
    main_window.py         Kenar çubuğu + sayfa yığını
    pages/                 Genel bakış, göz, ses, asistan, ayarlar, yardım
    widgets/               Anahtar, rozet, dwell buton, kamera, kartlar
    overlay/               Bakış imleci + kalibrasyon (tam ekran)
  vision/
    landmark_engine.py     MediaPipe Tasks: iris, kafa pozu, kırpma skoru
    head_mapper.py         Kafa işaretçisi + köşe mıknatısı
    eye_tracker.py         İzleme iş parçacığı (kafa varsayılan, göz deneysel)
    gaze_mapper.py         Göz modu kalibrasyonu (ridge, poz özellikli)
    filters.py             One Euro filtresi
  voice/
    whisper_recognizer.py  Whisper motoru (VAD + komut-yönlendirmeli)
    recognizer.py          Vosk yedek motoru + komut yönlendirici
    commands.py            Türkçe dilbilgisi + bulanık eşleştirme + niyetler
  assist/
    gemini_client.py       Gemini REST istemcisi (sohbet + niyet)
    reader.py              Otomatik Sesli Okuma (ekran OCR → TTS)
    tts.py                 Sesli okuma (Qt TTS)
    config.py              config.json (anahtar burada, repoya girmez)
  control/
    system_control.py      Fare, klavye, uygulama başlatma (pynput)
tests/                     Doğruluk ve canlı donanım testleri
```

## Kurulum

### Pardus / Debian / Ubuntu (önerilen — tek komut)

```bash
sh install-pardus.sh
```

Bu betik, pip'in **kuramadığı** sistem kitaplıklarını (Qt xcb, PortAudio,
OpenGL, konuşma, OCR) apt ile kurar, bir `.venv` oluşturur, Python
bağımlılıklarını ve Türkçe ses modelini indirir, masaüstü/menü simgesini ekler.
Sanal makinede uygulamanın açılmamasının **başlıca nedeni bu sistem
kitaplıklarının eksikliğidir** — betik bunu giderir.

### Elle kurulum (her platform)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Linux'ta ayrıca (pip kapsamaz):
```bash
sudo apt install -y libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1 \
                    libportaudio2 speech-dispatcher tesseract-ocr tesseract-ocr-tur
```

**Modeller:** Whisper ses modeli ilk kullanımda otomatik iner (~460 MB);
`face_landmarker.task` (kafa) da ilk çalıştırmada iner. Vosk yedeği için
`vosk-model-small-tr-0.3` → `models/` (install-pardus.sh hallederdi).
**Gemini anahtarı:** Ayarlar ekranından girilir (ya da `config.json`).

## Çalıştırma ve teşhis

```bash
python3 main.py             # tam ekran açılır  (Linux: ./pardus-erisim)
python3 main.py --doctor    # AÇILMIYORSA: eksik bileşenleri tek tek raporlar
```

`--doctor`, arayüz hiç açılmasa bile (ör. eksik Qt kitaplığı) çalışır ve her
sorun için Türkçe çözüm komutu verir. **Linux VM'de ilk iş budur.**

Masaüstü simgesi: `sh install-pardus.sh` (ya da yalnız simge için
`sh install-desktop.sh`). Windows geliştirmede masaüstündeki "Pardus Erisim"
kısayolu.

### Sanal makine notları
- **Kamera:** VirtualBox → Aygıtlar → Web Kameraları (Guest Additions gerekir);
  VMware → VM → Removable Devices. Kamera bağlı değilse kafa kontrolü açılmaz
  ama ses ve asistan çalışır.
- **Oturum türü:** İmleç kontrolü (pynput) **X11**'de tam çalışır; giriş
  ekranında "Xorg ile oturum" seç (Pardus varsayılanı X11'dir). Wayland'da
  imleç hareketi kısıtlıdır.
- **Mikrofon:** VM ses girişinin etkin olduğundan emin ol (`--doctor` denetler).

## Sesli komutlar (özet)

"tıkla", "çift tıkla", "sağ tıkla", "yukarı/aşağı/sola/sağa",
"kaydır aşağı/yukarı", "yaz …", "kopyala", "yapıştır", "geri al",
"internete gir", "youtube aç", "google aç", "vikipedi aç", "dosyaları aç",
"terminal aç", "satranç aç", "belge aç",
"uygulama mağazası", "pencereyi kapat", "sesi aç/kıs", "merkeze al", "çıkış",
"oku", "okumayı durdur", "otomatik okumayı aç/kapat", "asistan …" — ve
listeye uymayan her doğal ifade Gemini ile çözülür.

Not: küçük Türkçe Vosk modelinin sözlüğünde olmayan kelimeler ("tarayıcı",
"kaydır", "ortala") için sözlük-içi eşdeğerler tanınır ("internete gir",
"kaydı", "merkeze al"); katalog her iki söyleyişi de kabul eder.

## Güvenlik

Kenar çubuğundaki *Tümünü durdur* ya da **Esc** her iki sistemi anında
kapatır. Klavye her zaman önceliklidir. Ses tanıma tamamen cihazda çalışır;
yalnızca asistan soruları ve yerel dilbilgisinin anlamadığı ifadeler
(etkinleştirildiyse) Gemini'ye gider.

## Pardus paketi

Depo, Pardus uygulama düzenine uygundur (`debian/`, `data/*.desktop`,
başlatıcı betik). Paket: `gbp buildpackage -us -uc` (debhelper 13).
"# pardusos" 
