from tessera.engine.recommend import recommend
from tessera.models import ChassisKind, PowerProfile, SecurityLevel

from conftest import snap


def test_desktop_powerful_prefers_performance():
    reco = recommend(
        snap(
            chassis=ChassisKind.DESKTOP,
            battery=False,
            cap=None,
            ram_gib=64,
            cores=16,
            discrete=True,
        )
    )
    assert reco.power == PowerProfile.PERFORMANCE


def test_laptop_low_battery_prefers_battery():
    reco = recommend(snap(chassis=ChassisKind.LAPTOP, battery=True, cap=12, ram_gib=16, cores=8))
    assert reco.power == PowerProfile.BATTERY


def test_hot_cpu_prefers_quiet():
    reco = recommend(snap(hot=True, battery=True, cap=80))
    assert reco.power in {PowerProfile.QUIET, PowerProfile.BATTERY}


def test_same_snapshot_same_recommendation():
    s = snap()
    a = recommend(s)
    b = recommend(s)
    assert a == b
    assert a.power == b.power
    assert a.scores == b.scores


def test_encrypted_laptop_hardens_security():
    reco = recommend(snap(encrypted=True, chassis=ChassisKind.LAPTOP))
    assert reco.security in {SecurityLevel.HARDENED, SecurityLevel.FORTRESS}


def test_live_usb_relaxes_security():
    reco = recommend(snap(live=True))
    assert reco.security == SecurityLevel.RELAXED


def test_kali_hints_cyber():
    from tessera.models import RoleId

    reco = recommend(snap(distro_id="kali", family=__import__("tessera.models", fromlist=["DistroFamily"]).DistroFamily.KALI))
    assert RoleId.CYBER in reco.roles_hint
