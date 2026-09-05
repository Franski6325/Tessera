"""Factory of deterministic HardwareSnapshot objects for tests."""

from __future__ import annotations

from tessera.models import (
    BatteryInfo,
    ChassisKind,
    CpuInfo,
    DistroFamily,
    DistroInfo,
    DmiInfo,
    GpuDevice,
    GpuInfo,
    HardwareSnapshot,
    ManagerKind,
    ManagerStatus,
    MemoryInfo,
    NetIface,
    NetworkInfo,
    StorageDevice,
    StorageInfo,
    ThermalZone,
    VirtInfo,
)


def snap(
    *,
    chassis: ChassisKind = ChassisKind.LAPTOP,
    ram_gib: float = 16,
    cores: int = 8,
    battery: bool = True,
    cap: int | None = 70,
    discrete: bool = False,
    hot: bool = False,
    encrypted: bool = False,
    family: DistroFamily = DistroFamily.ARCH,
    distro_id: str = "endeavouros",
    live: bool = False,
    container: bool = False,
    vm: bool = False,
) -> HardwareSnapshot:
    gpu = GpuInfo(
        devices=(
            GpuDevice(0, "Intel", "UHD", "i915", "0000:00:02.0", False),
            *( (GpuDevice(1, "NVIDIA", "RTX", "nvidia", "0000:01:00.0", True),) if discrete else () ),
        )
    )
    return HardwareSnapshot(
        hostname="lab",
        chassis=chassis,
        distro=DistroInfo(
            distro_id,
            ("arch",) if family == DistroFamily.ARCH else ("debian",),
            "Test",
            "1",
            family,
            "Test OS",
            "6.8.0",
            "systemd",
        ),
        cpu=CpuInfo("Test CPU", "GenuineIntel", cores, max(1, cores // 2), 2, 4200.0, ("vmx",), "x86_64", ("vmx",)),
        memory=MemoryInfo(int(ram_gib * 1024**3), int(ram_gib * 0.5 * 1024**3), 0),
        gpu=gpu,
        storage=StorageInfo(
            devices=(
                StorageDevice("nvme0n1", "Samsung", 512_000_000_000, False, "nvme", False, ("/",), "ext4", encrypted),
            ),
            root_encrypted=encrypted,
        ),
        network=NetworkInfo(
            interfaces=(NetIface("wlan0", "aa:bb:cc:dd:ee:ff", ("192.168.1.10/24",), (), True, True, None),),
            hostname="lab",
        ),
        battery=BatteryInfo(battery, "BAT0" if battery else None, "Discharging" if battery else None, cap, None, None),
        dmi=DmiInfo("OEM", "Laptop" if battery else "Desktop", None, None, None, None, None, None, "10" if battery else "3"),
        usb=(),
        audio=(),
        thermals=(ThermalZone("x86_pkg_temp", 90.0 if hot else 45.0),),
        virt=VirtInfo(container, vm, "docker" if container else None, "kvm" if vm else None, False, live),
        managers=(
            ManagerStatus(ManagerKind.PACMAN, True, "6.1", True, False, False, None, ("extra", "multilib")),
            ManagerStatus(ManagerKind.YAY, True, "12", False, True, False, None, ()),
            ManagerStatus(ManagerKind.APT, family in {DistroFamily.DEBIAN, DistroFamily.UBUNTU, DistroFamily.KALI}, "2.7", True, False, False, None, ()),
        ),
        collected_at="2026-01-01T00:00:00+00:00",
    )
