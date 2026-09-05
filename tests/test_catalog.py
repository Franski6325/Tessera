import pytest

from tessera.catalog.packages import by_id, for_roles, name_for
from tessera.catalog.security import CONTROLS, defaults_for
from tessera.models import DistroFamily, RoleId, SecurityLevel
from tessera.pkg.resolve import PROTECTED_NATIVE, resolve_install, retire_helper_argv
from tessera.exceptions import PackageManagerError
from tessera.models import ManagerKind


def test_cyber_and_developer_union():
    pkgs = for_roles([RoleId.CYBER, RoleId.DEVELOPER])
    ids = {p.id for p in pkgs}
    assert "nmap" in ids
    assert "git" in ids
    assert "build-essential" in ids
    assert "sqlmap" in ids


def test_nmap_on_every_family():
    pkg = by_id("nmap")
    assert pkg is not None
    for family in DistroFamily:
        if family == DistroFamily.UNKNOWN:
            continue
        assert name_for(pkg, family) == "nmap"


def test_missing_package_marked_missing():
    pkg = by_id("nuclei")
    assert pkg is not None
    spec = resolve_install(pkg, DistroFamily.DEBIAN, ManagerKind.APT)
    assert spec.via == "missing"
    spec2 = resolve_install(pkg, DistroFamily.ARCH, ManagerKind.YAY)
    assert spec2.via in {"aur", "missing"}


def test_cannot_retire_pacman():
    with pytest.raises(PackageManagerError) as ei:
        retire_helper_argv(ManagerKind.PACMAN)
    assert ei.value.code == "pkg.protected"
    assert ManagerKind.PACMAN in PROTECTED_NATIVE


def test_retire_yay_keeps_deps():
    argv = retire_helper_argv(ManagerKind.YAY)
    assert argv[0] == "pacman"
    assert "-R" in argv
    assert "-Rns" not in " ".join(argv)
    assert "yay" in argv


def test_fortress_enables_usbguard():
    toggles = {t.id: t.enabled for t in defaults_for(SecurityLevel.FORTRESS)}
    assert toggles["usbguard"] is True
    assert toggles["firewall_inbound_deny"] is True
    assert toggles["firewall_allow_ssh"] is False


def test_relaxed_keeps_vault():
    toggles = {t.id: t.enabled for t in defaults_for(SecurityLevel.RELAXED)}
    assert toggles["password_store"] is True
    assert toggles["kernel_sysctl"] is False


def test_all_controls_have_copy():
    assert len(CONTROLS) >= 12
    for c in CONTROLS:
        assert c.title_it
        assert c.blurb_it
