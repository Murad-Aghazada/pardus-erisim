"""
Göz izleme motoru.

Ayrı iş parçacığında webcam'i okur; LandmarkEngine (MediaPipe Tasks) ile
iris + kafa pozu + kırpma skoru çıkarır, bakışı One Euro filtresiyle
yumuşatıp ekran koordinatına eşler. Kütüphane/kamera yoksa çökmeden
'error' durumu yayar.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

from app.vision.gaze_mapper import GazeMapper
from app.vision.filters import GazeFilter2D
from app.vision.landmark_engine import L_IRIS, R_IRIS, L_CORNERS, R_CORNERS


class EyeTracker(QThread):
    frame_ready = Signal(object)          # QImage (önizleme)
    gaze_screen = Signal(float, float)    # ekran pikseli (mantıksal)
    gesture_click = Signal(float, float)  # jest tıklaması: HEDEFLENEN konum
    status = Signal(str)                  # idle|starting|tracking|no_face|error
    capability = Signal(bool)
    fps_report = Signal(float)

    REWIND_S = 0.35   # jest başlarken imlecin bu kadar öncesine kilitlen

    def __init__(self, screen_w: int, screen_h: int, parent=None):
        super().__init__(parent)
        from app.vision.head_mapper import HeadMapper
        from app.vision.gestures import GestureClick
        self.mapper = GazeMapper(screen_w, screen_h)      # göz modu (deneysel)
        self.head_mapper = HeadMapper(screen_w, screen_h)  # varsayılan mod
        self.filter = GazeFilter2D()
        self.gesture = GestureClick()
        self._running = False

        self.mode = "head"               # "head" | "eye"
        self.sensitivity = 55
        self.emit_preview = True

        self._calibrating = False
        self._sample: tuple[float, float, float, float] | None = None

        # jest sırasında imleç kilidi: son konumlar tamponu + kilitli hedef
        from collections import deque
        self._history: deque = deque(maxlen=64)
        self._frozen = False
        self._latched: tuple[float, float] | None = None

    def _pos_before(self, t: float) -> tuple[float, float] | None:
        """t anından önceki son yayınlanan konum (jest öncesi nişan noktası)."""
        best = None
        for ts, x, y in self._history:
            if ts <= t:
                best = (x, y)
            else:
                break
        if best is None and self._history:
            best = (self._history[0][1], self._history[0][2])
        return best

    # ---- Dışarıdan ayar ----
    def apply_config(self, cfg):
        self.sensitivity = cfg.sensitivity
        self.mapper.sensitivity = cfg.sensitivity
        self.head_mapper.sensitivity = cfg.sensitivity
        self.filter.set_smoothing(cfg.smoothing)
        self.gesture.set_gesture(cfg.click_gesture)

    def recenter(self):
        """Kafa nötrünü şu anki duruştan yeniden topla (~1 sn)."""
        self.head_mapper.recenter()
        self.filter.reset()

    def set_calibrating(self, on: bool):
        self._calibrating = on
        if not on:
            self.filter.reset()

    def current_sample(self) -> tuple[float, float, float, float] | None:
        """Kalibrasyon için anlık (rx, ry, yaw, pitch)."""
        return self._sample

    def stop(self):
        self._running = False
        self.wait(5000)

    # ---- İş parçacığı ----
    def run(self):
        # bayrak en başta: init sırasında stop() gelirse döngüye hiç girmeyiz
        self._running = True
        self.status.emit("starting")
        try:
            import cv2
            from app.vision.landmark_engine import LandmarkEngine
            engine = LandmarkEngine()
        except Exception:
            self.capability.emit(False)
            self.status.emit("error")
            return

        self.capability.emit(True)

        cap = cv2.VideoCapture(0)
        if not cap or not cap.isOpened():
            self.status.emit("error")
            engine.close()
            if cap:
                cap.release()
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.status.emit("tracking")
        emitted_no_face = False
        frames, fps_t = 0, time.monotonic()

        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.02)
                    continue

                frame = cv2.flip(frame, 1)  # ayna görünümü
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = engine.process(rgb)

                if result.landmarks is not None:
                    if emitted_no_face:
                        self.status.emit("tracking")
                        emitted_no_face = False
                    rx, ry = result.ratio
                    yaw, pitch = result.pose
                    self._sample = (rx, ry, yaw, pitch)

                    now = time.monotonic()
                    click, freeze = self.gesture.update(result.gestures, now)

                    pt = None
                    if self.mode == "head":
                        hy, hp = result.head
                        if self.head_mapper.feed_neutral(hy, hp):
                            pt = self.head_mapper.map(hy, hp)
                    elif not self._calibrating:
                        pt = self.mapper.map(rx, ry, yaw, pitch)

                    if pt is not None:
                        if freeze:
                            if not self._frozen:
                                # jest başladı: nişan noktası, jest ÖNCESİNİN konumu
                                self._frozen = True
                                self._latched = self._pos_before(now - self.REWIND_S)
                        else:
                            self._frozen = False
                            gx, gy = self.filter.apply(*pt)
                            self._history.append((now, gx, gy))
                            self.gaze_screen.emit(gx, gy)

                    if click:
                        pos = self._latched
                        if pos is None and self._history:
                            pos = (self._history[-1][1], self._history[-1][2])
                        if pos is not None:
                            self.gesture_click.emit(pos[0], pos[1])

                    if self.emit_preview:
                        self._emit_frame(frame, result.landmarks, cv2)
                else:
                    self._sample = None
                    if not emitted_no_face:
                        self.status.emit("no_face")
                        emitted_no_face = True
                    if self.emit_preview:
                        self._emit_frame(frame, None, cv2)

                frames += 1
                now = time.monotonic()
                if now - fps_t >= 2.0:
                    self.fps_report.emit(frames / (now - fps_t))
                    frames, fps_t = 0, now

                time.sleep(0.002)
        finally:
            cap.release()
            engine.close()
            self.status.emit("idle")

    def _emit_frame(self, frame, lm, cv2):
        import numpy as np
        h, w = frame.shape[:2]
        if lm is not None:
            for iris in (L_IRIS, R_IRIS):
                cx = int(np.mean([lm[i].x for i in iris]) * w)
                cy = int(np.mean([lm[i].y for i in iris]) * h)
                cv2.circle(frame, (cx, cy), 4, (42, 86, 196), -1)
                cv2.circle(frame, (cx, cy), 9, (184, 179, 19), 1)
            for corners in (L_CORNERS, R_CORNERS):
                p0 = (int(lm[corners[0]].x * w), int(lm[corners[0]].y * h))
                p1 = (int(lm[corners[1]].x * w), int(lm[corners[1]].y * h))
                cv2.line(frame, p0, p1, (184, 179, 19), 1)

        from PySide6.QtGui import QImage
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        self.frame_ready.emit(img)
