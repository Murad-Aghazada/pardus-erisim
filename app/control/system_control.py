"""
Sistem denetimi — fare, klavye ve uygulama başlatma.

Hem göz izleme (imleç + tıklama) hem de ses (yazma, uygulama açma, sistem
komutları) bu katmanı kullanır. pynput yoksa uygulama çökmez; işlemler
sessizce yok sayılır ve `available` False olur.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import platform


class SystemControl:
    def __init__(self):
        self.available = False
        self._mouse = None
        self._kb = None
        self._Key = None
        self._Button = None
        try:
            from pynput.mouse import Controller as MouseController, Button
            from pynput.keyboard import Controller as KbController, Key
            self._mouse = MouseController()
            self._kb = KbController()
            self._Key = Key
            self._Button = Button
            self.available = True
        except Exception as exc:  # pragma: no cover - ortam bağımlı
            self._error = str(exc)

    # ---- İşaretçi ----
    def move_to(self, x: int, y: int):
        if self._mouse:
            self._mouse.position = (int(x), int(y))

    def move_by(self, dx: float, dy: float):
        if self._mouse:
            px, py = self._mouse.position
            self._mouse.position = (int(px + dx), int(py + dy))

    def click(self, button: str = "left", double: bool = False):
        if not self._mouse:
            return
        btn = self._Button.right if button == "right" else self._Button.left
        self._mouse.click(btn, 2 if double else 1)

    def scroll(self, dy: int):
        if self._mouse:
            self._mouse.scroll(0, dy)

    # ---- Klavye ----
    def type_text(self, text: str):
        if self._kb:
            self._kb.type(text)

    def press(self, *keys: str):
        """Tek tuş ya da kısayol. Örn: press('ctrl','c')."""
        if not self._kb:
            return
        resolved = [self._resolve_key(k) for k in keys]
        for k in resolved:
            self._kb.press(k)
        for k in reversed(resolved):
            self._kb.release(k)

    def _resolve_key(self, name: str):
        name = name.lower()
        return getattr(self._Key, name, name)

    # ---- Uygulama başlatma ----
    def launch(self, candidates: list[str]) -> bool:
        """Aday komutlardan ilk bulunanı başlatır. Bulursa True."""
        for cmd in candidates:
            exe = cmd.split()[0]
            if shutil.which(exe) or os.path.exists(exe):
                try:
                    if platform.system() == "Windows":
                        subprocess.Popen(cmd, shell=True)
                    else:
                        subprocess.Popen(cmd.split(),
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    continue
        # Windows'ta 'start' ile dene (tarayıcı vb.)
        if platform.system() == "Windows" and candidates:
            try:
                os.startfile(candidates[0])  # type: ignore[attr-defined]
                return True
            except Exception:
                return False
        return False

    def open_url(self, url: str) -> bool:
        import webbrowser
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False
