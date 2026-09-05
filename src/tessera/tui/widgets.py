"""Chrome widgets: mosaic rail, status, palette. Original layout — not derived from any other TUI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from tessera.tui.state import STEPS
from tessera.tui.brand import rail_brand

STEP_LABEL = {
    "welcome": ("01", "ingresso"),
    "hardware": ("02", "hardware"),
    "power": ("03", "profilo"),
    "roles": ("04", "ruoli"),
    "security": ("05", "sicurezza"),
    "packages": ("06", "strumenti"),
    "managers": ("07", "gestori"),
    "review": ("08", "revisione"),
    "apply": ("09", "applica"),
}


class StepPicked(Message):
    def __init__(self, step: str) -> None:
        super().__init__()
        self.step = step


class Rail(Vertical):
    """Vertical mosaic of steps — clickable, keyboard still lives on the app."""

    def __init__(self, current: str = "welcome") -> None:
        super().__init__(id="rail")
        self.current = current

    def compose(self) -> ComposeResult:
        yield Static(rail_brand(), id="rail-brand")
        for key in STEPS:
            num, name = STEP_LABEL[key]
            yield Button(f"{num}  {name}", id=f"step-{key}", classes="rail-btn")
        yield Static("[dim]ctrl+p cmd\n? aiuto\nn/p passi[/]", id="rail-help")

    def on_mount(self) -> None:
        self.set_current(self.current)

    def set_current(self, step: str) -> None:
        self.current = step
        for key in STEPS:
            try:
                btn = self.query_one(f"#step-{key}", Button)
            except Exception:
                continue
            if key == step:
                btn.add_class("rail-active")
            else:
                btn.remove_class("rail-active")


class StatusBar(Static):
    def __init__(self) -> None:
        super().__init__(id="status")

    def set_host(self, host: str, distro: str, extra: str = "") -> None:
        bits = [f"[bold]{host}[/]", distro]
        if extra:
            bits.append(extra)
        self.update("  ·  ".join(bits))


class Palette(Vertical):
    class Closed(Message):
        pass

    class Chosen(Message):
        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    COMMANDS = (
        ("goto:welcome", "Vai a ingresso"),
        ("goto:hardware", "Vai a hardware"),
        ("goto:power", "Vai a profilo energetico"),
        ("goto:roles", "Vai a ruoli"),
        ("goto:security", "Vai a sicurezza"),
        ("goto:packages", "Vai a strumenti"),
        ("goto:managers", "Vai a gestori pacchetti"),
        ("goto:review", "Vai a revisione"),
        ("goto:apply", "Vai ad applica"),
        ("scan", "Ri-esegui scansione hardware"),
        ("lang:it", "Lingua: italiano"),
        ("lang:en", "Language: English"),
        ("export", "Esporta piano come script"),
        ("quit", "Esci"),
    )

    def compose(self) -> ComposeResult:
        yield Label("comandi", id="palette-title")
        yield Input(placeholder="filtra…", id="palette-input")
        yield ListView(id="palette-list")

    def on_mount(self) -> None:
        self._fill("")
        self.query_one("#palette-input", Input).focus()

    def _fill(self, needle: str) -> None:
        needle = needle.lower().strip()
        lv = self.query_one("#palette-list", ListView)
        lv.clear()
        for cmd, label in self.COMMANDS:
            if needle and needle not in cmd and needle not in label.lower():
                continue
            item = ListItem(Label(f"{label}  [dim]{cmd}[/]"))
            item.data_cmd = cmd  # type: ignore[attr-defined]
            lv.append(item)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._fill(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        lv = self.query_one("#palette-list", ListView)
        if lv.children:
            first = lv.children[0]
            cmd = getattr(first, "data_cmd", None)
            if cmd:
                self.post_message(self.Chosen(cmd))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        cmd = getattr(event.item, "data_cmd", None)
        if cmd:
            self.post_message(self.Chosen(cmd))
