"""RAM and swap from /proc/meminfo."""

from __future__ import annotations

from tessera.detect._io import note, read_text
from tessera.models import MemoryInfo, ProbeNote


def _kib(meminfo: dict[str, int], *keys: str) -> int:
    for key in keys:
        if key in meminfo:
            return meminfo[key] * 1024
    return 0


def detect_memory() -> MemoryInfo:
    notes: list[ProbeNote] = []
    raw = read_text("/proc/meminfo", default="") or ""
    parsed: dict[str, int] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        num = rest.strip().split()[0]
        try:
            parsed[key] = int(num)
        except ValueError:
            continue
    if not parsed:
        notes.append(note("mem.proc", "/proc/meminfo illeggibile.", "error"))
    total = _kib(parsed, "MemTotal")
    available = _kib(parsed, "MemAvailable", "MemFree")
    swap = _kib(parsed, "SwapTotal")
    if total and available / total < 0.08:
        notes.append(note("mem.pressure", "Poca RAM libera: meglio un profilo bilanciato o a risparmio.", "warning"))
    if total and total < 2 * 1024**3:
        notes.append(note("mem.low", "Meno di 2 GiB: alcuni stack developer/cyber pesanti non ci stanno.", "warning"))
    return MemoryInfo(total_bytes=total, available_bytes=available, swap_bytes=swap, notes=tuple(notes))
