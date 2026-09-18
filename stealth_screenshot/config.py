"""Configuration loader for stealth-screenshot."""

import json
import os
from typing import Any

DEFAULT_CONFIG = {
    "hotkey": "ctrl+alt+q",
    "quit_hotkey": "ctrl+alt+shift+q",
    "tray_icon": False,
}

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def load_config() -> dict[str, Any]:
    """Load config.json from the project root, falling back to defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.isfile(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            cfg.update(user_cfg)
        except (json.JSONDecodeError, OSError):
            pass  # fall back to defaults
    return cfg
