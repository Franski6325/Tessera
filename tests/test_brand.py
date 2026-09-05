from tessera.tui.brand import STAR_GLYPH, STAR_LOCKUP, topbar_markup, welcome_banner, wordmark


def test_star_is_eight_pointed_rectilinear():
    assert STAR_GLYPH == "\u2738"
    assert STAR_LOCKUP[1] == "╱╲╳╱╲"
    assert "╱" in STAR_LOCKUP[0]


def test_wordmark_and_lockups_include_version():
    mark = wordmark("1.0.0")
    assert mark.startswith("✸")
    assert "tessera 1.0.0" in mark
    top = topbar_markup("01", "ingresso", "1.0.0")
    assert "tessera" in top
    assert "1.0.0" in top
    assert "╳" in top
    banner = welcome_banner("1.0.0")
    assert "tessera" in banner
    assert "1.0.0" in banner
    assert "╱╲╱  ╲╱╲" in banner
