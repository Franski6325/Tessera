"""Security controls. Defensive only: firewall, sysctl, encryption *checks*, password policy."""

from __future__ import annotations

from dataclasses import dataclass

from tessera.models import SecurityLevel, SecurityToggle


@dataclass(frozen=True)
class Control:
    id: str
    title_it: str
    title_en: str
    blurb_it: str
    blurb_en: str
    risk: str  # low medium high
    reversible: bool
    levels: frozenset[SecurityLevel]
    # never encrypts an existing live disk
    destructive: bool = False


CONTROLS: tuple[Control, ...] = (
    Control(
        "firewall_inbound_deny",
        "Firewall: deny in ingresso, allow established",
        "Firewall: deny inbound, allow established",
        "nftables/ufw/firewalld: chiude le porte in ascolto non richieste. SSH si chiede a parte.",
        "nftables/ufw/firewalld: close unsolicited inbound. SSH is a separate toggle.",
        "medium",
        True,
        frozenset({SecurityLevel.STANDARD, SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "firewall_allow_ssh",
        "Consenti SSH in ingresso (porta 22)",
        "Allow inbound SSH (port 22)",
        "Solo se amministri la macchina da remoto. Su un portatile desktop-local, lascialo spento.",
        "Only if you administer this host remotely. Leave off for a local laptop.",
        "medium",
        True,
        frozenset({SecurityLevel.RELAXED, SecurityLevel.STANDARD}),
    ),
    Control(
        "unattended_updates",
        "Aggiornamenti di sicurezza automatici",
        "Automatic security updates",
        "Installa le patch di sicurezza. Non fa dist-upgrade completo.",
        "Installs security patches. Not a full dist-upgrade.",
        "low",
        True,
        frozenset({SecurityLevel.STANDARD, SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "pwquality",
        "Politica password (pwquality / PAM)",
        "Password quality policy (pwquality / PAM)",
        "Lunghezza minima, classe di caratteri, rifiuto di password da dizionario locale.",
        "Minimum length, character classes, reject local dictionary words.",
        "low",
        True,
        frozenset({SecurityLevel.STANDARD, SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "password_store",
        "Cofanetto password (KeePassXC + pass)",
        "Password vault (KeePassXC + pass)",
        "Gestore locale, database cifrato. Tessera non vede né conserva i tuoi segreti.",
        "Local vault, encrypted database. Tessera never sees or stores your secrets.",
        "low",
        True,
        frozenset({SecurityLevel.STANDARD, SecurityLevel.HARDENED, SecurityLevel.FORTRESS, SecurityLevel.RELAXED}),
    ),
    Control(
        "kernel_sysctl",
        "Sysctl di raffreddamento kernel",
        "Kernel hardening sysctl",
        "ASLR, reverse-path filter, syncookies, kptr_restrict, dmesg_restrict, unprivileged bpf off.",
        "ASLR, rp_filter, syncookies, kptr_restrict, dmesg_restrict, unprivileged bpf off.",
        "medium",
        True,
        frozenset({SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "apparmor",
        "MAC: AppArmor (o SELinux se già enforcing)",
        "MAC: AppArmor (or SELinux if already enforcing)",
        "Non disabilita SELinux su Fedora/RHEL. Su Debian/Ubuntu/Arch abilita AppArmor.",
        "Does not disable SELinux on Fedora/RHEL. Enables AppArmor on Debian/Ubuntu/Arch.",
        "medium",
        True,
        frozenset({SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "fail2ban",
        "fail2ban su SSH (se SSH è esposto)",
        "fail2ban on SSH (if SSH is exposed)",
        "Ban temporaneo dopo tentativi ripetuti. Inutile se SSH è chiuso.",
        "Temporary bans after repeated attempts. Pointless if SSH is closed.",
        "low",
        True,
        frozenset({SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "ssh_hardening",
        "SSH: niente password, niente root login",
        "SSH: no passwords, no root login",
        "Si applica solo se sshd è installato. Richiede che tu abbia già una chiave.",
        "Only if sshd is installed. You must already have a key.",
        "high",
        True,
        frozenset({SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "usbguard",
        "USBGuard (policy allowlist)",
        "USBGuard (allowlist policy)",
        "Su un portatile riduce le BadUSB. Prima di attivarlo Tessera esporta i device attuali.",
        "On a laptop this cuts BadUSB. Tessera exports currently present devices first.",
        "high",
        True,
        frozenset({SecurityLevel.FORTRESS}),
    ),
    Control(
        "auditd",
        "auditd: tracce di login e privilegi",
        "auditd: login and privilege audit trail",
        "Log locali. Non spedisce nulla in rete.",
        "Local logs. Nothing is shipped off-box.",
        "low",
        True,
        frozenset({SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "coredump_off",
        "Disabilita core dump utente",
        "Disable user core dumps",
        "Meno leak di memoria su crash. I developer possono riattivarlo per sessione.",
        "Fewer memory leaks on crash. Developers can re-enable per session.",
        "low",
        True,
        frozenset({SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "mac_random",
        "Randomizzazione MAC sulle reti wireless",
        "MAC randomization on wireless",
        "NetworkManager / iwd se presenti. Non tocca ethernet dockage fisso.",
        "NetworkManager / iwd when present. Leaves docked ethernet alone.",
        "low",
        True,
        frozenset({SecurityLevel.STANDARD, SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "dns_stub_privacy",
        "DNS: stub resolver con DNSSEC se disponibile",
        "DNS: stub resolver with DNSSEC when available",
        "systemd-resolved DNSSEC=allow-downgrade, o unbound locale. Nessun DNS commerciale imposto.",
        "systemd-resolved DNSSEC=allow-downgrade, or local unbound. No commercial DNS forced.",
        "low",
        True,
        frozenset({SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "luks_check",
        "Verifica cifratura disco (LUKS) — nessuna formatta",
        "Check disk encryption (LUKS) — never formats",
        "Se il root non è cifrato, Tessera spiega come farlo su una nuova installazione. Non cifra un disco già in uso.",
        "If root is not encrypted, Tessera explains how to do it on a fresh install. It will not encrypt an in-use disk.",
        "low",
        True,
        frozenset({SecurityLevel.STANDARD, SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
        destructive=False,
    ),
    Control(
        "securetty_umask",
        "umask 027 e lock dello schermo",
        "umask 027 and screen lock",
        "Nuovi file non leggibili dal mondo. Ricorda il lock (GNOME/KDE/swaylock) — non lo forza in modo distruttivo.",
        "New files not world-readable. Reminds you to lock (GNOME/KDE/swaylock) — never wrecks the DE.",
        "low",
        True,
        frozenset({SecurityLevel.HARDENED, SecurityLevel.FORTRESS}),
    ),
    Control(
        "tmp_tmpfs",
        "/tmp su tmpfs (se RAM ≥ 8 GiB)",
        "/tmp on tmpfs (if RAM ≥ 8 GiB)",
        "Meno persistenza di scrap. Saltato se la RAM è bassa.",
        "Less leftover scrap. Skipped on low RAM.",
        "medium",
        True,
        frozenset({SecurityLevel.FORTRESS}),
    ),
    Control(
        "firejail",
        "firejail per browser (opt-in)",
        "firejail for browsers (opt-in)",
        "Profili upstream. Non sandboxa l'intero desktop.",
        "Upstream profiles. Does not sandbox the whole desktop.",
        "medium",
        True,
        frozenset({SecurityLevel.FORTRESS, SecurityLevel.HARDENED}),
    ),
)


def defaults_for(level: SecurityLevel) -> list[SecurityToggle]:
    if level == SecurityLevel.CUSTOM:
        # start from hardened then the UI lets the user flip
        level = SecurityLevel.HARDENED
    toggles: list[SecurityToggle] = []
    for ctrl in CONTROLS:
        enabled = level in ctrl.levels or (
            level == SecurityLevel.RELAXED and ctrl.id in {"password_store"}
        )
        # SSH allow is off unless relaxed/standard *and* user turns it on — default off
        if ctrl.id == "firewall_allow_ssh":
            enabled = False
        if ctrl.id == "fail2ban":
            enabled = level in {SecurityLevel.HARDENED, SecurityLevel.FORTRESS}
        toggles.append(SecurityToggle(id=ctrl.id, enabled=enabled))
    return toggles


def control_by_id(cid: str) -> Control | None:
    for ctrl in CONTROLS:
        if ctrl.id == cid:
            return ctrl
    return None
