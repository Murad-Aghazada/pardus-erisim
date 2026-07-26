"""
Wayland/X11 ortak imleç sürücüsü — çekirdek (evdev/uinput) sanal fare.

Wayland, hiçbir istemcinin (yetkili olsa bile) ekran genelinde imleci
sürmesine ya da başka pencerede tıklamasına izin vermez; bu protokol
seviyesinde kasıtlı bir güvenlik kısıtıdır (bkz. system_control.py
SystemControl.wayland_limited). Bu modül işletim sistemi çekirdeğinde
GERÇEK bir USB fare gibi görünen bir aygıt (/dev/uinput) oluşturur; masaüstü
ortamı bunu donanım fareden ayırt edemez, bu yüzden Wayland/X11 ya da
GNOME/KDE farkı olmadan çalışır.

Gereken tek şey /dev/uinput'a yazma izni (bkz. install-pardus.sh —
99-uinput.rules + 'input' grubu). İzin yoksa `available` False kalır ve
çağıran taraf (SystemControl) pynput'a döner.

İKİ AYGIT KULLANILIR — ölçümle bulunan bir libinput davranışı yüzünden:

  * konum aygıtı: yalnız ABS_X/ABS_Y. Mutlak konum, imleci tam istenen
    piksele koyar ve fare ivmesinden etkilenmez.
  * düğme aygıtı: sıradan GÖRELİ fare (REL_X/REL_Y + BTN_*).

Tek aygıtta ABS eksenleri ile BTN_LEFT birlikte tanıtıldığında imleç
hareketi çalışıyor ama TIKLAMALAR HİÇBİR PENCEREYE ULAŞMIYOR (libinput
aygıtı mutlak konumlu bir tablet/dokunmatik gibi değerlendirip çıplak
BTN_LEFT'i yok sayıyor). Düğmeler ayrı, sıradan bir fare aygıtından
gönderildiğinde sorun tamamen kayboluyor; iki aygıt da aynı paylaşılan
sistem imlecini sürdüğü için tıklama, konum aygıtının götürdüğü yere düşer.
"""

from __future__ import annotations


class UInputMouse:
    def __init__(self, screen_w: int, screen_h: int):
        self.available = False
        self.screen_w = max(1, int(screen_w))
        self.screen_h = max(1, int(screen_h))
        self._dev = None          # konum (ABS)
        self._btn = None          # düğmeler (göreli fare)
        self._e = None
        self._error = ""
        self._x, self._y = self.screen_w // 2, self.screen_h // 2
        try:
            from evdev import UInput, ecodes as e, AbsInfo

            # ÖNEMLİ: input_props VERME (özellikle INPUT_PROP_DIRECT değil).
            # INPUT_PROP_DIRECT çekirdeğe "bu bir dokunmatik ekran" der —
            # libinput bunu AYRI bir dokunma yüzeyi olarak izler, normal
            # imleç yönlendirmesinden kopuk kendi imlecini çizer (iki fare
            # görünmesinin nedeni buydu).
            # Konum aygıtı düğmeleri de TANITIR (ama onlara hiç yazmayız):
            # libinput bir aygıtı ancak düğme yeteneği varsa "pointer" olarak
            # sınıflar; yalnız ABS eksenli bir aygıt imleci HİÇ hareket
            # ettirmiyor. Düğme olayları yine ayrı aygıttan gider.
            self._dev = UInput(
                {e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
                 e.EV_ABS: [
                    (e.ABS_X, AbsInfo(value=0, min=0, max=self.screen_w,
                                      fuzz=0, flat=0, resolution=0)),
                    (e.ABS_Y, AbsInfo(value=0, min=0, max=self.screen_h,
                                      fuzz=0, flat=0, resolution=0)),
                 ],
                 e.EV_REL: [e.REL_WHEEL]},
                name="pardus-erisim-sanal-fare")
            self._btn = UInput(
                {e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL],
                 e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE]},
                name="pardus-erisim-sanal-fare-dugme")
            self._e = e
            self.available = True
        except Exception as exc:  # pragma: no cover - izin/ortam bağımlı
            self._error = str(exc)

    def move_to(self, x, y):
        if not self._dev:
            return
        x = max(0, min(self.screen_w, int(x)))
        y = max(0, min(self.screen_h, int(y)))
        try:
            self._dev.write(self._e.EV_ABS, self._e.ABS_X, x)
            self._dev.write(self._e.EV_ABS, self._e.ABS_Y, y)
            self._dev.syn()
            self._x, self._y = x, y
        except Exception:
            pass

    def move_by(self, dx: float, dy: float):
        self.move_to(self._x + dx, self._y + dy)

    def position(self) -> tuple[int, int]:
        """Son yazılan konum (gerçek geri-okuma değil — bkz. modül başlığı)."""
        return (self._x, self._y)

    # Basma ile bırakma arasında GERÇEK bir süre olmalı. Sıfır süreli
    # (aynı ana düşen) bas-bırak çiftini compositor/araç takımı geçerli bir
    # tıklama saymayıp düşürebiliyor; gerçek bir farede bu süre ~50-100 ms'dir.
    PRESS_MS = 55
    # Çift tıklamada iki tıklama arası boşluk (aksi halde tek tık sanılır).
    GAP_MS = 60

    def click(self, button: str = "left", double: bool = False):
        # Düğmeler AYRI, göreli fare aygıtından gider — bkz. modül başlığı
        # (ABS eksenli aygıttan gönderilen BTN_* hiçbir pencereye ulaşmıyor).
        if not self._btn:
            return
        import time
        btn = {"left": self._e.BTN_LEFT,
               "right": self._e.BTN_RIGHT,
               "middle": self._e.BTN_MIDDLE}.get(button, self._e.BTN_LEFT)
        try:
            for i in range(2 if double else 1):
                if i:
                    time.sleep(self.GAP_MS / 1000.0)
                self._btn.write(self._e.EV_KEY, btn, 1)
                self._btn.syn()
                time.sleep(self.PRESS_MS / 1000.0)
                self._btn.write(self._e.EV_KEY, btn, 0)
                self._btn.syn()
        except Exception:
            pass

    def scroll(self, dy: int):
        if not self._btn:
            return
        try:
            self._btn.write(self._e.EV_REL, self._e.REL_WHEEL, int(dy))
            self._btn.syn()
        except Exception:
            pass

    def close(self):
        for attr in ("_dev", "_btn"):
            dev = getattr(self, attr)
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
                setattr(self, attr, None)
