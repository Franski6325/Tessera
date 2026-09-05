"""CPU from /proc/cpuinfo and /sys/devices/system/cpu."""

from __future__ import annotations

import platform
import re

from tessera.detect._io import list_dir, note, read_int, read_text
from tessera.models import CpuInfo, ProbeNote

_VIRT_FLAGS = ("vmx", "svm", "hypervisor")


def detect_cpu() -> CpuInfo:
    notes: list[ProbeNote] = []
    cpuinfo = read_text("/proc/cpuinfo", default="") or ""
    if not cpuinfo:
        notes.append(note("cpu.proc", "/proc/cpuinfo illeggibile.", "error"))
    blocks = [b for b in cpuinfo.split("\n\n") if b.strip()]
    fields: dict[str, str] = {}
    if blocks:
        for line in blocks[0].splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            fields[k.strip().lower()] = v.strip()

    model = fields.get("model name") or fields.get("cpu") or fields.get("hardware") or platform.processor() or "sconosciuto"
    vendor = fields.get("vendor_id") or fields.get("cpu implementer") or "unknown"
    flags_raw = fields.get("flags") or fields.get("features") or ""
    flags = tuple(sorted(set(flags_raw.split())))
    virt = tuple(f for f in _VIRT_FLAGS if f in flags)

    logical = 0
    phys_ids: set[str] = set()
    core_ids: set[tuple[str, str]] = set()
    for block in blocks:
        local: dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            local[k.strip().lower()] = v.strip()
        if "processor" in local:
            logical += 1
        phys = local.get("physical id", "0")
        core = local.get("core id", local.get("processor", "0"))
        phys_ids.add(phys)
        core_ids.add((phys, core))

    if logical == 0:
        online = read_text("/sys/devices/system/cpu/online", default="0") or "0"
        logical = _parse_cpu_range(online)
        if logical == 0:
            logical = len([p for p in list_dir("/sys/devices/system/cpu") if p.name.startswith("cpu") and p.name[3:].isdigit()])
        if logical == 0:
            logical = os_cpu_count()
            notes.append(note("cpu.fallback", "Conteggio core da os.cpu_count().", "info"))

    physical = len(core_ids) if core_ids else max(1, logical)
    tpc = max(1, logical // physical) if physical else 1

    max_mhz = None
    mhz_text = fields.get("cpu mhz")
    if mhz_text:
        try:
            max_mhz = float(mhz_text)
        except ValueError:
            max_mhz = None
    freq = read_int("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")
    if freq:
        max_mhz = freq / 1000.0

    arch = platform.machine() or "unknown"
    return CpuInfo(
        model=re.sub(r"\s+", " ", model).strip(),
        vendor=vendor,
        cores_logical=logical,
        cores_physical=physical,
        threads_per_core=tpc,
        max_mhz=max_mhz,
        flags=flags,
        arch=arch,
        virtualization_flags=virt,
        notes=tuple(notes),
    )


def _parse_cpu_range(spec: str) -> int:
    total = 0
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                total += int(b) - int(a) + 1
            except ValueError:
                continue
        else:
            try:
                int(part)
                total += 1
            except ValueError:
                continue
    return total


def os_cpu_count() -> int:
    import os

    return os.cpu_count() or 1
