"""Small, idempotent host mutations invoked as `tessera apply-internal <verb>`. Dry-run safe."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from tessera.detect._io import list_dir, read_text, try_run, which
from tessera.exceptions import ApplyError, PermissionPlanError

SYSCTL_PATH = Path("/etc/sysctl.d/90-tessera-hardening.conf")
UMASK_PATH = Path("/etc/profile.d/tessera-umask.sh")
CORE_PATH = Path("/etc/security/limits.d/90-tessera-coredump.conf")
NM_WIFI = Path("/etc/NetworkManager/conf.d/90-tessera-wifi-privacy.conf")
RESOLVED = Path("/etc/systemd/resolved.conf.d/90-tessera-dnssec.conf")
SSH_DROPIN = Path("/etc/ssh/sshd_config.d/90-tessera.conf")
TMP_FSTAB = Path("/etc/fstab.d/tessera-tmpfs.fstab")
PWQUALITY = Path("/etc/security/pwquality.conf.d/90-tessera.conf")

SYSCTL_BODY = """# Managed by Tessera. Safe to delete this file.
kernel.randomize_va_space = 2
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.unprivileged_bpf_disabled = 1
kernel.yama.ptrace_scope = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
fs.suid_dumpable = 0
"""

UMASK_BODY = """# Managed by Tessera
umask 027
"""

CORE_BODY = """# Managed by Tessera
* hard core 0
"""

NM_BODY = """# Managed by Tessera
[device-mac-randomization]
wifi.scan-rand-mac-address=yes

[connection-mac-randomization]
wifi.cloned-mac-address=random
ethernet.cloned-mac-address=preserve
"""

RESOLVED_BODY = """# Managed by Tessera
[Resolve]
DNSSEC=allow-downgrade
"""

SSH_BODY = """# Managed by Tessera — requires an authorized_keys already in place
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
X11Forwarding no
AllowAgentForwarding no
"""

PWQ_BODY = """# Managed by Tessera
minlen = 12
minclass = 3
dictcheck = 1
enforcing = 1
"""


def _need_root(dry: bool) -> None:
    if dry:
        return
    if os.geteuid() != 0:
        raise PermissionPlanError(
            "Questo passo richiede root (sudo/pkexec).",
            code="apply.root",
            hint="Ri-lancia: sudo tessera apply-internal … oppure applica lo script esportato.",
        )


def _write(path: Path, body: str, *, dry: bool) -> str:
    if dry:
        return f"DRY write {path} ({len(body)} bytes)"
    _need_root(False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    except OSError as exc:
        raise ApplyError(f"Impossibile scrivere {path}: {exc}", code="apply.write") from exc
    return f"wrote {path}"


def governor(name: str, *, dry: bool) -> str:
    cpus = [p for p in list_dir("/sys/devices/system/cpu") if p.name.startswith("cpu") and p.name[3:].isdigit()]
    changed = 0
    for cpu in cpus:
        gov = cpu / "cpufreq" / "scaling_governor"
        avail_raw = read_text(cpu / "cpufreq" / "scaling_available_governors", default="") or ""
        available = avail_raw.split()
        pick = name if name in available else (available[0] if available else None)
        if not pick or not gov.exists():
            continue
        if dry:
            changed += 1
            continue
        try:
            gov.write_text(pick + "\n", encoding="utf-8")
            changed += 1
        except OSError:
            continue
    if changed == 0:
        return "nessun cpufreq sysfs scrivibile (VM, container, o driver senza governor)"
    return f"{'DRY ' if dry else ''}governor {name} su {changed} CPU"


def firewall(mode: str, *, dry: bool) -> str:
    _need_root(dry)
    if which("ufw"):
        if mode == "baseline":
            cmds = [["ufw", "default", "deny", "incoming"], ["ufw", "default", "allow", "outgoing"], ["ufw", "--force", "enable"]]
        elif mode == "allow-ssh":
            cmds = [["ufw", "allow", "OpenSSH"], ["ufw", "allow", "22/tcp"]]
        else:
            raise ApplyError(f"firewall mode sconosciuta: {mode}", code="apply.fw")
        return _run_many(cmds, dry=dry)
    if which("firewall-cmd"):
        if mode == "baseline":
            cmds = [["firewall-cmd", "--permanent", "--set-default-zone=public"],
                    ["firewall-cmd", "--reload"]]
        else:
            cmds = [["firewall-cmd", "--permanent", "--add-service=ssh"], ["firewall-cmd", "--reload"]]
        return _run_many(cmds, dry=dry)
    if which("nft"):
        if dry:
            return "DRY nft baseline (non flusha tabelle docker/cni)"
        table = "inet tessera"
        script = """
table inet tessera {
  chain input {
    type filter hook input priority 0; policy drop;
    ct state established,related accept
    iif lo accept
    ip protocol icmp accept
    ip6 nexthdr icmpv6 accept
  }
  chain forward { type filter hook forward priority 0; policy drop; }
  chain output { type filter hook output priority 0; policy accept; }
}
"""
        if mode == "allow-ssh":
            script = script.replace("iif lo accept", "iif lo accept\n    tcp dport 22 accept")
        existing = try_run(["nft", "list", "tables"]) or ""
        if "tessera" in existing and not dry:
            try_run(["nft", "delete", "table", "inet", "tessera"])
        path = Path("/etc/nftables.d/tessera.nft") if Path("/etc/nftables.d").exists() else Path("/etc/nftables-tessera.nft")
        if not dry:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(script, encoding="utf-8")
            try_run(["nft", "-f", str(path)])
        return f"{'DRY ' if dry else ''}nft {table} written"
    return "nessun firewall (ufw/firewalld/nft) trovato: passo saltato"


def sysctl(*, dry: bool) -> str:
    msg = _write(SYSCTL_PATH, SYSCTL_BODY, dry=dry)
    if not dry and which("sysctl"):
        try_run(["sysctl", "--system"])
    return msg


def umask(*, dry: bool) -> str:
    return _write(UMASK_PATH, UMASK_BODY, dry=dry)


def coredump(*, dry: bool) -> str:
    return _write(CORE_PATH, CORE_BODY, dry=dry)


def mac_random(*, dry: bool) -> str:
    if not Path("/etc/NetworkManager").exists():
        return "NetworkManager assente: MAC randomization saltata"
    return _write(NM_WIFI, NM_BODY, dry=dry)


def dns(*, dry: bool) -> str:
    if not which("resolvectl") and not Path("/etc/systemd/resolved.conf").exists():
        return "systemd-resolved assente: DNSSEC saltato"
    return _write(RESOLVED, RESOLVED_BODY, dry=dry)


def pwquality(*, dry: bool) -> str:
    if not Path("/etc/security").exists():
        return "PAM security/ assente"
    # pwquality.conf.d may not exist on all distros — fall back
    target = PWQUALITY if Path("/etc/security/pwquality.conf.d").exists() or dry else Path("/etc/security/pwquality.conf")
    if target.name == "pwquality.conf" and target.exists() and not dry:
        existing = target.read_text(encoding="utf-8", errors="replace")
        if "Managed by Tessera" not in existing:
            return _write(target, existing.rstrip() + "\n" + PWQ_BODY, dry=dry)
    return _write(target, PWQ_BODY, dry=dry)


def ssh(*, dry: bool) -> str:
    if not Path("/etc/ssh/sshd_config").exists():
        return "sshd non installato: salto"
    home = Path.home() / ".ssh"
    root_keys = Path("/root/.ssh")
    has_key = any((p / "authorized_keys").exists() and (p / "authorized_keys").stat().st_size > 0 for p in (home, root_keys))
    pubkeys = list(home.glob("id_*.pub")) + list(home.glob("*.pub"))
    if not has_key and not pubkeys:
        raise ApplyError(
            "Rifiuto ssh hardening: nessuna chiave trovata. Aggiungi authorized_keys prima.",
            code="apply.ssh_keys",
        )
    drop_dir = SSH_DROPIN.parent
    if drop_dir.exists() or dry:
        return _write(SSH_DROPIN, SSH_BODY, dry=dry)
    return _write(Path("/etc/ssh/sshd_config"), _merge_ssh(Path("/etc/ssh/sshd_config"), dry=dry), dry=dry)


def _merge_ssh(path: Path, *, dry: bool) -> str:
    raw = read_text(path, default="") or ""
    return raw.rstrip() + "\n" + SSH_BODY


def apparmor(*, dry: bool) -> str:
    selinux = read_text("/sys/fs/selinux/enforce", default=None)
    if selinux == "1":
        return "SELinux enforcing: Tessera non lo disabilita e non imposta AppArmor in parallelo"
    if which("aa-enforce") or Path("/sys/module/apparmor").exists() or which("apparmor_status"):
        if dry:
            return "DRY apparmor enable"
        if which("systemctl"):
            try_run(["systemctl", "enable", "--now", "apparmor"])
        return "apparmor enable tentato"
    return "AppArmor non disponibile su questa distro"


def fail2ban(*, dry: bool) -> str:
    if dry:
        return "DRY fail2ban enable"
    if which("systemctl"):
        try_run(["systemctl", "enable", "--now", "fail2ban"])
    return "fail2ban enable tentato (se il pacchetto è installato)"


def auditd(*, dry: bool) -> str:
    if dry:
        return "DRY auditd enable"
    if which("systemctl"):
        try_run(["systemctl", "enable", "--now", "auditd"])
    return "auditd enable tentato"


def usbguard(*, dry: bool) -> str:
    if dry:
        return "DRY usbguard generate-policy"
    if not which("usbguard"):
        return "usbguard non installato: installa il pacchetto e riesegui"
    policy = try_run(["usbguard", "generate-policy"]) or ""
    dest = Path("/etc/usbguard/rules.conf")
    if policy:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(policy, encoding="utf-8")
    if which("systemctl"):
        try_run(["systemctl", "enable", "--now", "usbguard"])
    return f"usbguard policy → {dest}"


def tmpfs(*, dry: bool) -> str:
    line = "tmpfs /tmp tmpfs defaults,noatime,mode=1777,nosuid,nodev 0 0\n"
    if Path("/etc/fstab.d").exists() or dry:
        return _write(TMP_FSTAB, line, dry=dry)
    fstab = Path("/etc/fstab")
    current = read_text(fstab, default="") or ""
    if "/tmp" in current and "tmpfs" in current:
        return "/tmp già tmpfs"
    if dry:
        return "DRY append /etc/fstab tmpfs /tmp"
    _need_root(False)
    with fstab.open("a", encoding="utf-8") as fh:
        fh.write("\n# Tessera\n" + line)
    return "appended tmpfs /tmp to /etc/fstab"


def unattended(*, dry: bool) -> str:
    if which("dpkg"):
        return "Debian-like: installa unattended-upgrades (pacchetto nel piano) e dpkg-reconfigure"
    if which("dnf"):
        if dry:
            return "DRY dnf-automatic"
        if which("systemctl"):
            try_run(["systemctl", "enable", "--now", "dnf-automatic.timer"])
        return "dnf-automatic timer"
    if which("pacman"):
        return "Arch: niente unattended ufficiale; usa i pacchetti di aggiornamento manuali o systemd timer tue"
    return "niente meccanismo unattended noto"


def firejail(*, dry: bool) -> str:
    if which("firejail"):
        return "firejail già presente"
    return "installa il pacchetto firejail dal piano strumenti"


def dispatch(verb: str, extra: list[str], *, dry: bool) -> str:
    mapping = {
        "governor": lambda: governor(extra[0] if extra else "schedutil", dry=dry),
        "firewall": lambda: firewall(extra[0] if extra else "baseline", dry=dry),
        "sysctl": lambda: sysctl(dry=dry),
        "umask": lambda: umask(dry=dry),
        "coredump": lambda: coredump(dry=dry),
        "mac-random": lambda: mac_random(dry=dry),
        "dns": lambda: dns(dry=dry),
        "pwquality": lambda: pwquality(dry=dry),
        "ssh": lambda: ssh(dry=dry),
        "apparmor": lambda: apparmor(dry=dry),
        "fail2ban": lambda: fail2ban(dry=dry),
        "auditd": lambda: auditd(dry=dry),
        "usbguard": lambda: usbguard(dry=dry),
        "tmpfs": lambda: tmpfs(dry=dry),
        "unattended": lambda: unattended(dry=dry),
        "firejail": lambda: firejail(dry=dry),
    }
    fn = mapping.get(verb)
    if fn is None:
        raise ApplyError(f"Verbo interno sconosciuto: {verb}", code="apply.verb")
    return fn()


def _run_many(cmds: list[list[str]], *, dry: bool) -> str:
    logs = []
    for cmd in cmds:
        if dry:
            logs.append("DRY " + " ".join(cmd))
            continue
        if not which(cmd[0]) and not shutil.which(cmd[0]):
            logs.append("missing " + cmd[0])
            continue
        out = try_run(cmd, timeout=30.0)
        logs.append((out or "")[:200] or "ok " + cmd[0])
    return " | ".join(logs)
