"""Build a reversible-ish apply plan from snapshot + choices. No side effects."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from tessera.catalog.packages import by_id, for_roles
from tessera.catalog.power import actions_for
from tessera.catalog.security import CONTROLS
from tessera.models import (
    ApplyPlan,
    DistroFamily,
    HardwareSnapshot,
    ManagerKind,
    PlanStep,
    PowerProfile,
    RoleId,
    UserChoices,
)
from tessera.pkg.query import installed_names
from tessera.pkg.resolve import (
    pick_primary,
    refresh_argv,
    resolve_install,
    retire_helper_argv,
    upgrade_argv,
)


def _sid(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:10]


def build_plan(snapshot: HardwareSnapshot, choices: UserChoices) -> ApplyPlan:
    warnings: list[str] = []
    steps: list[PlanStep] = []
    journal_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if snapshot.virt.live_usb:
        warnings.append("Sessione live: i passi persistenti verranno comunque scritti nello script, ma il disco live potrebbe non tenerli.")
    if snapshot.virt.is_container:
        warnings.append("Container: sysctl, firewall host e governor CPU saranno marcati skip.")
    if snapshot.virt.wsl:
        warnings.append("WSL: systemd/firewall possono non essere disponibili.")

    primary_status = pick_primary(snapshot.managers, choices.primary_manager)
    primary = primary_status.kind if primary_status else None
    extra = tuple(choices.extra_managers)
    family = snapshot.distro.family

    if primary is None:
        warnings.append("Nessun gestore pacchetti utilizzabile: solo file di hardening locali (se non container).")
    else:
        if primary_status and primary_status.locked:
            warnings.append(f"Gestore {primary.value} in lock ({primary_status.lock_reason}). Sblocca prima di applicare.")

        ref = refresh_argv(primary)
        if ref:
            steps.append(
                PlanStep(
                    id=_sid("refresh", primary.value),
                    title=f"Aggiorna indici {primary.value}",
                    kind="package",
                    command=ref,
                    privileged=primary != ManagerKind.PIPX,
                    reversible=True,
                    risk="low",
                )
            )
        up = upgrade_argv(primary)
        if up and not snapshot.virt.live_usb:
            steps.append(
                PlanStep(
                    id=_sid("upgrade", primary.value),
                    title=f"Aggiorna pacchetti già installati ({primary.value})",
                    kind="package",
                    command=up,
                    privileged=True,
                    reversible=False,
                    risk="medium",
                    notes="Upgrade, non dist-upgrade. I pacchetti restano; non si toccano i dati in $HOME.",
                )
            )

    # Retire helpers — after new helper is present in extra/primary
    for helper in choices.retire_helpers:
        try:
            argv = retire_helper_argv(helper)
        except Exception as exc:  # noqa: BLE001
            warnings.append(str(exc))
            continue
        steps.append(
            PlanStep(
                id=_sid("retire", helper.value),
                title=f"Rimuovi solo l'helper {helper.value} (i pacchetti installati restano)",
                kind="manager",
                command=argv,
                privileged=True,
                reversible=True,
                risk="medium" if helper != ManagerKind.SNAP else "high",
                notes=(
                    "yay/paru sono wrapper: i pacchetti AUR restano nel database pacman. "
                    "Non viene usato -Rns, quindi le dipendenze condivise restano."
                ),
            )
        )

    if choices.enable_blackarch and family == DistroFamily.ARCH:
        steps.append(
            PlanStep(
                id=_sid("blackarch"),
                title="Istruzioni repo BlackArch (non esegue strap cieco)",
                kind="info",
                command=("true",),
                privileged=False,
                reversible=True,
                risk="low",
                notes="Esegui solo lo strap ufficiale da blackarch.org dopo aver verificato HTTPS/GPG. Tessera non scarica strap da mirror non verificati.",
            )
        )

    if choices.enable_flatpak and not any(m.kind == ManagerKind.FLATPAK and m.present for m in snapshot.managers):
        if primary:
            from tessera.catalog.packages import Pkg
            from tessera.catalog.packages import n as names
            dummy = Pkg("flatpak", (RoleId.DAILY,), "flatpak", "flatpak", names("flatpak"))
            spec = resolve_install(dummy, family, primary, extra=extra)
            if spec.argv:
                steps.append(
                    PlanStep(
                        id=_sid("flatpak-pkg"),
                        title="Installa flatpak",
                        kind="package",
                        command=spec.argv,
                        privileged=True,
                        reversible=True,
                        risk="low",
                    )
                )
        steps.append(
            PlanStep(
                id=_sid("flathub"),
                title="Aggiungi remote Flathub",
                kind="package",
                command=("flatpak", "remote-add", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"),
                privileged=True,
                reversible=True,
                risk="low",
            )
        )

    # Power
    for action in actions_for(choices.power, snapshot):
        if action.id.startswith("cpu_"):
            gov = {
                "cpu_perf": "performance",
                "cpu_powersave": "powersave",
                "cpu_schedutil": "schedutil",
                "cpu_ondemand": "ondemand",
            }.get(action.id, "schedutil")
            steps.append(
                PlanStep(
                    id=_sid("gov", gov),
                    title=f"Imposta governor CPU → {gov}",
                    kind="file",
                    command=("tessera-internal", "governor", gov),
                    privileged=True,
                    reversible=True,
                    risk="low",
                    skip_if="container" if snapshot.virt.is_container else None,
                    notes=action.notes,
                )
            )
        for pkg_name in action.packages:
            steps.append(
                PlanStep(
                    id=_sid("ppkg", pkg_name),
                    title=f"Pacchetto profilo energetico: {pkg_name}",
                    kind="package",
                    command=_install_raw(primary, pkg_name) if primary else (),
                    privileged=True,
                    reversible=True,
                    risk="low",
                )
            )

    # Security files
    enabled = {t.id: t.enabled for t in choices.toggles}
    for ctrl in CONTROLS:
        if not enabled.get(ctrl.id, False):
            continue
        steps.extend(_security_steps(ctrl.id, snapshot, choices))

    # Packages for roles
    selected = set(choices.selected_packages)
    available = {p.id: p for p in for_roles(choices.roles)}
    already: set[str] = set()
    if primary:
        try:
            already = installed_names(primary)
        except Exception:  # noqa: BLE001
            already = set()

    low_ram = snapshot.memory.total_gib < 8
    for pid in sorted(selected):
        pkg = available.get(pid) or by_id(pid)
        if pkg is None:
            warnings.append(f"Pacchetto catalogo sconosciuto: {pid}")
            continue
        if pkg.heavy and low_ram:
            warnings.append(f"{pkg.id} è pesante per {snapshot.memory.total_gib:.1f} GiB RAM: resta nel piano ma valuta di toglierlo.")
        if not primary:
            warnings.append(f"Salto {pkg.id}: niente gestore.")
            continue
        spec = resolve_install(
            pkg,
            family,
            primary,
            extra=extra,
            enable_blackarch=choices.enable_blackarch,
            enable_flatpak=choices.enable_flatpak or ManagerKind.FLATPAK in extra,
        )
        if spec.via == "missing":
            warnings.append(f"{pkg.id}: {spec.note}")
            steps.append(
                PlanStep(
                    id=_sid("miss", pkg.id),
                    title=f"NON installabile: {pkg.id}",
                    kind="info",
                    command=("true",),
                    privileged=False,
                    reversible=True,
                    risk="low",
                    notes=spec.note,
                )
            )
            continue
        if spec.display_name in already or spec.pkg_id in already:
            steps.append(
                PlanStep(
                    id=_sid("have", pkg.id),
                    title=f"Già presente: {spec.display_name}",
                    kind="info",
                    command=("true",),
                    privileged=False,
                    reversible=True,
                    risk="low",
                )
            )
            continue
        steps.append(
            PlanStep(
                id=_sid("pkg", pkg.id),
                title=f"Installa {spec.display_name} [{spec.via}]",
                kind="package",
                command=spec.argv,
                privileged=spec.manager != ManagerKind.PIPX,
                reversible=True,
                risk="low" if spec.via == "native" else "medium",
                notes=spec.note,
            )
        )

    if choices.power == PowerProfile.BATTERY and not snapshot.battery.present:
        warnings.append("Profilo batteria su macchina senza batteria: verrà applicato solo il governor powersave.")

    if RoleId.CYBER in choices.roles:
        warnings.append(
            "Ruolo cyber: gli strumenti sono per laboratori e perimetri con autorizzazione scritta. "
            "Usarli altrove è illecito."
        )

    return ApplyPlan(
        hostname=snapshot.hostname,
        distro=snapshot.distro.pretty,
        steps=[s for s in steps if s.command],
        warnings=warnings,
        journal_id=journal_id,
    )


def _install_raw(primary: ManagerKind | None, name: str) -> tuple[str, ...]:
    if primary is None:
        return ()
    from tessera.pkg.resolve import _native_install
    from tessera.models import DistroFamily

    try:
        return _native_install(primary, name, DistroFamily.UNKNOWN)
    except Exception:
        return ()


def _security_steps(cid: str, snapshot: HardwareSnapshot, choices: UserChoices) -> list[PlanStep]:
    steps: list[PlanStep] = []
    skip = "container" if snapshot.virt.is_container else None

    if cid == "firewall_inbound_deny":
        steps.append(
            PlanStep(
                id=_sid("fw"),
                title="Firewall: policy ingresso deny + established",
                kind="firewall",
                command=("tessera-internal", "firewall", "baseline"),
                privileged=True,
                reversible=True,
                risk="medium",
                skip_if=skip,
                notes="Preferisce ufw, poi firewalld, poi nft. Non flusha tabelle docker/cni se trovate.",
            )
        )
    if cid == "firewall_allow_ssh":
        steps.append(
            PlanStep(
                id=_sid("fw-ssh"),
                title="Firewall: allow 22/tcp",
                kind="firewall",
                command=("tessera-internal", "firewall", "allow-ssh"),
                privileged=True,
                reversible=True,
                risk="medium",
                skip_if=skip,
            )
        )
    if cid == "unattended_updates":
        steps.append(
            PlanStep(
                id=_sid("unatt"),
                title="Abilita aggiornamenti di sicurezza automatici (se il distro li offre)",
                kind="package",
                command=("tessera-internal", "unattended"),
                privileged=True,
                reversible=True,
                risk="low",
            )
        )
    if cid == "pwquality":
        steps.append(
            PlanStep(
                id=_sid("pwq"),
                title="Installa e configura libpwquality (minlen=12)",
                kind="file",
                command=("tessera-internal", "pwquality"),
                privileged=True,
                reversible=True,
                risk="low",
            )
        )
    if cid == "password_store":
        # actual keepassxc package is selected in the catalog if daily/privacy; still add pass
        steps.append(
            PlanStep(
                id=_sid("pstore"),
                title="Assicura keepassxc e/o pass nel piano pacchetti",
                kind="info",
                command=("true",),
                privileged=False,
                reversible=True,
                risk="low",
                notes="Se non l'hai spuntato in Strumenti, aggiungilo: keepassxc.",
            )
        )
    if cid == "kernel_sysctl":
        steps.append(
            PlanStep(
                id=_sid("sysctl"),
                title="Scrive /etc/sysctl.d/90-tessera-hardening.conf",
                kind="sysctl",
                command=("tessera-internal", "sysctl"),
                privileged=True,
                reversible=True,
                risk="medium",
                skip_if=skip,
            )
        )
    if cid == "apparmor":
        steps.append(
            PlanStep(
                id=_sid("aa"),
                title="Abilita AppArmor se la distro lo usa; non tocca SELinux enforcing",
                kind="service",
                command=("tessera-internal", "apparmor"),
                privileged=True,
                reversible=True,
                risk="medium",
                skip_if=skip,
            )
        )
    if cid == "fail2ban":
        steps.append(
            PlanStep(
                id=_sid("f2b"),
                title="fail2ban con jail sshd",
                kind="service",
                command=("tessera-internal", "fail2ban"),
                privileged=True,
                reversible=True,
                risk="low",
                skip_if=skip,
            )
        )
    if cid == "ssh_hardening":
        steps.append(
            PlanStep(
                id=_sid("ssh"),
                title="sshd: PasswordAuthentication no, PermitRootLogin no",
                kind="file",
                command=("tessera-internal", "ssh"),
                privileged=True,
                reversible=True,
                risk="high",
                notes="Applicato solo se /etc/ssh/sshd_config esiste e una chiave è in ~/.ssh o /root/.ssh.",
                skip_if=skip,
            )
        )
    if cid == "usbguard":
        steps.append(
            PlanStep(
                id=_sid("usb"),
                title="usbguard: genera policy dai device attuali",
                kind="service",
                command=("tessera-internal", "usbguard"),
                privileged=True,
                reversible=True,
                risk="high",
                skip_if=skip,
            )
        )
    if cid == "auditd":
        steps.append(
            PlanStep(
                id=_sid("audit"),
                title="Abilita auditd",
                kind="service",
                command=("tessera-internal", "auditd"),
                privileged=True,
                reversible=True,
                risk="low",
                skip_if=skip,
            )
        )
    if cid == "coredump_off":
        steps.append(
            PlanStep(
                id=_sid("core"),
                title="limits.d: * hard core 0",
                kind="file",
                command=("tessera-internal", "coredump"),
                privileged=True,
                reversible=True,
                risk="low",
            )
        )
    if cid == "mac_random":
        steps.append(
            PlanStep(
                id=_sid("mac"),
                title="NetworkManager wifi.scan-rand-mac-address=yes",
                kind="file",
                command=("tessera-internal", "mac-random"),
                privileged=True,
                reversible=True,
                risk="low",
            )
        )
    if cid == "dns_stub_privacy":
        steps.append(
            PlanStep(
                id=_sid("dns"),
                title="systemd-resolved DNSSEC=allow-downgrade se presente",
                kind="file",
                command=("tessera-internal", "dns"),
                privileged=True,
                reversible=True,
                risk="low",
                skip_if=skip,
            )
        )
    if cid == "luks_check":
        msg = (
            "Root risulta cifrato (LUKS/dm-crypt)."
            if snapshot.storage.root_encrypted
            else "Root NON cifrato. Tessera NON formatta. Per LUKS serve una reinstallazione o un migrate manuale documentato da cryptsetup."
        )
        steps.append(
            PlanStep(
                id=_sid("luks"),
                title=msg,
                kind="info",
                command=("true",),
                privileged=False,
                reversible=True,
                risk="low",
            )
        )
    if cid == "securetty_umask":
        steps.append(
            PlanStep(
                id=_sid("umask"),
                title="Drop-in umask 027 in /etc/profile.d/tessera-umask.sh",
                kind="file",
                command=("tessera-internal", "umask"),
                privileged=True,
                reversible=True,
                risk="low",
            )
        )
    if cid == "tmp_tmpfs":
        if snapshot.memory.total_gib >= 8:
            steps.append(
                PlanStep(
                    id=_sid("tmp"),
                    title="fstab drop-in: tmpfs su /tmp",
                    kind="file",
                    command=("tessera-internal", "tmpfs"),
                    privileged=True,
                    reversible=True,
                    risk="medium",
                    skip_if=skip,
                )
            )
    if cid == "firejail":
        steps.append(
            PlanStep(
                id=_sid("fj"),
                title="Installa firejail (profili upstream)",
                kind="package",
                command=("tessera-internal", "firejail"),
                privileged=True,
                reversible=True,
                risk="medium",
            )
        )
    return steps


def plan_to_script(plan: ApplyPlan, *, dry_run: bool) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "# Generated by Tessera. Review before running.",
        "set -euo pipefail",
        f"# host={plan.hostname} distro={plan.distro} journal={plan.journal_id} dry={dry_run}",
        "",
        "log() { printf '%s %s\\n' \"$(date -Is)\" \"$*\"; }",
        "",
    ]
    for w in plan.warnings:
        lines.append(f"# WARN: {w.replace(chr(10), ' ')}")
    lines.append("")
    for i, step in enumerate(plan.steps, 1):
        quoted = " ".join(_bash_quote(p) for p in step.command)
        lines.append(f"log '[{i}/{len(plan.steps)}] {step.title}'")
        if step.command == ("true",) or step.kind == "info":
            lines.append(f"log 'info: {step.notes or step.title}'")
        elif step.command[0] == "tessera-internal":
            lines.append(f"# internal:{' '.join(step.command[1:])}")
            lines.append(f"tessera apply-internal {' '.join(_bash_quote(p) for p in step.command[1:])} "
                         + ("--dry-run" if dry_run else ""))
        elif dry_run:
            lines.append(f"log 'DRY {quoted}'")
        else:
            lines.append(quoted)
        lines.append("")
    return "\n".join(lines) + "\n"


def _bash_quote(part: str) -> str:
    if not part:
        return "''"
    if all(c.isalnum() or c in "-_./:=@" for c in part):
        return part
    return "'" + part.replace("'", "'\"'\"'") + "'"


def plan_json(plan: ApplyPlan) -> str:
    payload = {
        "hostname": plan.hostname,
        "distro": plan.distro,
        "journal_id": plan.journal_id,
        "warnings": plan.warnings,
        "steps": [
            {
                "id": s.id,
                "title": s.title,
                "kind": s.kind,
                "command": list(s.command),
                "privileged": s.privileged,
                "reversible": s.reversible,
                "risk": s.risk,
                "notes": s.notes,
                "skip_if": s.skip_if,
            }
            for s in plan.steps
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
