"""Immutable snapshots of the host, the operator's choices, and the resulting plan."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Iterable


class ChassisKind(str, Enum):
    DESKTOP = "desktop"
    LAPTOP = "laptop"
    CONVERTIBLE = "convertible"
    SERVER = "server"
    VM = "vm"
    CONTAINER = "container"
    EMBEDDED = "embedded"
    UNKNOWN = "unknown"


class PowerProfile(str, Enum):
    PERFORMANCE = "performance"
    BALANCED = "balanced"
    BATTERY = "battery"
    QUIET = "quiet"
    SERVER = "server"


class SecurityLevel(str, Enum):
    RELAXED = "relaxed"
    STANDARD = "standard"
    HARDENED = "hardened"
    FORTRESS = "fortress"
    CUSTOM = "custom"


class RoleId(str, Enum):
    CYBER = "cyber"
    DEVELOPER = "developer"
    OPS = "ops"
    DATA = "data"
    CREATIVE = "creative"
    DAILY = "daily"
    PRIVACY = "privacy"
    SERVER = "server"


class DistroFamily(str, Enum):
    DEBIAN = "debian"
    UBUNTU = "ubuntu"
    KALI = "kali"
    ARCH = "arch"
    FEDORA = "fedora"
    RHEL = "rhel"
    SUSE = "suse"
    ALPINE = "alpine"
    VOID = "void"
    GENTOO = "gentoo"
    NIXOS = "nixos"
    UNKNOWN = "unknown"


class ManagerKind(str, Enum):
    APT = "apt"
    NALA = "nala"
    PACMAN = "pacman"
    YAY = "yay"
    PARU = "paru"
    DNF = "dnf"
    YUM = "yum"
    ZYPPER = "zypper"
    APK = "apk"
    XBPS = "xbps"
    EMERGE = "emerge"
    NIX = "nix"
    FLATPAK = "flatpak"
    SNAP = "snap"
    PIPX = "pipx"


def enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def to_dict(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    return obj


@dataclass(frozen=True)
class ProbeNote:
    code: str
    message: str
    level: str = "warning"  # info | warning | error
    hint: str | None = None


@dataclass(frozen=True)
class CpuInfo:
    model: str
    vendor: str
    cores_logical: int
    cores_physical: int
    threads_per_core: int
    max_mhz: float | None
    flags: tuple[str, ...]
    arch: str
    virtualization_flags: tuple[str, ...]
    notes: tuple[ProbeNote, ...] = ()


@dataclass(frozen=True)
class MemoryInfo:
    total_bytes: int
    available_bytes: int
    swap_bytes: int
    notes: tuple[ProbeNote, ...] = ()

    @property
    def total_gib(self) -> float:
        return self.total_bytes / (1024**3)

    @property
    def available_gib(self) -> float:
        return self.available_bytes / (1024**3)


@dataclass(frozen=True)
class GpuDevice:
    index: int
    vendor: str
    name: str
    driver: str | None
    pci_id: str | None
    discrete: bool
    vram_bytes: int | None = None


@dataclass(frozen=True)
class GpuInfo:
    devices: tuple[GpuDevice, ...]
    notes: tuple[ProbeNote, ...] = ()

    @property
    def has_discrete(self) -> bool:
        return any(d.discrete for d in self.devices)


@dataclass(frozen=True)
class StorageDevice:
    name: str
    model: str
    size_bytes: int
    rotational: bool
    transport: str
    removable: bool
    mountpoints: tuple[str, ...]
    fstype: str | None
    encrypted: bool
    serial: str | None = None


@dataclass(frozen=True)
class StorageInfo:
    devices: tuple[StorageDevice, ...]
    root_encrypted: bool
    notes: tuple[ProbeNote, ...] = ()


@dataclass(frozen=True)
class NetIface:
    name: str
    mac: str | None
    ipv4: tuple[str, ...]
    ipv6: tuple[str, ...]
    wireless: bool
    up: bool
    speed_mbps: int | None


@dataclass(frozen=True)
class NetworkInfo:
    interfaces: tuple[NetIface, ...]
    hostname: str
    notes: tuple[ProbeNote, ...] = ()


@dataclass(frozen=True)
class BatteryInfo:
    present: bool
    name: str | None
    status: str | None
    capacity_percent: int | None
    energy_full_uwh: int | None
    energy_now_uwh: int | None
    notes: tuple[ProbeNote, ...] = ()


@dataclass(frozen=True)
class DmiInfo:
    vendor: str | None
    product: str | None
    version: str | None
    serial_redacted: str | None
    board_vendor: str | None
    board_name: str | None
    bios_vendor: str | None
    bios_version: str | None
    chassis_type: str | None


@dataclass(frozen=True)
class UsbDevice:
    bus: str
    vid: str
    pid: str
    name: str


@dataclass(frozen=True)
class AudioDevice:
    name: str
    sysfs: str


@dataclass(frozen=True)
class ThermalZone:
    name: str
    celsius: float | None


@dataclass(frozen=True)
class VirtInfo:
    is_container: bool
    is_vm: bool
    container_runtime: str | None
    hypervisor: str | None
    wsl: bool
    live_usb: bool
    notes: tuple[ProbeNote, ...] = ()


@dataclass(frozen=True)
class DistroInfo:
    id: str
    id_like: tuple[str, ...]
    name: str
    version: str
    family: DistroFamily
    pretty: str
    kernel: str
    init: str | None
    notes: tuple[ProbeNote, ...] = ()


@dataclass(frozen=True)
class ManagerStatus:
    kind: ManagerKind
    present: bool
    version: str | None
    native: bool
    helper: bool
    locked: bool
    lock_reason: str | None
    extra_repos: tuple[str, ...] = ()
    notes: tuple[ProbeNote, ...] = ()


@dataclass(frozen=True)
class HardwareSnapshot:
    hostname: str
    chassis: ChassisKind
    distro: DistroInfo
    cpu: CpuInfo
    memory: MemoryInfo
    gpu: GpuInfo
    storage: StorageInfo
    network: NetworkInfo
    battery: BatteryInfo
    dmi: DmiInfo
    usb: tuple[UsbDevice, ...]
    audio: tuple[AudioDevice, ...]
    thermals: tuple[ThermalZone, ...]
    virt: VirtInfo
    managers: tuple[ManagerStatus, ...]
    notes: tuple[ProbeNote, ...] = ()
    collected_at: str = ""


@dataclass
class SecurityToggle:
    id: str
    enabled: bool
    locked: bool = False
    reason: str | None = None


@dataclass
class UserChoices:
    power: PowerProfile = PowerProfile.BALANCED
    roles: list[RoleId] = field(default_factory=list)
    security: SecurityLevel = SecurityLevel.STANDARD
    toggles: list[SecurityToggle] = field(default_factory=list)
    selected_packages: list[str] = field(default_factory=list)
    primary_manager: ManagerKind | None = None
    extra_managers: list[ManagerKind] = field(default_factory=list)
    retire_helpers: list[ManagerKind] = field(default_factory=list)
    enable_blackarch: bool = False
    enable_flatpak: bool = False
    dry_run: bool = True
    language: str = "it"


@dataclass(frozen=True)
class ScoreBreakdown:
    profile: PowerProfile
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Recommendation:
    power: PowerProfile
    scores: tuple[ScoreBreakdown, ...]
    security: SecurityLevel
    roles_hint: tuple[RoleId, ...]
    rationale: tuple[str, ...]


@dataclass(frozen=True)
class PlanStep:
    id: str
    title: str
    kind: str  # package | sysctl | firewall | service | file | manager | info
    command: tuple[str, ...]
    privileged: bool
    reversible: bool
    risk: str  # low | medium | high
    notes: str = ""
    skip_if: str | None = None


@dataclass
class ApplyPlan:
    hostname: str
    distro: str
    steps: list[PlanStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    journal_id: str = ""

    def privileged_steps(self) -> Iterable[PlanStep]:
        return [s for s in self.steps if s.privileged]
