"""Battery and AC from /sys/class/power_supply."""

from __future__ import annotations

from tessera.detect._io import list_dir, note, read_int, read_text
from tessera.models import BatteryInfo, ProbeNote


def detect_battery() -> BatteryInfo:
    notes: list[ProbeNote] = []
    batteries = []
    for path in list_dir("/sys/class/power_supply"):
        typ = (read_text(path / "type", default="") or "").lower()
        if typ != "battery" and not path.name.upper().startswith("BAT"):
            continue
        batteries.append(path)
    if not batteries:
        return BatteryInfo(
            present=False,
            name=None,
            status=None,
            capacity_percent=None,
            energy_full_uwh=None,
            energy_now_uwh=None,
            notes=tuple(notes),
        )
    bat = batteries[0]
    cap = read_int(bat / "capacity")
    status = read_text(bat / "status", default=None)
    full = read_int(bat / "energy_full") or read_int(bat / "charge_full")
    now = read_int(bat / "energy_now") or read_int(bat / "charge_now")
    if cap is not None and cap < 20:
        notes.append(note("bat.low", f"Batteria al {cap}%. Profilo battery consigliato.", "warning"))
    return BatteryInfo(
        present=True,
        name=bat.name,
        status=status,
        capacity_percent=cap,
        energy_full_uwh=full,
        energy_now_uwh=now,
        notes=tuple(notes),
    )
