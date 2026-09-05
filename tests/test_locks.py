from pathlib import Path

from tessera.detect.managers import _inode_held, _locked
from tessera.models import ManagerKind


def test_apt_lock_file_existence_is_not_enough(tmp_path, monkeypatch):
    # Ubuntu always has the lock file; without /proc/locks match it is idle.
    fake = tmp_path / "lock-frontend"
    fake.write_text("")
    from tessera.detect import managers as m

    monkeypatch.setitem(m._LOCKS, ManagerKind.APT, fake)
    locked, reason = m._locked(ManagerKind.APT)
    assert locked is False
    assert reason is None


def test_inode_held_empty_file(tmp_path):
    p = tmp_path / "x"
    p.write_text("hi")
    assert _inode_held(p) is False
