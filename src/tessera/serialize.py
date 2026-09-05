"""JSON-safe dump helpers."""

from __future__ import annotations

import json
from typing import Any

from tessera.models import to_dict


def dumps(obj: Any) -> str:
    return json.dumps(to_dict(obj), indent=2, ensure_ascii=False, default=str)
