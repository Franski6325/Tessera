"""Translate a package id into an install argv for the selected manager. Never uninstall user apps."""

from __future__ import annotations

from dataclasses import dataclass

from tessera.catalog.packages import Pkg, name_for
from tessera.exceptions import PackageManagerError
from tessera.models import DistroFamily, ManagerKind, ManagerStatus


@dataclass(frozen=True)
class InstallSpec:
    pkg_id: str
    manager: ManagerKind
    argv: tuple[str, ...]
    display_name: str
    via: str  # native | aur | blackarch | flatpak | pipx | missing
    note: str = ""


def pick_primary(managers: tuple[ManagerStatus, ...], preferred: ManagerKind | None) -> ManagerStatus | None:
    present = [m for m in managers if m.present]
    if preferred:
        for m in present:
            if m.kind == preferred:
                return m
    for m in present:
        if m.native:
            return m
    return present[0] if present else None


def resolve_install(
    pkg: Pkg,
    family: DistroFamily,
    primary: ManagerKind,
    *,
    extra: tuple[ManagerKind, ...] = (),
    enable_blackarch: bool = False,
    enable_flatpak: bool = False,
) -> InstallSpec:
    native_name = name_for(pkg, family)
    aur_ok = primary in {ManagerKind.YAY, ManagerKind.PARU} or ManagerKind.YAY in extra or ManagerKind.PARU in extra
    helper = primary if primary in {ManagerKind.YAY, ManagerKind.PARU} else (
        ManagerKind.PARU if ManagerKind.PARU in extra else ManagerKind.YAY if ManagerKind.YAY in extra else None
    )

    if native_name:
        argv = _native_install(primary, native_name, family)
        return InstallSpec(pkg.id, primary, argv, native_name, "native")

    if enable_blackarch and pkg.blackarch and primary in {ManagerKind.PACMAN, ManagerKind.YAY, ManagerKind.PARU}:
        argv = _native_install(primary, pkg.blackarch, family)
        return InstallSpec(pkg.id, primary, argv, pkg.blackarch, "blackarch",
                           "Richiede repo BlackArch abilitato (scelta esplicita).")

    if aur_ok and pkg.aur and helper:
        argv = (helper.value, "-S", "--needed", pkg.aur)
        return InstallSpec(pkg.id, helper, argv, pkg.aur, "aur",
                           "AUR: pacchetto community. Tessera non esegue PKGBUILD senza --needed e conferma.")

    if enable_flatpak and pkg.flatpak and (primary == ManagerKind.FLATPAK or ManagerKind.FLATPAK in extra):
        return InstallSpec(
            pkg.id,
            ManagerKind.FLATPAK,
            ("flatpak", "install", "-y", "flathub", pkg.flatpak),
            pkg.flatpak,
            "flatpak",
        )

    if pkg.pipx and (primary == ManagerKind.PIPX or ManagerKind.PIPX in extra):
        return InstallSpec(pkg.id, ManagerKind.PIPX, ("pipx", "install", pkg.pipx), pkg.pipx, "pipx")

    return InstallSpec(
        pkg.id,
        primary,
        (),
        pkg.id,
        "missing",
        "Nessun pacchetto equivalente in questo gestore. Cambia gestore, abilita BlackArch/Flathub, o togli lo strumento.",
    )


def _native_install(primary: ManagerKind, name: str, family: DistroFamily) -> tuple[str, ...]:
    # multi-name (fedora '@group' or 'gcc make') — split carefully
    bits = name.split()
    if primary == ManagerKind.NALA:
        return ("nala", "install", "-y", *bits)
    if primary in {ManagerKind.APT}:
        return ("apt-get", "install", "-y", *bits)
    if primary == ManagerKind.PACMAN:
        return ("pacman", "-S", "--needed", "--noconfirm", *bits)
    if primary in {ManagerKind.YAY, ManagerKind.PARU}:
        return (primary.value, "-S", "--needed", *bits)
    if primary == ManagerKind.DNF:
        return ("dnf", "install", "-y", *bits)
    if primary == ManagerKind.YUM:
        return ("yum", "install", "-y", *bits)
    if primary == ManagerKind.ZYPPER:
        return ("zypper", "--non-interactive", "install", *bits)
    if primary == ManagerKind.APK:
        return ("apk", "add", *bits)
    if primary == ManagerKind.XBPS:
        return ("xbps-install", "-Sy", *bits)
    if primary == ManagerKind.EMERGE:
        return ("emerge", "--ask=n", *bits)
    if primary == ManagerKind.NIX:
        return ("nix-env", "-iA", *bits)
    raise PackageManagerError(f"Gestore {primary.value} non mappato per l'installazione.", code="pkg.map")


def refresh_argv(kind: ManagerKind) -> tuple[str, ...]:
    return {
        ManagerKind.APT: ("apt-get", "update"),
        ManagerKind.NALA: ("nala", "update"),
        ManagerKind.PACMAN: ("pacman", "-Sy"),
        ManagerKind.YAY: ("yay", "-Sy"),
        ManagerKind.PARU: ("paru", "-Sy"),
        ManagerKind.DNF: ("dnf", "makecache"),
        ManagerKind.YUM: ("yum", "makecache"),
        ManagerKind.ZYPPER: ("zypper", "refresh"),
        ManagerKind.APK: ("apk", "update"),
        ManagerKind.XBPS: ("xbps-install", "-S"),
        ManagerKind.FLATPAK: ("flatpak", "update", "-y", "--appstream"),
        ManagerKind.EMERGE: ("emerge", "--sync"),
        ManagerKind.NIX: ("nix-channel", "--update"),
    }.get(kind, ())


def upgrade_argv(kind: ManagerKind) -> tuple[str, ...]:
    """Security-friendly upgrade. Never dist-upgrade / -Syu without the plan calling it out."""
    return {
        ManagerKind.APT: ("apt-get", "upgrade", "-y"),
        ManagerKind.NALA: ("nala", "upgrade", "-y"),
        ManagerKind.PACMAN: ("pacman", "-Su", "--noconfirm"),
        ManagerKind.YAY: ("yay", "-Su", "--noconfirm"),
        ManagerKind.PARU: ("paru", "-Su", "--noconfirm"),
        ManagerKind.DNF: ("dnf", "upgrade", "-y"),
        ManagerKind.YUM: ("yum", "update", "-y"),
        ManagerKind.ZYPPER: ("zypper", "--non-interactive", "update"),
        ManagerKind.APK: ("apk", "upgrade"),
        ManagerKind.XBPS: ("xbps-install", "-u"),
        ManagerKind.FLATPAK: ("flatpak", "update", "-y"),
    }.get(kind, ())


PROTECTED_NATIVE = frozenset(
    {
        ManagerKind.APT,
        ManagerKind.PACMAN,
        ManagerKind.DNF,
        ManagerKind.YUM,
        ManagerKind.ZYPPER,
        ManagerKind.APK,
        ManagerKind.XBPS,
        ManagerKind.EMERGE,
        ManagerKind.NIX,
    }
)


def retire_helper_argv(kind: ManagerKind) -> tuple[str, ...]:
    """Remove an AUR helper / frontend only. Packages it installed stay in pacman/dpkg db."""
    if kind in PROTECTED_NATIVE:
        raise PackageManagerError(
            f"Rifiuto di rimuovere il gestore nativo {kind.value}.",
            code="pkg.protected",
            hint="Puoi aggiungere nala/paru/flatpak accanto, non al posto di apt/pacman/dnf.",
        )
    # -R without -s/-ns: keep deps that other packages need. Does not touch packages installed *through* the helper.
    if kind in {ManagerKind.YAY, ManagerKind.PARU}:
        return ("pacman", "-R", "--noconfirm", kind.value)
    if kind == ManagerKind.NALA:
        return ("apt-get", "remove", "-y", "nala")
    if kind == ManagerKind.SNAP:
        return ("snap", "remove", "snapd")  # still dangerous — planner marks high risk and asks
    if kind == ManagerKind.FLATPAK:
        raise PackageManagerError(
            "Rimuovere flatpak cancellerebbe il runtime delle app Flatpak. Tessera rifiuta.",
            code="pkg.flatpak_keep",
            hint="Disinstalla singole app flatpak, non il gestore.",
        )
    raise PackageManagerError(f"Non so come dismettere {kind.value} in sicurezza.", code="pkg.retire")
