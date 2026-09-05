"""Which packages are already present — best-effort, never fatal."""

from __future__ import annotations

from tessera.detect._io import try_run, which
from tessera.models import ManagerKind


def installed_names(kind: ManagerKind) -> set[str]:
    if kind in {ManagerKind.APT, ManagerKind.NALA} and which("dpkg-query"):
        raw = try_run(["dpkg-query", "-W", "-f", "${Package}\n"], timeout=20.0) or ""
        return {l.strip() for l in raw.splitlines() if l.strip()}
    if kind in {ManagerKind.PACMAN, ManagerKind.YAY, ManagerKind.PARU} and which("pacman"):
        raw = try_run(["pacman", "-Qq"], timeout=20.0) or ""
        return {l.strip() for l in raw.splitlines() if l.strip()}
    if kind in {ManagerKind.DNF, ManagerKind.YUM} and which("rpm"):
        raw = try_run(["rpm", "-qa", "--qf", "%{NAME}\n"], timeout=20.0) or ""
        return {l.strip() for l in raw.splitlines() if l.strip()}
    if kind == ManagerKind.ZYPPER and which("rpm"):
        raw = try_run(["rpm", "-qa", "--qf", "%{NAME}\n"], timeout=20.0) or ""
        return {l.strip() for l in raw.splitlines() if l.strip()}
    if kind == ManagerKind.APK and which("apk"):
        raw = try_run(["apk", "info"], timeout=20.0) or ""
        return {l.strip() for l in raw.splitlines() if l.strip()}
    if kind == ManagerKind.XBPS and which("xbps-query"):
        raw = try_run(["xbps-query", "-l"], timeout=20.0) or ""
        names = set()
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                names.add(parts[1].rsplit("-", 1)[0])
        return names
    if kind == ManagerKind.FLATPAK and which("flatpak"):
        raw = try_run(["flatpak", "list", "--app", "--columns=application"], timeout=20.0) or ""
        return {l.strip() for l in raw.splitlines() if l.strip() and l.strip() != "Application"}
    if kind == ManagerKind.PIPX and which("pipx"):
        raw = try_run(["pipx", "list", "--short"], timeout=20.0) or ""
        return {l.strip() for l in raw.splitlines() if l.strip()}
    return set()
