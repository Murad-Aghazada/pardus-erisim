"""Yerel yapılandırma — config.json (repoya girmez, .gitignore'da)."""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "config.json")

_DEFAULTS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "speak_replies": True,
}


def load() -> dict:
    data = dict(_DEFAULTS)
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except (OSError, ValueError):
        pass
    # ortam değişkeni her zaman öncelikli
    env = os.environ.get("GEMINI_API_KEY")
    if env:
        data["gemini_api_key"] = env
    return data


def save(updates: dict) -> None:
    data = load()
    data.update(updates)
    try:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
