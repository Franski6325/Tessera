"""Discover native package managers, AUR helpers, locks, extra repos."""

from __future__ import annotations

import os
from pathlib import Path

from tessera.detect._io import note, read_text, try_run, which
from tessera.models import DistroFamily, ManagerKind, ManagerStatus, ProbeNote

_NATIVE: dict[DistroFamily, tuple[ManagerKind, ...]] = {
    DistroFamily.DEBIAN: (ManagerKind.APT,),
    DistroFamily.UBUNTU: (ManagerKind.APT,),
    DistroFamily.KALI: (ManagerKind.APT,),
    DistroFamily.ARCH: (ManagerKind.PACMAN,),
    DistroFamily.FEDORA: (ManagerKind.DNF,),
    DistroFamily.RHEL: (ManagerKind.DNF, ManagerKind.YUM),
    DistroFamily.SUSE: (ManagerKind.ZYPPER,),
    DistroFamily.ALPINE: (ManagerKind.APK,),
    DistroFamily.VOID: (ManagerKind.XBPS,),
    DistroFamily.GENTOO: (ManagerKind.EMERGE,),
    DistroFamily.NIXOS: (ManagerKind.NIX,),
    DistroFamily.UNKNOWN: (),
}

_LOCKS = {
    ManagerKind.APT: Path("/var/lib/dpkg/lock-frontend"),
    ManagerKind.PACMAN: Path("/var/lib/pacman/db.lck"),
    ManagerKind.DNF: Path("/var/run/dnf.pid"),
    ManagerKind.ZYPPER: Path("/var/run/zypp.pid"),
}


def _version(binary: str, args: list[str] | None = None) -> str | None:
    if not which(binary):
        return None
    raw = try_run([binary, *(args or ["--version"])], timeout=5.0)
    if not raw:
        return None
    return raw.splitlines()[0][:80]


def _inode_held(path: Path) -> bool:
    """True only if /proc/locks shows an advisory lock on this inode.

    Debian/Ubuntu always *create* /var/lib/dpkg/lock-frontend; existence ≠ busy.
    pacman instead creates db.lck only while running — we still consult /proc/locks
    so a leftover empty file does not block Tessera.
    """
    try:
        st = path.stat()
    except OSError:
        return False
    locks = read_text("/proc/locks", default="") or ""
    token = f":{st.st_ino} "
    token2 = f":{st.st_ino}\n"
    for line in locks.splitlines():
        # "1: POSIX  ADVISORY  WRITE  123  00:00:45678 0 EOF"
        if f":{st.st_ino} " in f"{line} " or line.endswith(f":{st.st_ino}"):
            return True
        parts = line.split()
        for part in parts:
            if part.endswith(f":{st.st_ino}"):
                return True
    del token, token2
    return False


def _pidfile_alive(path: Path) -> bool:
    raw = read_text(path, default="") or ""
    try:
        pid = int(raw.strip().split()[0])
    except (ValueError, IndexError):
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _locked(kind: ManagerKind) -> tuple[bool, str | None]:
    path = _LOCKS.get(kind)
    if path is None:
        return False, None
    if kind in {ManagerKind.DNF, ManagerKind.ZYPPER}:
        if path.exists() and _pidfile_alive(path):
            return True, f"processo attivo ({path})"
        return False, None
    if not path.exists():
        return False, None
    if _inode_held(path):
        return True, f"lock held: {path}"
    return False, None


def _extra_repos(kind: ManagerKind) -> tuple[str, ...]:
    found: list[str] = []
    if kind in {ManagerKind.PACMAN, ManagerKind.YAY, ManagerKind.PARU}:
        pacman_conf = read_text("/etc/pacman.conf", default="") or ""
        if "[blackarch]" in pacman_conf:
            found.append("blackarch")
        if "[multilib]" in pacman_conf and not _section_commented(pacman_conf, "multilib"):
            found.append("multilib")
        if "[extra]" in pacman_conf:
            found.append("extra")
        if "[chaotic-aur]" in pacman_conf:
            found.append("chaotic-aur")
    if kind in {ManagerKind.APT, ManagerKind.NALA}:
        sources = []
        sources.append(read_text("/etc/apt/sources.list", default="") or "")
        src_dir = Path("/etc/apt/sources.list.d")
        if src_dir.is_dir():
            for item in src_dir.iterdir():
                if item.suffix in {".list", ".sources"}:
                    sources.append(read_text(item, default="") or "")
        blob = "\n".join(sources).lower()
        if "kali" in blob:
            found.append("kali")
        if "debian" in blob:
            found.append("debian")
        if "ubuntu" in blob:
            found.append("ubuntu")
        if "flathub" in blob:
            found.append("flathub-apt")
    return tuple(dict.fromkeys(found))


def _section_commented(conf: str, name: str) -> bool:
    for line in conf.splitlines():
        if line.strip().startswith(f"[{name}]"):
            return False
        if line.strip().startswith(f"#[ {name}") or line.strip().startswith(f"#[{name}]"):
            return True
    return False


def detect_managers(family: DistroFamily) -> tuple[ManagerStatus, ...]:
    notes_global: list[ProbeNote] = []
    results: list[ManagerStatus] = []
    native_kinds = _NATIVE.get(family, ())

    specs: list[tuple[ManagerKind, str, bool, bool, list[str] | None]] = [
        (ManagerKind.APT, "apt-get", True, False, ["--version"]),
        (ManagerKind.NALA, "nala", False, True, ["--version"]),
        (ManagerKind.PACMAN, "pacman", True, False, ["--version"]),
        (ManagerKind.YAY, "yay", False, True, ["--version"]),
        (ManagerKind.PARU, "paru", False, True, ["--version"]),
        (ManagerKind.DNF, "dnf", True, False, ["--version"]),
        (ManagerKind.YUM, "yum", True, False, ["--version"]),
        (ManagerKind.ZYPPER, "zypper", True, False, ["--version"]),
        (ManagerKind.APK, "apk", True, False, ["--version"]),
        (ManagerKind.XBPS, "xbps-install", True, False, ["--version"]),
        (ManagerKind.EMERGE, "emerge", True, False, ["--version"]),
        (ManagerKind.NIX, "nix-env", True, False, ["--version"]),
        (ManagerKind.FLATPAK, "flatpak", False, True, ["--version"]),
        (ManagerKind.SNAP, "snap", False, True, ["--version"]),
        (ManagerKind.PIPX, "pipx", False, True, ["--version"]),
    ]

    present_native = False
    for kind, binary, _can_native, helper, args in specs:
        version = _version(binary, args)
        present = version is not None or bool(which(binary))
        native = kind in native_kinds and present
        if native:
            present_native = True
        locked, lock_reason = _locked(kind) if present and not helper else (False, None)
        extra = _extra_repos(kind) if present else ()
        item_notes: list[ProbeNote] = []
        if kind == ManagerKind.YAY and present:
            item_notes.append(
                note(
                    "mgr.yay",
                    "yay è un helper AUR: usa pacman per i repo ufficiali e l'AUR per il resto. "
                    "Non sostituisce pacman e non contiene 'tutti' i pacchetti cyber/developer: "
                    "dipende da extra/multilib, BlackArch e da ciò che esiste in AUR.",
                    "info",
                )
            )
        if kind == ManagerKind.SNAP and present:
            item_notes.append(
                note("mgr.snap", "snap è opzionale e confinante; Tessera non lo impone.", "info")
            )
        results.append(
            ManagerStatus(
                kind=kind,
                present=present,
                version=version,
                native=native,
                helper=helper,
                locked=locked,
                lock_reason=lock_reason,
                extra_repos=extra,
                notes=tuple(item_notes),
            )
        )

    if not present_native and family != DistroFamily.UNKNOWN:
        notes_global.append(
            note(
                "mgr.native_missing",
                "Il gestore nativo della distro non risulta nel PATH. "
                "Tessera può solo pianificare, non applicare pacchetti.",
                "error",
            )
        )
    # attach global notes onto a synthetic unknown if needed — callers merge snapshot.notes
    del notes_global
    return tuple(results)


def native_kind(family: DistroFamily) -> ManagerKind | None:
    kinds = _NATIVE.get(family) or ()
    return kinds[0] if kinds else None
