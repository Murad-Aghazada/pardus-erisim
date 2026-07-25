"""
Yüz landmark motoru — MediaPipe Tasks API (FaceLandmarker) sarmalayıcısı.

Modern API; iris dahil 478 nokta, göz kırpma blendshape skorları ve gerçek
kafa pozu (dönüşüm matrisi) verir. Hem izleyici hem test sondaları bunu
kullanır; hesap mantığı tek yerde durur.
"""

from __future__ import annotations

import math
import os
import time

import numpy as np

# Landmark indeksleri (FaceMesh şeması). Not: 33/133 kişinin SAĞ gözüdür,
# 362/263 SOL gözü (MediaPipe adlandırması); aynadan çevrilmiş karede sağ göz
# görüntünün sağında belirir. Eşleştirme çiftleri tutarlıdır:
# 33/133 ↔ iris 468-472, 362/263 ↔ iris 473-477.
L_CORNERS = (33, 133)
L_LID = (159, 145)
R_CORNERS = (362, 263)
R_LID = (386, 374)
L_IRIS = (468, 469, 470, 471, 472)
R_IRIS = (473, 474, 475, 476, 477)
NOSE_TIP = 1
CHIN = 152
FOREHEAD = 10
# Yüz ovalinin kulak hizasındaki yan noktaları: göz kırpma, ağız açma ve
# konuşma bunları OYNATMAZ. Kafa işaretçisi pozu bu çerçeveye göre ölçülür ki
# tıklama jesti imleci sürüklemesin.
FACE_SIDES = (234, 454)


def model_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "models", "face_landmarker.task")


def ensure_model() -> str | None:
    """Model dosyası yoksa resmî Google deposundan indir. Yol ya da None."""
    path = model_path()
    if os.path.isfile(path) and os.path.getsize(path) > 1_000_000:
        return path
    url = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/"
           "face_landmarker/float16/latest/face_landmarker.task")
    try:
        import requests
        os.makedirs(os.path.dirname(path), exist_ok=True)
        r = requests.get(url, timeout=60)
        if r.status_code == 200 and len(r.content) > 1_000_000:
            with open(path, "wb") as f:
                f.write(r.content)
            return path
    except Exception:
        pass
    return None


class FrameResult:
    __slots__ = ("landmarks", "ratio", "pose", "head", "blink_score", "gestures")

    def __init__(self, landmarks, ratio, pose, head, blink_score, gestures=None):
        self.landmarks = landmarks        # 478 nokta ya da None
        self.ratio = ratio                # (rx, ry) ya da None
        self.pose = pose                  # (yaw, pitch) matris/geo — göz kalibrasyon özelliği
        self.head = head                  # (yaw, pitch) HER ZAMAN geometrik — kafa işaretçisi
        self.blink_score = blink_score    # 0..1 (1 = kapalı) ya da None
        self.gestures = gestures or {}    # {"blink","blink_left","blink_right","jaw","brow","smile"} skorları


class LandmarkEngine:
    """VIDEO modunda FaceLandmarker; kare başına FrameResult üretir."""

    def __init__(self):
        import mediapipe as mp
        from mediapipe.tasks.python.core.base_options import BaseOptions
        from mediapipe.tasks.python import vision

        path = ensure_model()
        if not path:
            raise RuntimeError("face_landmarker.task modeli yok ve indirilemedi")

        self._mp = mp
        opts = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=path),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._lm = vision.FaceLandmarker.create_from_options(opts)
        self._t0 = time.monotonic()
        self._last_ts = -1

    def close(self):
        try:
            self._lm.close()
        except Exception:
            pass

    def process(self, rgb_frame: np.ndarray) -> FrameResult:
        mp = self._mp
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        ts = int((time.monotonic() - self._t0) * 1000)
        if ts <= self._last_ts:          # VIDEO modu kesin artan ister
            ts = self._last_ts + 1
        self._last_ts = ts
        res = self._lm.detect_for_video(image, ts)

        if not res.face_landmarks:
            return FrameResult(None, None, None, None, None)

        lm = res.face_landmarks[0]
        ratio = self._gaze_ratio(lm)
        head = self._pose_geometric(lm)     # işaret kesin: kafa işaretçisi bunu kullanır
        pose = self._pose_from_matrix(res) or head
        gestures = self._gesture_scores(res)
        blink = gestures.get("blink")
        return FrameResult(lm, ratio, pose, head, blink, gestures)

    # ---- hesaplar ----
    @staticmethod
    def _gaze_ratio(lm) -> tuple[float, float]:
        """İşaret-güvenli bakış oranı.

        Yatay: iris merkezinin köşeler arasındaki konumu, köşeler min/max ile
        sıralanır — ayna çevirmesi ve indeks sırası yönü ASLA ters çeviremez.
        0 = görüntü solu, 1 = görüntü sağı (ayna görünümünde kullanıcının
        soluna bakış = görüntü solu = ekran solu).

        Dikey: iris merkezinin GÖZ KÖŞELERİ çizgisine göre yüksekliği, göz
        genişliğiyle normalize. Göz kapakları KULLANILMAZ: kapaklar bakışla
        birlikte hareket ettiğinden kapak-göreli oran dikey yönü tersine
        çevirir (klasik hata). + değer = çizginin altı = aşağı bakış.
        """
        def px(i):
            return np.array([lm[i].x, lm[i].y])

        def eye_ratio(corners, iris):
            c0, c1 = px(corners[0]), px(corners[1])
            center = np.mean([px(i) for i in iris], axis=0)
            lo, hi = min(c0[0], c1[0]), max(c0[0], c1[0])
            width = hi - lo
            if width < 1e-6:
                return 0.5, 0.0
            hr = (center[0] - lo) / width
            mid_y = (c0[1] + c1[1]) / 2.0
            vr = (center[1] - mid_y) / width
            return hr, vr

        ahr, avr = eye_ratio(L_CORNERS, L_IRIS)
        bhr, bvr = eye_ratio(R_CORNERS, R_IRIS)
        return (ahr + bhr) / 2.0, (avr + bvr) / 2.0

    @staticmethod
    def _pose_from_matrix(res) -> tuple[float, float] | None:
        try:
            m = np.array(res.facial_transformation_matrixes[0])
            R = m[:3, :3]
            yaw = math.atan2(-R[2, 0], math.hypot(R[2, 1], R[2, 2]))
            pitch = math.atan2(R[2, 1], R[2, 2])
            return float(yaw), float(pitch)
        except (IndexError, TypeError, AttributeError):
            return None

    @staticmethod
    def _pose_geometric(lm) -> tuple[float, float]:
        """Mimik-bağışık kafa pozu: burun ucunun yanak-çizgisine göre konumu.

        Göz köşeleri (kısınca oynar) ve çene (ağız açınca düşer) KULLANILMAZ;
        referans, ifadeyle hareket etmeyen yüz-ovali yan noktalarıdır. Böylece
        göz kapama/ağız açma jestleri imleci kıpırdatmaz.
        Ayna karede: kafa sağa → yaw artar; kafa aşağı → pitch artar.
        """
        a = np.array([lm[FACE_SIDES[0]].x, lm[FACE_SIDES[0]].y])
        b = np.array([lm[FACE_SIDES[1]].x, lm[FACE_SIDES[1]].y])
        mid = (a + b) / 2.0
        width = np.linalg.norm(b - a) or 1e-6
        nose = np.array([lm[NOSE_TIP].x, lm[NOSE_TIP].y])
        return (float((nose[0] - mid[0]) / width),
                float((nose[1] - mid[1]) / width))

    @staticmethod
    def _gesture_scores(res) -> dict:
        """Jest tıklaması için blendshape skorları (yoksa boş sözlük)."""
        try:
            raw = {c.category_name: c.score for c in res.face_blendshapes[0]}
        except (IndexError, TypeError, AttributeError):
            return {}
        def avg(a, b):
            va, vb = raw.get(a), raw.get(b)
            if va is None or vb is None:
                return None
            return (va + vb) / 2.0
        out = {}
        blink = avg("eyeBlinkLeft", "eyeBlinkRight")
        if blink is not None:
            out["blink"] = blink
        # Tek göz kırpma (wink) için ayrı sol/sağ skorlar.
        # ÖNEMLİ — AYNA TAKASI: eye_tracker.py kareyi MediaPipe'a vermeden
        # önce aynalar (cv2.flip). MediaPipe blendshape'i gördüğü yüze göre
        # adlandırdığından "eyeBlinkLeft" aynalanmış yüzün solu, yani
        # KULLANICININ SAĞ gözüdür. Burada takas edilir ki blink_left
        # gerçekten kullanıcının SOL gözü olsun (aksi halde sol göz kırpma
        # sağ tıkı, sağ göz kırpma sol tıkı tetikler).
        if "eyeBlinkRight" in raw:
            out["blink_left"] = raw["eyeBlinkRight"]
        if "eyeBlinkLeft" in raw:
            out["blink_right"] = raw["eyeBlinkLeft"]
        if "jawOpen" in raw:
            out["jaw"] = raw["jawOpen"]
        brow = raw.get("browInnerUp")
        if brow is not None:
            out["brow"] = brow
        smile = avg("mouthSmileLeft", "mouthSmileRight")
        if smile is not None:
            out["smile"] = smile
        return out
