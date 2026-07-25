"""
Uygulama denetleyicisi (köprü).

Motorları (göz, ses, asistan, sistem denetimi) ve tam ekran katmanları
sahiplenir; tüm sinyalleri birbirine bağlar. Sayfalar bu nesnenin
yöntemlerini çağırır.

Ses komut hattı iki katmanlıdır:
  1. Yerel dilbilgisi (çevrimdışı, anında)
  2. Eşleşmezse Gemini niyet çözümleme (çevrimiçi, akıllı)
"""

from __future__ import annotations

import importlib.util
import math
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from app.state import AppState
from app.control.system_control import SystemControl
from app.voice.commands import CommandRouter
from app.assist import config as assist_config
from app.assist.tts import Speaker


def _have(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


class AppController(QObject):
    # Odaktan bağımsız acil-durdur: pencere odakta olmasa da her zaman çalışır
    panic_stop = Signal()

    # Elle fare hareketi algılama: göz/kafa imleci gerçek imleçle "boğuşmasın"
    MANUAL_OVERRIDE_PX = 40        # bu kadar sapma = kullanıcı fareyi elle tuttu
    # Doğal "konumla, DUR, tıkla" akışı 1-2 sn sürebilir; kısa bir bekleme
    # süresi tam tıklama anında dolup imleci geri kapabilirdi.
    MANUAL_OVERRIDE_COOLDOWN_S = 2.5

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.window = None
        self._eye_page = None
        self._voice_page = None
        self._assist_page = None

        screen = QGuiApplication.primaryScreen()
        geo = screen.geometry()
        self.screen_w, self.screen_h = geo.width(), geo.height()
        self._geo = geo
        # Qt mantıksal piksel kullanır; pynput fiziksel ister (ör. %125 ölçek)
        self._dpr = float(screen.devicePixelRatio() or 1.0)
        # Birincil ekranın tüm sanal masaüstü içindeki konumu (çoklu monitörde
        # birincil (0,0)'da olmayabilir) — imleç hedefine bu ofset eklenir.
        self._origin_x = int(geo.x() * self._dpr)
        self._origin_y = int(geo.y() * self._dpr)

        # ÖNEMLİ: uinput sanal farenin mutlak (ABS) konum aralığı TÜM sanal
        # masaüstünü (çoklu monitörde bile) kapsamalı — Wayland/libinput, ABS
        # aralığını yalnızca birincil ekranın kendi boyutuna göre değil,
        # birleşik masaüstünün tamamına göre eşler. Yalnız birincil ekranın
        # boyutu verilirse (ör. 2560x1440 iken gerçek masaüstü 5120x1600),
        # imleç orantılı ama YANLIŞ (uzak) bir noktaya gider.
        vgeo = screen.virtualGeometry()
        phys_w = int(vgeo.width() * self._dpr)
        phys_h = int(vgeo.height() * self._dpr)
        self.control = SystemControl(phys_w, phys_h)
        self.tracker = None
        self.overlay = None
        self.recognizer = None

        # elle fare hareketi algılama durumu (_on_gaze içinde kullanılır)
        self._last_cmd_pos: tuple[float, float] | None = None
        self._manual_override_until: float = 0.0
        self._real_mouse = None
        if self.control.using_uinput:
            from app.control.real_mouse_watch import RealMouseWatcher
            self._real_mouse = RealMouseWatcher()
            self._real_mouse.start()

        self.panic_stop.connect(self.stop_all)
        self._panic_listener = None
        self._start_panic_listener()

        self.speaker = Speaker()
        self.speaker.speaking_changed.connect(self._on_speaking_changed)
        self._cfg = assist_config.load()
        self._chat: list[dict] = []      # asistan sohbet geçmişi
        self._gem_tasks: set = set()     # çalışan Gemini iş parçacıkları
        self._zombies: list = []         # bitmesi beklenen eski iş parçacıkları
        self._plan: list = []            # yürütülen sesli eylem planı

        from app.vision.head_mapper import CornerMagnet
        from app.assist.reader import ReadAloud
        self.magnet = CornerMagnet(self.screen_w, self.screen_h)
        self.magnet.enabled = self.state.eye.magnet_enabled
        self.reader = ReadAloud(self.speaker)
        self.reader.set_auto(self.state.eye.auto_read)
        self.reader.read_started.connect(
            lambda t: self.state.log_event.emit("read", t[:80]))
        self.reader.unavailable.connect(self._on_read_unavailable)

        self.router = CommandRouter(self.control, {
            "set_eye": self.toggle_eye,
            "open_help": self.open_help,
            "ask_assistant": self.ask_assistant,
            "recenter": self.recenter_head,
            "read_now": self.reader.read_now,
            "read_stop": self.reader.stop,
            "read_auto": self.set_auto_read,
            "quit_app": self.quit_app,
        })

        self._probe()

    # ---- Odaktan bağımsız acil-durdur ----
    def _start_panic_listener(self):
        """Esc'i pencere odağından BAĞIMSIZ dinler (Qt kısayolu yalnız pencere
        odaktayken çalışır; imleç göz kontrolüyle boğuşurken odak başka bir
        pencerede kalabilir — o durumda bile çıkış garanti olsun diye)."""
        if not _have("pynput"):
            return
        try:
            from pynput import keyboard as pynput_keyboard

            def on_press(key):
                if key == pynput_keyboard.Key.esc:
                    self.panic_stop.emit()

            self._panic_listener = pynput_keyboard.Listener(on_press=on_press)
            self._panic_listener.daemon = True
            self._panic_listener.start()
        except Exception:
            self._panic_listener = None

    # ---- Başlangıç yetenek denetimi ----
    def _probe(self):
        self.state.set_capability("vision", _have("mediapipe") and _have("cv2"))
        # Ses: Whisper YA DA Vosk yeter — yalnız Vosk'a bakmak, Whisper
        # kuruluyken bile "Eksik" gösterip kullanıcıyı yanlış yönlendirirdi.
        self.state.set_capability(
            "voice", _have("sounddevice") and (_have("faster_whisper") or _have("vosk")))
        self.state.set_capability("control", self.control.available)
        from app.assist.gemini_client import has_key
        self.state.set_capability("assist", _have("requests") and has_key())

    def bind(self, window):
        self.window = window
        self._eye_page = window.pages["eye"]
        self._voice_page = window.pages["voice"]
        self._assist_page = window.pages.get("assist")

    # ---- Köprü: gezinme ----
    def navigate(self, key: str):
        if self.window:
            self.window.navigate(key)

    def open_help(self):
        self.navigate("help")

    def is_calibrated(self) -> bool:
        if self.tracker:
            return self.tracker.mapper.is_calibrated
        from app.vision.gaze_mapper import GazeMapper
        return GazeMapper(self.screen_w, self.screen_h).is_calibrated

    # ---- Göz sistemi ----
    def toggle_eye(self, on: bool):
        if on:
            self._start_eye()
        else:
            self._stop_eye()

    def _start_eye(self):
        if self.tracker is not None:
            return
        from app.vision.eye_tracker import EyeTracker
        from app.ui.overlay.gaze_overlay import GazeOverlay

        self.tracker = EyeTracker(self.screen_w, self.screen_h)
        self.tracker.apply_config(self.state.eye)
        self.tracker.frame_ready.connect(self._on_frame)
        self.tracker.gaze_screen.connect(self._on_gaze)
        self.tracker.gesture_click.connect(self._on_gesture_click)
        self.tracker.gesture_scores.connect(self._on_gesture_scores)
        self.tracker.status.connect(self.state.set_eye_status)
        self.tracker.capability.connect(lambda ok: self.state.set_capability("vision", ok))
        self.tracker.status.connect(self._eye_status_side_effects)

        self.overlay = GazeOverlay(self._geo)
        self.overlay.configure(self.state.eye.show_gaze_dot,
                               self.state.eye.dwell_enabled,
                               self.state.eye.dwell_ms)
        self.overlay.dwell_click.connect(self._on_dwell_click)

        self.state.set_eye_active(True)
        self.tracker.start()

    def _eye_status_side_effects(self, status: str):
        if status in ("tracking", "no_face"):
            self.state.set_camera_ready(True)
            if self.overlay and self.state.eye.show_gaze_dot:
                self.overlay.show()
        elif status == "error":
            self.state.set_camera_ready(False)
            self._stop_eye()

    def _stop_eye(self):
        if self.overlay:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None
        if self.tracker:
            self._retire_thread(self.tracker)
            self.tracker = None
        self.state.set_eye_active(False)
        self.state.set_eye_status("idle")
        self.state.set_camera_ready(False)
        self._last_cmd_pos = None
        self._manual_override_until = 0.0

    def _on_frame(self, image):
        if self._eye_page:
            self._eye_page.show_frame(image)

    def _on_gesture_scores(self, scores: dict):
        if self._eye_page:
            self._eye_page.show_gesture_scores(scores)

    def _on_gaze(self, x: float, y: float):
        # köşe mıknatısı: kapat düğmesi gibi köşe hedeflerine oturt
        x, y = self.magnet.apply(x, y)
        if self.overlay:
            self.overlay.set_gaze(x, y)

        now = time.monotonic()
        if now < self._manual_override_until:
            return  # kullanıcı fareyi elle tutuyor: kısa süre karışma

        target = (self._origin_x + x * self._dpr, self._origin_y + y * self._dpr)
        if self._real_mouse is not None:
            # uinput yolu: gerçek imleç konumu okunamaz (Wayland), bu yüzden
            # GERÇEK fare aygıtındaki ham hareketi doğrudan izleriz.
            if self._real_mouse.last_motion_age() < self.MANUAL_OVERRIDE_COOLDOWN_S:
                self._manual_override_until = now + self.MANUAL_OVERRIDE_COOLDOWN_S
                return
        elif self._last_cmd_pos is not None and self.control.available:
            cx, cy = self.control.position()
            lx, ly = self._last_cmd_pos
            if math.hypot(cx - lx, cy - ly) > self.MANUAL_OVERRIDE_PX:
                # gerçek imleç son komuttan uzakta: kullanıcı fareyi elle
                # hareket ettirmiş — göz kontrolünü kısa süre duraklat
                self._manual_override_until = now + self.MANUAL_OVERRIDE_COOLDOWN_S
                self._last_cmd_pos = None
                return

        self.control.move_to(*target)
        self._last_cmd_pos = target

    # uinput (Wayland) yolunda: imleç taşındıktan hemen sonra tıklarsak
    # compositor "imleç bu pencereye/widget'a girdi" durumunu henüz
    # işlememiş olabilir — tıklama, imlecin ÖNCEKİ konumundaki eski hover
    # durumuna düşer (ya da hiçbir yere). Kısa bir kare payı bu yarışı önler.
    CLICK_SETTLE_MS = 40

    def _on_gesture_click(self, x: float, y: float, action: str = "left"):
        """Jest tıklaması: jest ÖNCESİNDE nişan alınan noktaya tıkla."""
        x, y = self.magnet.apply(x, y)
        if self.overlay:
            self.overlay.set_gaze(x, y)
        target = (self._origin_x + x * self._dpr, self._origin_y + y * self._dpr)
        self.control.move_to(*target)
        self._last_cmd_pos = target
        if self.control.using_uinput:
            # Ayak: jest biter bitmez (göz açılır açılmaz) göz izleme hemen
            # devam eder ve _on_gaze imleci BAŞKA yere taşıyabilir — tam bu
            # bekleme penceresinde. Tıklama gerçekleşene kadar göz kontrolünün
            # imleci taşımasını engelle (aynı "elle fare" duraklatma mekanizması).
            self._manual_override_until = max(
                self._manual_override_until,
                time.monotonic() + self.CLICK_SETTLE_MS / 1000.0 + 0.05)
            QTimer.singleShot(self.CLICK_SETTLE_MS, lambda: self._finish_click(action))
        else:
            self._finish_click(action)

    def _on_dwell_click(self, x: int, y: int):
        target = (self._origin_x + x * self._dpr, self._origin_y + y * self._dpr)
        self.control.move_to(*target)
        self._last_cmd_pos = target
        if self.control.using_uinput:
            self._manual_override_until = max(
                self._manual_override_until,
                time.monotonic() + self.CLICK_SETTLE_MS / 1000.0 + 0.05)
            QTimer.singleShot(self.CLICK_SETTLE_MS, lambda: self._finish_click("left"))
        else:
            self._finish_click("left")

    def _finish_click(self, action: str):
        self.control.click(action)
        if self.overlay:
            self.overlay.flash()

    def apply_eye_config(self):
        self.magnet.enabled = self.state.eye.magnet_enabled
        if self.tracker:
            self.tracker.apply_config(self.state.eye)
        if self.overlay:
            self.overlay.configure(self.state.eye.show_gaze_dot,
                                   self.state.eye.dwell_enabled,
                                   self.state.eye.dwell_ms)
            if self.state.eye.show_gaze_dot:
                self.overlay.show()
            else:
                self.overlay.hide()

    def recenter_head(self):
        """Şu anki kafa duruşunu nötr kabul et (1 sn içinde etkili)."""
        if self.tracker:
            self.tracker.recenter()

    def set_auto_read(self, on: bool):
        self.state.eye.auto_read = bool(on)
        self.state.save()
        self.reader.set_auto(bool(on))
        if self._eye_page:
            self._eye_page._sync()

    def _on_read_unavailable(self, msg: str):
        """Ekran yakalama engelli: ayarı da kapat, kullanıcıya nedenini söyle."""
        self.state.eye.auto_read = False
        self.state.save()
        self.state.log_event.emit("read", msg)
        if self._eye_page:
            self._eye_page.show_read_note(msg)
            self._eye_page._sync()

    def start_calibration(self):
        """Göz modu kalibrasyonu (deneysel; varsayılan kafa modunda gerekmez)."""
        if not self.tracker or self.tracker.mode != "eye":
            return
        from app.ui.overlay.calibration import CalibrationOverlay
        self._cal = CalibrationOverlay(self.tracker, self._geo)
        self._cal.finished.connect(self._on_calibrated)
        self._cal.start()

    def _on_calibrated(self, ok: bool):
        if self._eye_page:
            self._eye_page._sync()
        if self.window:
            self.window.pages["dashboard"]._sync()

    # ---- Ses sistemi ----
    # TTS bittikten sonra hoparlörün/odanın son yankısı sönsün diye kısa
    # bir gecikmeyle mikrofonu aç (aksi halde asistanın son kelimesinin
    # kuyruğunu duyup yeni bir komut sanabilir).
    UNMUTE_DELAY_MS = 400

    def _on_speaking_changed(self, speaking: bool):
        if not self.recognizer:
            return
        if speaking:
            self.recognizer.set_muted(True)
        else:
            QTimer.singleShot(self.UNMUTE_DELAY_MS, self._unmute_voice)

    def _unmute_voice(self):
        if self.recognizer:
            self.recognizer.set_muted(False)

    def toggle_voice(self, on: bool):
        if on:
            self._start_voice()
        else:
            self._stop_voice()

    def _voice_engine_class(self):
        """Motor seçimi: Whisper varsa yüksek doğruluk, yoksa Vosk."""
        from app.voice.recognizer import VoiceRecognizer
        eng = self.state.voice.engine
        if eng != "vosk":
            from app.voice.whisper_recognizer import (
                WhisperRecognizer, whisper_available)
            if whisper_available():
                return WhisperRecognizer
            if eng == "whisper":
                return WhisperRecognizer   # kurulu değilse no_lib durumu yayar
        return VoiceRecognizer

    def _start_voice(self):
        if self.recognizer is not None:
            return
        cls = self._voice_engine_class()
        self.recognizer = cls(self.router)
        self.recognizer.set_muted(self.speaker.is_speaking)
        if hasattr(self.recognizer, "sensitivity"):
            self.recognizer.sensitivity = self.state.voice.sensitivity
        self.recognizer.require_wake = self.state.voice.require_wake
        self.recognizer.wake_word = self.state.voice.wake_word
        self.recognizer.partial_text.connect(self.state.transcript_changed.emit)
        self.recognizer.final_text.connect(self.state.transcript_changed.emit)
        self.recognizer.action_done.connect(self._on_action)
        self.recognizer.unmatched.connect(self._on_unmatched)
        self.recognizer.status.connect(self.state.set_voice_status)
        self.recognizer.status.connect(self._voice_status_side_effects)
        self.recognizer.capability.connect(lambda ok: self.state.set_capability("voice", ok))
        self.state.set_voice_active(True)
        self.recognizer.start()

    def _voice_status_side_effects(self, status: str):
        if status == "listening":
            self.state.set_mic_ready(True)
        elif status in ("no_lib", "no_model", "error"):
            self.state.set_mic_ready(False)
            QTimer.singleShot(50, self._finalize_voice_stop)

    def _finalize_voice_stop(self):
        if self.recognizer and not self.recognizer.isRunning():
            self.recognizer.deleteLater()
            self.recognizer = None
            self.state.set_voice_active(False)

    def _stop_voice(self):
        if self.recognizer:
            self._retire_thread(self.recognizer)
            self.recognizer = None
        self.state.set_voice_active(False)
        self.state.set_voice_status("idle")
        self.state.set_mic_ready(False)

    def _retire_thread(self, thread):
        """İş parçacığını durdur; bitmediyse asla yok etme (çökme önlemi)."""
        thread.stop()
        if thread.isFinished():
            thread.deleteLater()
        else:
            self._zombies.append(thread)
            thread.finished.connect(thread.deleteLater)

    def _on_action(self, desc: str):
        if self._voice_page:
            self._voice_page.show_action(desc)
        self.state.log_event.emit("voice", desc)

    # ---- Katman 2: Gemini plan çözümleme ----
    def _on_unmatched(self, text: str):
        from app.assist.gemini_client import GeminiTask, INTENT_SYSTEM, has_key
        if not has_key():
            return
        task = GeminiTask([{"role": "user", "text": text}], system=INTENT_SYSTEM)
        task.done.connect(lambda raw, t=text: self._on_plan_reply(t, raw))
        task.failed.connect(lambda _err: None)
        self._track(task)
        task.start()

    def _on_plan_reply(self, original: str, raw: str):
        from app.assist.gemini_client import parse_plan
        plan = parse_plan(raw)
        if not plan:
            return
        say = plan.get("say", "").strip()
        steps = plan.get("steps", [])
        if say and not steps:
            # saf soru-cevap: asistan akışına ver
            self._deliver_assistant(original, say)
            return
        if say:
            self._on_action(say)
            if self.speak_replies:
                self.speaker.say(say)
        self._run_plan(steps)

    def _run_plan(self, steps: list):
        """Adımları sırayla, aralarında kısa beklemeyle çalıştır."""
        self._plan = list(steps[:6])
        self._plan_step()

    def _plan_step(self):
        if not self._plan:
            return
        step = self._plan.pop(0)
        delay = 350                      # adımlar arası taban bekleme
        t = step.get("type")
        if t == "wait":
            delay = int(step.get("ms", 1000))
        elif t == "read_screen":
            self.reader.read_now()
        else:
            desc = self.router.execute_intent(step)
            if desc:
                self._on_action(desc)
        if self._plan:
            QTimer.singleShot(delay, self._plan_step)

    # ---- Asistan sohbeti ----
    @property
    def speak_replies(self) -> bool:
        return bool(self._cfg.get("speak_replies", True))

    def set_speak_replies(self, on: bool):
        self._cfg["speak_replies"] = bool(on)
        assist_config.save({"speak_replies": bool(on)})
        if not on:
            self.speaker.stop()

    def set_api_key(self, key: str):
        self._cfg["gemini_api_key"] = key.strip()
        assist_config.save({"gemini_api_key": key.strip()})
        self._probe()

    def ask_assistant(self, text: str):
        """Sohbet: yazıdan ya da sesten gelen soru."""
        from app.assist.gemini_client import GeminiTask, CHAT_SYSTEM, has_key
        if not has_key():
            if self._assist_page:
                self._assist_page.add_note("API anahtarı eksik. Ayarlar ekranından ekle.")
            return
        self._chat.append({"role": "user", "text": text})
        if self._assist_page:
            self._assist_page.add_user(text)
            self._assist_page.set_busy()
        self.navigate("assist")

        task = GeminiTask(list(self._chat), system=CHAT_SYSTEM)
        task.done.connect(lambda reply, q=text: self._on_chat_reply(reply))
        task.failed.connect(self._on_chat_failed)
        self._track(task)
        task.start()

    def _on_chat_reply(self, reply: str):
        self._chat.append({"role": "model", "text": reply})
        if self._assist_page:
            self._assist_page.add_reply(reply)
        if self.speak_replies:
            self.speaker.say(reply)

    def _on_chat_failed(self, err: str):
        msg = {
            "no_key": "API anahtarı eksik. Ayarlar ekranından ekle.",
            "network": "Ağ bağlantısı kurulamadı. İnterneti denetle.",
        }.get(err, f"Asistan yanıt veremedi ({err}).")
        if self._assist_page:
            self._assist_page.add_note(msg)

    def _deliver_assistant(self, question: str, answer: str):
        """Sesle sorulan, Gemini'nin yanıtladığı soru-cevabı işle."""
        self._chat.append({"role": "user", "text": question})
        self._chat.append({"role": "model", "text": answer})
        if self._assist_page:
            self._assist_page.add_user(question)
            self._assist_page.add_reply(answer)
        if self.speak_replies:
            self.speaker.say(answer)

    def _track(self, task):
        self._gem_tasks.add(task)
        task.finished.connect(lambda t=task: self._untrack(t))

    def _untrack(self, task):
        self._gem_tasks.discard(task)
        task.deleteLater()

    def apply_voice_config(self):
        if self.recognizer:
            self.recognizer.require_wake = self.state.voice.require_wake
            self.recognizer.wake_word = self.state.voice.wake_word
            if hasattr(self.recognizer, "sensitivity"):
                self.recognizer.sensitivity = self.state.voice.sensitivity
            # motor değiştiyse dinlemeyi yeni motorla yeniden başlat
            if type(self.recognizer) is not self._voice_engine_class():
                self._stop_voice()
                self._start_voice()

    def voice_engine_name(self) -> str:
        from app.voice.whisper_recognizer import whisper_available
        eng = self.state.voice.engine
        if eng == "vosk":
            return "Vosk"
        if whisper_available():
            return "Whisper"
        return "Whisper (kurulu değil)" if eng == "whisper" else "Vosk"

    def quit_app(self):
        """Sesle ya da büyük ÇIKIŞ düğmesiyle uygulamayı kapat."""
        if self.window:
            QTimer.singleShot(0, self.window.close)

    # ---- Global ----
    def stop_all(self):
        self._stop_eye()
        self._stop_voice()
        self.speaker.stop()

    def shutdown(self):
        self.stop_all()
        if self._panic_listener:
            self._panic_listener.stop()
        if self._real_mouse:
            self._real_mouse.stop()
        self.control.close()
        for t in list(self._gem_tasks):
            t.wait(500)
