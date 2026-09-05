"""GPUs from DRM sysfs and PCI class 03xx. No vendor SDK required."""

from __future__ import annotations

import re
from pathlib import Path

from tessera.detect._io import list_dir, note, read_int, read_text
from tessera.models import GpuDevice, GpuInfo, ProbeNote

_VENDOR = {
    "0x10de": "NVIDIA",
    "0x1002": "AMD",
    "0x1022": "AMD",
    "0x8086": "Intel",
    "0x1a03": "ASPEED",
    "0x1414": "Microsoft",
    "0x15ad": "VMware",
    "0x1234": "QEMU",
    "0x1af4": "Virtio",
}

_IGPU_HINTS = ("uhd", "iris", "radeon graphics", "vega", "integrated", "qxl", "virtio", "vmware", "aspeed")


def _pci_name(uevent: dict[str, str], vendor_id: str, device_id: str) -> str:
    driver = uevent.get("DRIVER") or ""
    vendor = _VENDOR.get(vendor_id.lower(), vendor_id)
    return f"{vendor} {device_id} {driver}".strip()


def _parse_uevent(path: Path) -> dict[str, str]:
    raw = read_text(path, default="") or ""
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k] = v
    return data


def detect_gpu() -> GpuInfo:
    notes: list[ProbeNote] = []
    devices: list[GpuDevice] = []
    seen: set[str] = set()
    pci_devs = list_dir("/sys/bus/pci/devices")
    index = 0
    for dev in pci_devs:
        class_code = (read_text(dev / "class", default="") or "").lower()
        # Display controllers: 0x030000 VGA, 0x030200 3D, 0x038000 other
        if not class_code.startswith("0x03"):
            continue
        uevent = _parse_uevent(dev / "uevent")
        vendor_id = read_text(dev / "vendor", default="") or uevent.get("PCI_ID", ":").split(":")[0]
        device_id = read_text(dev / "device", default="") or ""
        pci_id = uevent.get("PCI_SLOT_NAME") or dev.name
        if pci_id in seen:
            continue
        seen.add(pci_id)
        driver = None
        driver_link = dev / "driver"
        try:
            if driver_link.exists():
                driver = driver_link.resolve().name
        except OSError:
            driver = uevent.get("DRIVER")
        vendor_name = _VENDOR.get((vendor_id or "").lower(), vendor_id or "unknown")
        # Try a human name from drm
        name = _friendly_name(dev, vendor_name, device_id, driver)
        discrete = _is_discrete(name, vendor_name, class_code)
        vram = _vram_bytes(dev)
        devices.append(
            GpuDevice(
                index=index,
                vendor=vendor_name,
                name=name,
                driver=driver,
                pci_id=pci_id,
                discrete=discrete,
                vram_bytes=vram,
            )
        )
        index += 1

    if not devices:
        # drm cards without PCI (SoC / Raspberry)
        for card in list_dir("/sys/class/drm"):
            if not re.fullmatch(r"card\d+", card.name):
                continue
            label = read_text(card / "device" / "uevent", default="") or card.name
            devices.append(
                GpuDevice(
                    index=len(devices),
                    vendor="SoC",
                    name=label.split("\n")[0][:80],
                    driver=None,
                    pci_id=None,
                    discrete=False,
                )
            )
        if not devices:
            notes.append(note("gpu.none", "Nessuna GPU visibile in sysfs (headless, permessi o driver assente).", "info"))

    return GpuInfo(devices=tuple(devices), notes=tuple(notes))


def _friendly_name(dev: Path, vendor: str, device_id: str, driver: str | None) -> str:
    for candidate in (
        dev / "label",
        *[p for p in list_dir(Path("/sys/class/drm")) if (p / "device").exists()],
    ):
        pass
    modalias = read_text(dev / "modalias", default="") or ""
    bits = [vendor]
    if device_id:
        bits.append(device_id)
    if driver:
        bits.append(f"({driver})")
    if "pci:" in modalias:
        bits.append(modalias.split("pci:")[-1][:24])
    return " ".join(bits)


def _is_discrete(name: str, vendor: str, class_code: str) -> bool:
    lowered = name.lower()
    if any(h in lowered for h in _IGPU_HINTS):
        return False
    if vendor in {"QEMU", "VMware", "Virtio", "Microsoft", "ASPEED"}:
        return False
    # 3D controller class is almost always a discrete NVIDIA/AMD
    if class_code.startswith("0x0302"):
        return True
    if vendor in {"NVIDIA"}:
        return True
    if vendor == "AMD" and "radeon graphics" not in lowered:
        return True
    return False


def _vram_bytes(dev: Path) -> int | None:
    for rel in (
        "mem_info_vram_total",
        "drm/card0/device/mem_info_vram_total",
    ):
        value = read_int(dev / rel)
        if value:
            return value
    # NVIDIA sysfs often exposes none without nvidia-smi; we do not call proprietary tools.
    return None
