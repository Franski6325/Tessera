"""Deterministic scoring. Same hardware snapshot always yields the same recommendation."""

from __future__ import annotations

from tessera.models import (
    ChassisKind,
    HardwareSnapshot,
    PowerProfile,
    Recommendation,
    RoleId,
    ScoreBreakdown,
    SecurityLevel,
)


def recommend(snapshot: HardwareSnapshot) -> Recommendation:
    scores = {p: 0 for p in PowerProfile}
    reasons: dict[PowerProfile, list[str]] = {p: [] for p in PowerProfile}

    def add(profile: PowerProfile, pts: int, why: str) -> None:
        scores[profile] += pts
        reasons[profile].append(f"{why} ({pts:+d})")

    # Baseline: balanced is the safe default on unknown hosts.
    add(PowerProfile.BALANCED, 40, "Punto di partenza conservativo")

    laptop = snapshot.chassis in {ChassisKind.LAPTOP, ChassisKind.CONVERTIBLE}
    if laptop:
        add(PowerProfile.BATTERY, 28, "Telaio portatile")
        add(PowerProfile.BALANCED, 8, "Portatile: il bilanciato resta valido")
        add(PowerProfile.QUIET, 10, "Portatile: rumore e termica contano")
    elif snapshot.chassis == ChassisKind.DESKTOP:
        add(PowerProfile.PERFORMANCE, 18, "Desktop senza vincolo batteria")
        add(PowerProfile.BATTERY, -25, "Nessuna batteria da conservare")
    elif snapshot.chassis == ChassisKind.SERVER:
        add(PowerProfile.SERVER, 35, "Telaio server")
        add(PowerProfile.PERFORMANCE, 10, "Server: throughput")
        add(PowerProfile.BATTERY, -40, "Irrilevante su server")
    elif snapshot.chassis in {ChassisKind.VM, ChassisKind.CONTAINER}:
        add(PowerProfile.BALANCED, 12, "Ospite virtuale: evita governor aggressivi sull'host")
        add(PowerProfile.PERFORMANCE, -8, "La CPU è condivisa con l'hypervisor")
        add(PowerProfile.SERVER, 6, "Spesso headless")

    if snapshot.battery.present:
        cap = snapshot.battery.capacity_percent
        add(PowerProfile.BATTERY, 12, "Batteria presente")
        if cap is not None and cap < 25:
            add(PowerProfile.BATTERY, 20, f"Carica al {cap}%")
            add(PowerProfile.PERFORMANCE, -20, "Carica bassa")
        if snapshot.battery.status and snapshot.battery.status.lower() == "discharging":
            add(PowerProfile.BATTERY, 10, "In scarica")
    else:
        add(PowerProfile.BATTERY, -30, "Nessuna batteria")

    ram = snapshot.memory.total_gib
    cores = snapshot.cpu.cores_logical
    if ram >= 32 and cores >= 12 and snapshot.gpu.has_discrete:
        add(PowerProfile.PERFORMANCE, 24, f"Macchina potente ({cores} thread, {ram:.0f} GiB, GPU discreta)")
    elif ram >= 16 and cores >= 8:
        add(PowerProfile.PERFORMANCE, 10, "Risorse medio-alte")
        add(PowerProfile.BALANCED, 6, "Ancora adatta al bilanciato")
    elif ram < 8:
        add(PowerProfile.BALANCED, 8, "RAM contenuta")
        add(PowerProfile.PERFORMANCE, -12, "Poca RAM per un profilo performance")
        add(PowerProfile.BATTERY, 6, "Meno turbo = meno pressione memoria/termica")

    if snapshot.gpu.has_discrete and not laptop:
        add(PowerProfile.PERFORMANCE, 8, "GPU discreta su macchina fissa")
    if snapshot.gpu.has_discrete and laptop:
        add(PowerProfile.BALANCED, 6, "iGPU+dGPU: il bilanciato evita il dreno")
        add(PowerProfile.BATTERY, 8, "Su portatile la dGPU va usata a comando")

    hot = any(z.celsius is not None and z.celsius >= 85 for z in snapshot.thermals)
    warm = any(z.celsius is not None and z.celsius >= 75 for z in snapshot.thermals)
    if hot:
        add(PowerProfile.QUIET, 28, "Termiche alte (≥85°C)")
        add(PowerProfile.PERFORMANCE, -22, "Turbo sconsigliato a caldo")
        add(PowerProfile.BATTERY, 8, "Ridurre il TDP")
    elif warm:
        add(PowerProfile.QUIET, 12, "Termiche elevate")
        add(PowerProfile.BALANCED, 6, "Meglio non spingere")

    rotational = any(d.rotational and not d.removable for d in snapshot.storage.devices)
    if rotational:
        add(PowerProfile.QUIET, 6, "HDD meccanico: meno seek da carico")
        add(PowerProfile.SERVER, 4, "I/O da calibrare")

    if snapshot.virt.live_usb:
        add(PowerProfile.BALANCED, 15, "Live USB: niente tuning persistente aggressivo")
        add(PowerProfile.PERFORMANCE, -10, "Live: persistenza limitata")

    if snapshot.cpu.arch.startswith(("aarch64", "arm")):
        add(PowerProfile.BATTERY, 8, "SoC ARM: il risparmio è il default sano")
        add(PowerProfile.QUIET, 6, "Fanless / passivo frequente")

    # Security recommendation (deterministic, independent of roles).
    security = SecurityLevel.STANDARD
    sec_why = ["Standard: firewall in ingresso chiuso, aggiornamenti, password sane."]
    if snapshot.storage.root_encrypted:
        sec_why.append("Root già su disco cifrato: si può salire a raffreddato/fortezza senza LUKS distruttivo.")
        security = SecurityLevel.HARDENED
    elif snapshot.chassis in {ChassisKind.LAPTOP, ChassisKind.CONVERTIBLE}:
        sec_why.append("Portatile: Fortezza è consigliata (cifratura, schermo lock, USB).")
        security = SecurityLevel.HARDENED
    if snapshot.virt.is_vm or snapshot.virt.is_container:
        security = SecurityLevel.STANDARD
        sec_why.append("Virtualizzato: alcune protezioni kernel restano all'host.")
    if snapshot.virt.live_usb:
        security = SecurityLevel.RELAXED
        sec_why.append("Live: applica solo regole volatile, non cifratura del disco live.")

    # Role hints — not auto-selected, only suggestions.
    role_hint: list[RoleId] = [RoleId.DAILY]
    if snapshot.distro.id == "kali" or "blackarch" in snapshot.distro.id_like:
        role_hint.append(RoleId.CYBER)
    if ram >= 8 and cores >= 4:
        role_hint.append(RoleId.DEVELOPER)
    if snapshot.chassis == ChassisKind.SERVER or snapshot.virt.is_vm:
        role_hint.append(RoleId.OPS)

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0].value))
    winner = ranked[0][0]
    breakdown = tuple(
        ScoreBreakdown(profile=p, score=s, reasons=tuple(reasons[p])) for p, s in ranked
    )
    rationale = tuple(reasons[winner] + sec_why)
    return Recommendation(
        power=winner,
        scores=breakdown,
        security=security,
        roles_hint=tuple(dict.fromkeys(role_hint)),
        rationale=rationale,
    )
