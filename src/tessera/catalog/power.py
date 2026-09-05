"""Power-profile actions: governors, TLP, tuned, NVIDIA/AMD hints — never proprietary blobs forced."""

from __future__ import annotations

from dataclasses import dataclass

from tessera.models import DistroFamily, HardwareSnapshot, PowerProfile


@dataclass(frozen=True)
class PowerAction:
    id: str
    title: str
    sysctl: dict[str, str] | None = None
    packages: tuple[str, ...] = ()
    notes: str = ""


def actions_for(profile: PowerProfile, snapshot: HardwareSnapshot) -> tuple[PowerAction, ...]:
    family = snapshot.distro.family
    laptop = snapshot.battery.present
    out: list[PowerAction] = []

    if profile == PowerProfile.PERFORMANCE:
        out.append(
            PowerAction(
                "cpu_perf",
                "Governor performance (cpu0..n)",
                notes="Scrive /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor se esiste.",
            )
        )
        if laptop:
            out.append(PowerAction("tlp_ac", "TLP: AC come performance se TLP è il stack", packages=_tlp(family)))
        if family in {DistroFamily.FEDORA, DistroFamily.RHEL}:
            out.append(PowerAction("tuned_tput", "tuned-adm profile throughput-performance", packages=("tuned",)))
    elif profile == PowerProfile.BATTERY:
        out.append(PowerAction("cpu_powersave", "Governor powersave / conservative"))
        if laptop:
            out.append(PowerAction("tlp_bat", "Installa TLP e abilita il servizio", packages=_tlp(family)))
        out.append(
            PowerAction(
                "sata_alpm",
                "ALPM med_power_with_dipm sui SATA se supportato",
                notes="Saltato su NVMe-only.",
            )
        )
        if snapshot.gpu.has_discrete and laptop:
            out.append(
                PowerAction(
                    "dgpu_hint",
                    "Suggerisci hybrid graphics (supergfxctl / envycontrol / kernel iGPU) — nessuna installazione forzata",
                    notes="Tessera non scarica blob NVIDIA proprietari senza una scelta esplicita nel piano pacchetti.",
                )
            )
    elif profile == PowerProfile.QUIET:
        out.append(PowerAction("cpu_schedutil", "Governor schedutil / powersave"))
        out.append(PowerAction("thermald", "thermald se Intel e presente", packages=_thermald(family)))
    elif profile == PowerProfile.SERVER:
        out.append(PowerAction("cpu_ondemand", "Governor ondemand / schedutil"))
        if family in {DistroFamily.FEDORA, DistroFamily.RHEL}:
            out.append(PowerAction("tuned_server", "tuned-adm profile balanced-server", packages=("tuned",)))
    else:  # balanced
        out.append(PowerAction("cpu_schedutil", "Governor schedutil (default kernel moderno)"))
        if laptop:
            out.append(PowerAction("tlp_balanced", "TLP con default vendor", packages=_tlp(family)))

    return tuple(out)


def _tlp(family: DistroFamily) -> tuple[str, ...]:
    if family in {DistroFamily.DEBIAN, DistroFamily.UBUNTU, DistroFamily.KALI}:
        return ("tlp", "tlp-rdw")
    if family == DistroFamily.ARCH:
        return ("tlp",)
    if family in {DistroFamily.FEDORA, DistroFamily.RHEL, DistroFamily.SUSE}:
        return ("tlp",)
    return ()


def _thermald(family: DistroFamily) -> tuple[str, ...]:
    if family in {DistroFamily.DEBIAN, DistroFamily.UBUNTU, DistroFamily.KALI, DistroFamily.FEDORA, DistroFamily.ARCH}:
        return ("thermald",)
    return ()
