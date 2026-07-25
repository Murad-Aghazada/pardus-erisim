"""
Gerçek fare hareketi/tıklaması izleyici — sanal (uinput) fareyle "boğuşmayı"
önler.

Wayland altında sanal fareyi (uinput) kullanırken sistemin GERÇEK imleç
konumunu geri okuyamayız: Wayland bunu istemcilerden kasıtlı olarak gizler
(sorunun ta kendisi budur). "Kullanıcı fareyi şu an elle mi tutuyor?"
sorusunu bu yüzden konum karşılaştırmasıyla değil, GERÇEK fare aygıtının ham
REL_X/REL_Y (hareket) VE EV_KEY (tıklama) olaylarını doğrudan dinleyerek
cevaplıyoruz — yalnız hareketi izlemek yetmez: kullanıcı fareyi konumlayıp
DURUP tıkladığında (aim-then-click) bekleme süresi tam tıklama anında dolup
göz kontrolü imleci geri kapabilirdi. Kendi sanal aygıtımız
(uinput_mouse.py) adıyla ayırt edilip dışarıda bırakılır, bu yüzden kendi
hareketimizle karışmaz.

Gerekli izin: /dev/input/event* okuma (aynı 'input' grubu, uinput ile aynı
kurulum — bkz. install-pardus.sh).
"""

from __future__ import annotations

import threading
import time


class RealMouseWatcher:
    def __init__(self, exclude_name: str = "pardus-erisim-sanal-fare"):
        self.available = False
        self._exclude_name = exclude_name
        self._last_t = 0.0
        self._stop = False
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _find_mice(self):
        import evdev
        from evdev import ecodes
        mice = []
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except Exception:
                continue
            if dev.name == self._exclude_name:
                dev.close()
                continue
            caps = dev.capabilities().get(ecodes.EV_REL, [])
            if ecodes.REL_X in caps and ecodes.REL_Y in caps:
                mice.append(dev)
            else:
                dev.close()
        return mice

    def _run(self):
        try:
            import selectors
            from evdev import ecodes
            devices = self._find_mice()
        except Exception:
            return
        if not devices:
            return
        self.available = True
        sel = selectors.DefaultSelector()
        for dev in devices:
            sel.register(dev, selectors.EVENT_READ)
        try:
            while not self._stop:
                for key, _ in sel.select(timeout=0.5):
                    dev = key.fileobj
                    try:
                        for event in dev.read():
                            # hareket VEYA tıklama — yalnız hareket izlemek
                            # yetmez: kullanıcı fareyi konumlayıp DURUP
                            # tıkladığında (aim-then-click) bekleme süresi
                            # tam tıklama anında dolup göz kontrolü imleci
                            # geri kapabilirdi
                            if event.type in (ecodes.EV_REL, ecodes.EV_KEY):
                                self._last_t = time.monotonic()
                    except (OSError, BlockingIOError):
                        continue
        finally:
            for dev in devices:
                try:
                    dev.close()
                except Exception:
                    pass

    def last_motion_age(self) -> float:
        """Son GERÇEK fare hareketinden bu yana geçen süre (sn); hiç yoksa büyük değer."""
        if self._last_t == 0.0:
            return 1e9
        return time.monotonic() - self._last_t

    def stop(self):
        self._stop = True
        if self._thread:
            self._thread.join(timeout=1.0)
