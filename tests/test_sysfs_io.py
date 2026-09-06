from pathlib import Path

from tessera.detect._io import read_text


def test_einval_returns_default(tmp_path, monkeypatch):
    target = tmp_path / "speed"

    def boom(_self, *args, **kwargs):
        raise OSError(22, "Invalid argument")

    monkeypatch.setattr(Path, "read_bytes", boom)
    assert read_text(target, default=None) is None
    assert read_text(target, default="x") == "x"


def test_eacces_returns_default(tmp_path, monkeypatch):
    target = tmp_path / "product_serial"

    def boom(_self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_bytes", boom)
    assert read_text(target, default="") == ""
    assert read_text(target, default=None) is None
