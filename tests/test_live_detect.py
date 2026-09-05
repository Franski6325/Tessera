from tessera.detect import collect_snapshot
from tessera.engine.recommend import recommend
from tessera.models import ChassisKind


def test_collects_on_this_linux():
    snap = collect_snapshot()
    assert snap.cpu.cores_logical >= 1
    assert snap.memory.total_bytes > 0
    assert snap.distro.pretty
    assert snap.hostname
    reco = recommend(snap)
    assert reco.power
    assert reco.scores
    # this cloud environment is typically a VM or container
    assert snap.chassis in set(ChassisKind)
