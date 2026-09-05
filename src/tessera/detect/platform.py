"""DMI chassis and USB / audio / thermals / virtualization."""

from __future__ import annotations

from pathlib import Path

from tessera.detect._io import list_dir, note, read_int, read_text, redact_serial
from tessera.models import (
    AudioDevice,
    ChassisKind,
    DmiInfo,
    ProbeNote,
    ThermalZone,
    UsbDevice,
    VirtInfo,
)

_CHASSIS = {
    "1": ChassisKind.UNKNOWN,
    "3": ChassisKind.DESKTOP,
    "4": ChassisKind.DESKTOP,
    "5": ChassisKind.DESKTOP,
    "6": ChassisKind.DESKTOP,
    "7": ChassisKind.DESKTOP,
    "8": ChassisKind.LAPTOP,
    "9": ChassisKind.LAPTOP,
    "10": ChassisKind.LAPTOP,
    "11": ChassisKind.LAPTOP,
    "14": ChassisKind.LAPTOP,
    "30": ChassisKind.CONVERTIBLE,
    "31": ChassisKind.CONVERTIBLE,
    "32": ChassisKind.CONVERTIBLE,
    "17": ChassisKind.SERVER,
    "23": ChassisKind.SERVER,
}


def detect_dmi() -> DmiInfo:
    base = Path("/sys/class/dmi/id")
    if not base.exists():
        base = Path("/sys/devices/virtual/dmi/id")

    def grab(name: str) -> str | None:
        return read_text(base / name, default=None)

    serial = redact_serial(grab("product_serial"))
    return DmiInfo(
        vendor=grab("sys_vendor"),
        product=grab("product_name"),
        version=grab("product_version"),
        serial_redacted=serial,
        board_vendor=grab("board_vendor"),
        board_name=grab("board_name"),
        bios_vendor=grab("bios_vendor"),
        bios_version=grab("bios_version"),
        chassis_type=grab("chassis_type"),
    )


def classify_chassis(dmi: DmiInfo, virt: VirtInfo, battery_present: bool) -> ChassisKind:
    if virt.is_container:
        return ChassisKind.CONTAINER
    if virt.is_vm or virt.wsl:
        return ChassisKind.VM
    if dmi.chassis_type and dmi.chassis_type in _CHASSIS:
        kind = _CHASSIS[dmi.chassis_type]
        if kind != ChassisKind.UNKNOWN:
            return kind
    if battery_present:
        return ChassisKind.LAPTOP
    product = (dmi.product or "").lower()
    if any(x in product for x in ("raspberry", "rockchip", "orangepi", "pine64")):
        return ChassisKind.EMBEDDED
    return ChassisKind.DESKTOP


def detect_usb() -> tuple[UsbDevice, ...]:
    devices: list[UsbDevice] = []
    for path in list_dir("/sys/bus/usb/devices"):
        if not (path / "idVendor").exists():
            continue
        vid = read_text(path / "idVendor", default="") or ""
        pid = read_text(path / "idProduct", default="") or ""
        name = (
            read_text(path / "product", default=None)
            or read_text(path / "manufacturer", default=None)
            or f"{vid}:{pid}"
        )
        devices.append(UsbDevice(bus=path.name, vid=vid, pid=pid, name=name.strip()))
    return tuple(devices[:80])


def detect_audio() -> tuple[AudioDevice, ...]:
    devices: list[AudioDevice] = []
    for path in list_dir("/sys/class/sound"):
        if not path.name.startswith("card"):
            continue
        name = read_text(path / "id", default=path.name) or path.name
        devices.append(AudioDevice(name=name, sysfs=str(path)))
    return tuple(devices)


def detect_thermals() -> tuple[ThermalZone, ...]:
    zones: list[ThermalZone] = []
    for path in list_dir("/sys/class/thermal"):
        if not path.name.startswith("thermal_zone"):
            continue
        typ = read_text(path / "type", default=path.name) or path.name
        milli = read_int(path / "temp")
        celsius = milli / 1000.0 if milli is not None and milli > 0 else None
        zones.append(ThermalZone(name=typ, celsius=celsius))
    return tuple(zones)


def detect_virt() -> VirtInfo:
    notes: list[ProbeNote] = []
    is_container = False
    runtime = None
    if Path("/.dockerenv").exists():
        is_container, runtime = True, "docker"
    if Path("/run/.containerenv").exists():
        is_container, runtime = True, "podman"
    cg = read_text("/proc/1/cgroup", default="") or ""
    if "docker" in cg or "containerd" in cg:
        is_container, runtime = True, runtime or "cgroup-container"
    if (read_text("/proc/1/environ", default="") or "").find("container=") >= 0:
        is_container = True
        runtime = runtime or "pid1-env"

    cpuinfo = (read_text("/proc/cpuinfo", default="") or "").lower()
    hypervisor = None
    is_vm = "hypervisor" in cpuinfo
    dmi_vendor = (read_text("/sys/class/dmi/id/sys_vendor", default="") or "").lower()
    product = (read_text("/sys/class/dmi/id/product_name", default="") or "").lower()
    for name in ("kvm", "qemu", "vmware", "virtualbox", "xen", "hyper-v", "microsoft", "bhyve", "parallels"):
        if name in dmi_vendor or name in product:
            is_vm = True
            hypervisor = name
            break
    if Path("/proc/xen").exists():
        is_vm, hypervisor = True, "xen"
    wsl = "microsoft" in (read_text("/proc/version", default="") or "").lower() or Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists()
    if wsl:
        is_vm = True
        hypervisor = hypervisor or "wsl"

    live = False
    mounts = read_text("/proc/mounts", default="") or ""
    if "overlay" in mounts and ("casper" in mounts or "live" in mounts or "squashfs" in mounts):
        live = True
        notes.append(note("virt.live", "Sembra una sessione live USB: non applicare hardening persistente.", "warning"))

    if is_container:
        notes.append(note("virt.container", "Ambiente container: molti sysctl e il firewall dell'host non sono applicabili.", "warning"))
    if wsl:
        notes.append(note("virt.wsl", "WSL: GPU e systemd possono essere parziali.", "info"))

    return VirtInfo(
        is_container=is_container,
        is_vm=is_vm,
        container_runtime=runtime,
        hypervisor=hypervisor,
        wsl=wsl,
        live_usb=live,
        notes=tuple(notes),
    )
