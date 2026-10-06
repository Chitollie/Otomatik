import json
import os
from pathlib import Path

APP_NAME = "Otomatik"
APP_VERSION = "1.1.1"

GITHUB_OWNER = "Chitollie"
GITHUB_REPO = "Otomatik"
GITHUB_BRANCH = "main"
GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"

DISCORD_CLIENT_ID = "1554182013466972231"
DISCORD_REDIRECT_URI = "http://127.0.0.1:8765/callback"
DISCORD_ADMIN_ID = "765306791093076058"

DEFAULT_SETTINGS = {
    "ref_w": 1920,
    "ref_h": 1080,
    "roi_x": 1082,
    "roi_y": 245,
    "roi_w": 40,
    "roi_h": 592,
    "hold_duration": 4.0,
    "bite_timeout": 120.0,
    "minigame_timeout": 60.0,
    "minigame_end_delay": 0.6,
    "scan_interval": 0.01,
    "recast_min": 0.5,
    "recast_max": 2.0,
    "green_min": 0.005,
    "cast_key": "e",
    "catch_key": "space",
    "pause_key": "f8",
    "afk_minutes": 20,
}


def data_dir():
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    folder = Path(base) / APP_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_path():
    return data_dir() / "settings.json"


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        saved = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings

    for key, default in DEFAULT_SETTINGS.items():
        if key not in saved:
            continue
        try:
            settings[key] = type(default)(saved[key])
        except (TypeError, ValueError):
            pass
    return settings


def save_settings(settings):
    try:
        settings_path().write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass
