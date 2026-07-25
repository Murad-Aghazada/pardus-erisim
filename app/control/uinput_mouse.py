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
"""

from __future__ import annotations


class UInputMouse:
    def __init__(self, screen_w: int, screen_h: int):
        self.available = False
        self.screen_w = max(1, int(screen_w))
        self.screen_h = max(1, int(screen_h))
        self._dev = None
        self._e = None
        self._error = ""
        self._x, self._y = self.screen_w // 2, self.screen_h // 2
        try:
            from evdev import UInput, ecodes as e, AbsInfo

            capabilities = {
                e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
                e.EV_ABS: [
                    (e.ABS_X, AbsInfo(value=0, min=0, max=self.screen_w,
                                      fuzz=0, flat=0, resolution=0)),
                    (e.ABS_Y, AbsInfo(value=0, min=0, max=self.screen_h,
                                      fuzz=0, flat=0, resolution=0)),
                ],
                e.EV_REL: [e.REL_WHEEL],
            }
            # ÖNEMLİ: input_props VERME (özellikle INPUT_PROP_DIRECT değil).
            # INPUT_PROP_DIRECT çekirdeğe "bu bir dokunmatik ekran" der —
            # libinput bunu AYRI bir dokunma yüzeyi olarak izler, normal
            # imleç/tıklama yönlendirmesinden kopuk kendi imlecini çizer
            # (iki farı görünmesinin ve tıklamanın düğmeye ulaşmamasının
            # nedeni buydu). Hiç input_props vermemek çekirdek varsayılanı
            # INPUT_PROP_POINTER'a düşürür — grafik tableti gibi MUTLAK
            # konumlu ama TEK, paylaşılan sistem imleciyle birleşen bir
            # aygıt; göreli fare ivmesi (pointer acceleration) yine
            # uygulanmaz çünkü ABS eksenleri ivme filtresinden muaftır.
            self._dev = UInput(capabilities, name="pardus-erisim-sanal-fare")
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

    def click(self, button: str = "left", double: bool = False):
        if not self._dev:
            return
        btn = {"left": self._e.BTN_LEFT,
               "right": self._e.BTN_RIGHT,
               "middle": self._e.BTN_MIDDLE}.get(button, self._e.BTN_LEFT)
        try:
            for _ in range(2 if double else 1):
                self._dev.write(self._e.EV_KEY, btn, 1)
                self._dev.syn()
                self._dev.write(self._e.EV_KEY, btn, 0)
                self._dev.syn()
        except Exception:
            pass

    def scroll(self, dy: int):
        if not self._dev:
            return
        try:
            self._dev.write(self._e.EV_REL, self._e.REL_WHEEL, int(dy))
            self._dev.syn()
        except Exception:
            pass

    def close(self):
        if self._dev:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None
