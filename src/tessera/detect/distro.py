"""Distro family from /etc/os-release plus init and kernel."""

from __future__ import annotations

import os
import platform
from pathlib import Path

from tessera.detect._io import note, read_text
from tessera.models import DistroFamily, DistroInfo, ProbeNote


def _parse_os_release(raw: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"').strip("'")
    return data


def _family(os_id: str, id_like: tuple[str, ...]) -> DistroFamily:
    blob = " ".join((os_id, *id_like)).lower()
    mapping = (
        ("kali", DistroFamily.KALI),
        ("ubuntu", DistroFamily.UBUNTU),
        ("linuxmint", DistroFamily.UBUNTU),
        ("pop", DistroFamily.UBUNTU),
        ("elementary", DistroFamily.UBUNTU),
        ("debian", DistroFamily.DEBIAN),
        ("raspbian", DistroFamily.DEBIAN),
        ("arch", DistroFamily.ARCH),
        ("endeavouros", DistroFamily.ARCH),
        ("manjaro", DistroFamily.ARCH),
        ("garuda", DistroFamily.ARCH),
        ("artix", DistroFamily.ARCH),
        ("cachyos", DistroFamily.ARCH),
        ("blackarch", DistroFamily.ARCH),
        ("fedora", DistroFamily.FEDORA),
        ("nobara", DistroFamily.FEDORA),
        ("rhel", DistroFamily.RHEL),
        ("rocky", DistroFamily.RHEL),
        ("almalinux", DistroFamily.RHEL),
        ("centos", DistroFamily.RHEL),
        ("opensuse", DistroFamily.SUSE),
        ("suse", DistroFamily.SUSE),
        ("alpine", DistroFamily.ALPINE),
        ("void", DistroFamily.VOID),
        ("gentoo", DistroFamily.GENTOO),
        ("nixos", DistroFamily.NIXOS),
    )
    for needle, family in mapping:
        if needle in blob:
            return family
    return DistroFamily.UNKNOWN


def _init_system() -> str | None:
    for candidate in ("/sbin/init", "/usr/lib/systemd/systemd", "/sbin/openrc"):
        try:
            target = os.path.realpath(candidate)
        except OSError:
            continue
        name = Path(target).name.lower()
        if "systemd" in name:
            return "systemd"
        if "openrc" in name:
            return "openrc"
        if name in {"runit", "s6-svscan"}:
            return name
    comm = read_text("/proc/1/comm", default="")
    if comm:
        return comm
    return None


def detect_distro() -> DistroInfo:
    notes: list[ProbeNote] = []
    raw = read_text("/etc/os-release", default="") or read_text("/usr/lib/os-release", default="") or ""
    parsed = _parse_os_release(raw) if raw else {}
    if not parsed:
        notes.append(note("distro.missing", "os-release assente: famiglia sconosciuta.", "warning"))
    os_id = (parsed.get("ID") or "unknown").lower()
    id_like = tuple(part for part in (parsed.get("ID_LIKE") or "").replace(",", " ").split() if part)
    family = _family(os_id, id_like)
    kernel = platform.release()
    return DistroInfo(
        id=os_id,
        id_like=id_like,
        name=parsed.get("NAME") or os_id,
        version=parsed.get("VERSION_ID") or parsed.get("BUILD_ID") or "",
        family=family,
        pretty=parsed.get("PRETTY_NAME") or parsed.get("NAME") or os_id,
        kernel=kernel,
        init=_init_system(),
        notes=tuple(notes),
    )
