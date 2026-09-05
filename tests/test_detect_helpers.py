from tessera.detect.distro import _family, _parse_os_release
from tessera.detect._io import redact_serial
from tessera.i18n import I18n, detect_lang
from tessera.models import DistroFamily


def test_os_release_endeavouros():
    parsed = _parse_os_release(
        'NAME="EndeavourOS"\nID=endeavouros\nID_LIKE=arch\nPRETTY_NAME="EndeavourOS"\n'
    )
    assert parsed["ID"] == "endeavouros"
    fam = _family(parsed["ID"], ("arch",))
    assert fam == DistroFamily.ARCH


def test_kali_family():
    assert _family("kali", ("debian",)) == DistroFamily.KALI


def test_ubuntu_like():
    assert _family("linuxmint", ("ubuntu", "debian")) == DistroFamily.UBUNTU


def test_redact_serial():
    assert redact_serial("ABC123XYZ") == "AB…YZ"
    assert redact_serial("None") is None
    assert redact_serial("") is None


def test_lang_from_env(monkeypatch):
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.delenv("TESSERA_LANG", raising=False)
    assert detect_lang() == "en"
    monkeypatch.setenv("LANG", "it_IT.UTF-8")
    assert detect_lang() == "it"


def test_i18n_fallback():
    i = I18n("it")
    assert "Tessera" in i.t("app.title")
    assert i.t("does.not.exist") == "does.not.exist"
