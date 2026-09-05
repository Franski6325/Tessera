"""XDG-aware locations. Never write outside these without an explicit plan path."""

from __future__ import annotations

import os
from pathlib import Path


def _xdg(env: str, fallback: Path) -> Path:
    raw = os.environ.get(env)
    if raw:
        return Path(raw).expanduser()
    return fallback


def home() -> Path:
    return Path.home()


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", home() / ".config") / "tessera"


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", home() / ".local" / "share") / "tessera"


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", home() / ".local" / "state") / "tessera"


def cache_dir() -> Path:
    return _xdg("XDG_CACHE_HOME", home() / ".cache") / "tessera"


def journal_dir() -> Path:
    return state_dir() / "journal"


def plans_dir() -> Path:
    return data_dir() / "plans"


def ensure_layout() -> None:
    for path in (config_dir(), data_dir(), state_dir(), cache_dir(), journal_dir(), plans_dir()):
        path.mkdir(parents=True, exist_ok=True)
