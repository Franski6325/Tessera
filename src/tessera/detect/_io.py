"""Safe reads of /proc, /sys and small command outputs. Never raise past the probe boundary."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from tessera.exceptions import ProbeError
from tessera.models import ProbeNote

SYS = Path("/sys")
PROC = Path("/proc")


def read_text(path: Path | str, *, default: str | None = None, max_bytes: int = 1_000_000) -> str | None:
    p = Path(path)
    try:
        data = p.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace").strip()
    except FileNotFoundError:
        return default
    except PermissionError:
        if default is not None:
            return default
        raise ProbeError(
            f"Permesso negato su {p}",
            code="probe.eacces",
            hint="Alcuni nodi DMI richiedono root. Tessera continua con i dati pubblici.",
        )
    except OSError as exc:
        if default is not None:
            return default
        raise ProbeError(f"Lettura fallita {p}: {exc}", code="probe.io") from exc


def read_int(path: Path | str, default: int | None = None) -> int | None:
    raw = read_text(path, default=None)
    if raw is None:
        return default
    try:
        return int(raw.split()[0])
    except (ValueError, IndexError):
        return default


def first_existing(paths: Iterable[Path | str]) -> Path | None:
    for item in paths:
        p = Path(item)
        if p.exists():
            return p
    return None


def which(name: str) -> str | None:
    return shutil.which(name)


def run(
    args: list[str],
    *,
    timeout: float = 8.0,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except FileNotFoundError as exc:
        raise ProbeError(f"Comando assente: {args[0]}", code="probe.cmd") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError(f"Timeout su {' '.join(args)}", code="probe.timeout") from exc
    except OSError as exc:
        raise ProbeError(f"Esecuzione fallita {' '.join(args)}: {exc}", code="probe.exec") from exc


def try_run(args: list[str], *, timeout: float = 8.0) -> str | None:
    if not which(args[0]) and not str(args[0]).startswith("/"):
        return None
    try:
        proc = run(args, timeout=timeout)
    except ProbeError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def list_dir(path: Path | str) -> list[Path]:
    p = Path(path)
    try:
        return sorted(p.iterdir())
    except (FileNotFoundError, PermissionError, OSError):
        return []


def note(code: str, message: str, level: str = "warning", hint: str | None = None) -> ProbeNote:
    return ProbeNote(code=code, message=message, level=level, hint=hint)


def redact_serial(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.lower() in {"none", "not specified", "to be filled by o.e.m.", "default string"}:
        return None
    if len(value) <= 4:
        return "***"
    return value[:2] + "…" + value[-2:]
