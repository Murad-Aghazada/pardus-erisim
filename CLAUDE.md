# CLAUDE.md

Pardus Erişim (VeLink) — head/eye-tracking + voice control accessibility app for Pardus OS (TEKNOFEST entry). Single-process PySide6 desktop app, all UI/logs/comments in Turkish.

## Run / test

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 main.py --doctor    # diagnose missing deps/system libs before anything else
python3 main.py             # launch (fullscreen)
pytest tests/               # unit tests (no camera/mic needed)
python tests/probe_camera.py  # needs real webcam
python tests/probe_voice.py   # needs real mic
```

One-step Debian/Pardus setup: `sh install-pardus.sh` (apt system libs + venv + models + desktop icon).

Linux needs system libs pip can't install: `libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1 libportaudio2 speech-dispatcher tesseract-ocr tesseract-ocr-tur`. On Wayland, pynput's XTest/XWayland path can't drive the real cursor (protocol-level restriction, not a bug) — `install-pardus.sh` also sets up a `/dev/uinput` udev rule + `input` group so `SystemControl` falls back to a kernel-level virtual mouse (`app/control/uinput_mouse.py`) that works on Wayland too. Requires a relogin after first setup for the group membership to take effect; `--doctor` reports whether this permission is in place.

## Architecture

Heavy libs (mediapipe, cv2, faster-whisper, vosk) are lazy-imported and optional — missing one disables that feature (shown as "Eksik" in Settings) instead of crashing. `app/doctor.py` (`--doctor`) checks all of this standalone, without Qt.

- `app/state.py` — `AppState`: central reactive state (Qt signals) + `QSettings`-backed persistence for `EyeConfig`/`VoiceConfig`.
- `app/application.py` — `AppController`: owns all engines (eye tracker, voice recognizer, Gemini bridge, system control) and wires their signals to state/UI. This is the hub — read it first to understand data flow.
- `app/vision/` — `landmark_engine.py` (MediaPipe FaceLandmarker: iris, head pose, blink score) → `head_mapper.py` (head-pose-to-cursor + corner magnet, default mode) / `gaze_mapper.py` (experimental eye-mode, ridge regression, needs calibration) → `eye_tracker.py` (capture thread) → `filters.py` (One Euro filter for jitter).
- `app/voice/` — two-tier command pipeline: `commands.py` (offline Turkish grammar/fuzzy match + intents) tried first; on no match, `AppController._on_unmatched` sends text to Gemini for an action plan (`assist/gemini_client.py`, max 6 steps, whitelisted intent types only — dangerous requests never reach the model). `whisper_recognizer.py` (faster-whisper, preferred, higher accuracy) vs `recognizer.py` (Vosk fallback, lighter); engine choice in Settings.
- `app/assist/` — `gemini_client.py` (REST, chat + intent-plan modes), `reader.py` (dwell-triggered screen OCR → TTS "Otomatik Sesli Okuma"), `tts.py`, `config.py` (loads/saves `config.json`, gitignored, holds the Gemini API key — never commit it).
- `app/control/system_control.py` — mouse/keyboard/app-launch. Keyboard and X11 mouse go through pynput; on Wayland (`wayland_limited`), mouse/click transparently switch to `uinput_mouse.py` (`using_uinput`) if `/dev/uinput` is writable, else stay degraded. `real_mouse_watch.py` watches the real hardware mouse device's raw REL events directly (can't read the compositor's cursor position back on Wayland) so `AppController._on_gaze` can detect "user grabbed the real mouse" and pause gaze-driven movement — same purpose as the position-diff check used on the X11/pynput path.
- `app/ui/` — `main_window.py` (sidebar + page stack), `pages/` (dashboard, eye, voice, assist, settings, help), `widgets/`, `overlay/` (fullscreen gaze cursor + calibration overlay).

Click safety model (see README for full detail): head pose is measured from a cheek-frame region unaffected by facial expressions, so blinking/talking never jitters the cursor; gesture-click freezes the cursor the instant a gesture signal rises; click lands on the aim point from 0.35s *before* the gesture started (rewind buffer), not where the cursor drifted to mid-blink.

## Conventions

- No comments unless explaining non-obvious *why*; existing docstrings/comments are Turkish — match that when touching this code.
- Never write to `config.json` or `models/` in commits — both gitignored (API key, downloaded Vosk model).
- Keep new optional-dependency code behind `_have("modname")` lazy-import checks like the rest of the codebase, so missing libs degrade a feature rather than crashing startup.
