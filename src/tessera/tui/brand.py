"""Brand mark: eight-pointed star of two overlapping rhombi (thin line art)."""

from __future__ import annotations

from tessera import __version__

# U+2738 HEAVY EIGHT POINTED RECTILINEAR BLACK STAR — two diamonds, one rotated 45°.
STAR_GLYPH = "✸"

# Compact 3-line compass-rose made of ╱ ╲ ╳ (the same two-rhombus geometry).
STAR_LOCKUP = (
    "  ╱╲",
    "╱╲╳╱╲",
    "  ╲╱",
)


def wordmark(version: str | None = None) -> str:
    v = version or __version__
    return f"{STAR_GLYPH} tessera {v}"


def topbar_markup(step_num: str, step_name: str, version: str | None = None) -> str:
    v = version or __version__
    a, b, c = STAR_LOCKUP
    ink = "#e8eef4"
    mint = "#7ee0c6"
    muted = "#7d8b99"
    return (
        f"[bold {ink}]{a}[/]   [bold {mint}]{step_num}  {step_name}[/]\n"
        f"[bold {ink}]{b}[/]  [bold {mint}]tessera[/] [dim]{v}[/]\n"
        f"[bold {ink}]{c}[/]   [dim {muted}]mosaico tastiera-first[/]"
    )


def welcome_banner(version: str | None = None) -> str:
    v = version or __version__
    ink = "#e8eef4"
    mint = "#7ee0c6"
    muted = "#9aabba"
    return (
        f"[bold {ink}]      ╱╲[/]\n"
        f"[bold {ink}]   ╱╲╱  ╲╱╲[/]   [bold {mint}]tessera[/]  [dim]{v}[/]\n"
        f"[bold {ink}]   ╲╱╲  ╱╲╱[/]   [italic {muted}]mosaico del tuo linux[/]\n"
        f"[bold {ink}]      ╲╱[/]\n"
    )


def rail_brand() -> str:
    ink = "#e8eef4"
    mint = "#7ee0c6"
    a, b, c = STAR_LOCKUP
    return (
        f"[bold {ink}]{a}[/]\n"
        f"[bold {ink}]{b}[/] [bold {mint}]tessera[/]\n"
        f"[bold {ink}]{c}[/]\n"
        f"[dim]─────────[/]"
    )
