"""Configuration loading: env vars > .env file > QSettings > defaults."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings

ORG = "Shard"
APP = "Shard"

KEYS = ("SHARD_API_HOST", "SHARD_API_PORT", "SHARD_API_TOKEN", "SHARD_SAVE_DIR")


def _default_save_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") \
        or str(Path.home())
    return str(Path(base) / "Shard" / "workers")


DEFAULTS = {
    "SHARD_API_HOST": "127.0.0.1",
    "SHARD_API_PORT": "8765",
    "SHARD_API_TOKEN": "",
    "SHARD_SAVE_DIR": _default_save_dir(),
}


def _load_dotenv() -> None:
    """Tiny .env loader (no external dep). Does not overwrite real env vars."""
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
        except OSError:
            pass


def load_settings() -> dict[str, str]:
    """Resolve config from env > .env > QSettings > defaults, and seed os.environ."""
    _load_dotenv()
    s = QSettings(ORG, APP)
    out: dict[str, str] = {}
    for key in KEYS:
        val = os.environ.get(key) or str(s.value(key, "") or "") or DEFAULTS.get(key, "")
        out[key] = val
        if val:
            os.environ[key] = val
    return out


def save_settings(values: dict[str, str]) -> None:
    s = QSettings(ORG, APP)
    for k, v in values.items():
        if k in KEYS:
            s.setValue(k, v)
    s.sync()
    for k, v in values.items():
        if k in KEYS and v:
            os.environ[k] = v
