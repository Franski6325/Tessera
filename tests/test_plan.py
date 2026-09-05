from tessera.apply.internal import SYSCTL_BODY, dispatch
from tessera.apply.planner import build_plan
from tessera.catalog.security import defaults_for
from tessera.models import PowerProfile, RoleId, SecurityLevel, UserChoices
from tessera.tui.state import Session

from conftest import snap


def test_plan_contains_firewall_and_packages():
    s = snap()
    choices = UserChoices(
        power=PowerProfile.BALANCED,
        roles=[RoleId.CYBER, RoleId.DEVELOPER],
        security=SecurityLevel.HARDENED,
        toggles=defaults_for(SecurityLevel.HARDENED),
        selected_packages=["nmap", "git", "ripgrep"],
        primary_manager=__import__("tessera.models", fromlist=["ManagerKind"]).ManagerKind.PACMAN,
        dry_run=True,
    )
    plan = build_plan(s, choices)
    titles = " ".join(st.title.lower() for st in plan.steps)
    assert "nmap" in titles or "già presente" in titles or "installa" in titles
    assert any(st.kind == "firewall" for st in plan.steps)
    assert any(st.kind == "sysctl" for st in plan.steps)
    assert plan.warnings  # cyber legal warning


def test_luks_never_formats():
    s = snap(encrypted=False)
    choices = UserChoices(
        security=SecurityLevel.FORTRESS,
        toggles=defaults_for(SecurityLevel.FORTRESS),
        roles=[RoleId.DAILY],
    )
    plan = build_plan(s, choices)
    luks = [st for st in plan.steps if "luks" in st.id or "cifr" in st.title.lower() or "LUKS" in st.title]
    assert luks
    for st in luks:
        joined = " ".join(st.command).lower()
        assert "mkfs" not in joined
        assert "cryptsetup luksFormat" not in joined
        assert st.kind == "info"


def test_sysctl_dry_does_not_write(tmp_path, monkeypatch):
    msg = dispatch("sysctl", [], dry=True)
    assert "DRY" in msg
    assert "kernel.randomize_va_space" in SYSCTL_BODY


def test_session_seed_skips_heavy_on_low_ram():
    s = snap(ram_gib=4)
    sess = Session(snapshot=s)
    sess.choices.roles = [RoleId.CREATIVE]
    sess.seed_packages()
    assert "blender" not in sess.choices.selected_packages
