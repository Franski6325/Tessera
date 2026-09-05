"""Tessera TUI — original mosaic chrome, vim-like movement, command overlay."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    OptionList,
    RichLog,
    Static,
)
from textual.widgets.option_list import Option

from tessera import __version__
from tessera.apply import apply_plan, save_plan
from tessera.apply.planner import build_plan
from tessera.catalog.packages import for_roles
from tessera.catalog.security import CONTROLS
from tessera.detect import collect_snapshot
from tessera.engine.recommend import recommend
from tessera.exceptions import TesseraError
from tessera.i18n import I18n
from tessera.models import (
    ManagerKind,
    PowerProfile,
    RoleId,
    SecurityLevel,
)
from tessera.tui.state import STEPS, Session
from tessera.tui.widgets import Palette, Rail, StatusBar
from tessera.tui.brand import topbar_markup, welcome_banner

CSS = """
Screen {
    background: #0c1117;
    color: #d7e0ea;
}

#chrome {
    height: 100%;
}

#rail {
    width: 22;
    background: #101820;
    border-right: tall #1e2a38;
    padding: 1 0;
    color: #9aabba;
}

#rail-brand {
    padding: 0 1 1 1;
}

#rail-help {
    padding: 1 1 0 1;
}

.rail-btn {
    width: 100%;
    height: 1;
    min-height: 1;
    border: none;
    background: transparent;
    color: #7d8b99;
    text-align: left;
    padding: 0 1;
}

.rail-btn:hover {
    color: #d7e0ea;
    background: #1a2834;
}

.rail-active {
    background: #7ee0c6;
    color: #0c1117;
    text-style: bold;
}

#main {
    width: 1fr;
    height: 1fr;
}

#topbar {
    height: 4;
    padding: 0 2;
    background: #101820;
    border-bottom: tall #1e2a38;
    content-align: left middle;
}

#status {
    height: 1;
    padding: 0 2;
    background: #101820;
    color: #7d8b99;
    border-top: tall #1e2a38;
}

#body {
    padding: 1 2;
    height: 1fr;
}

.title {
    text-style: bold;
    color: #7ee0c6;
    padding-bottom: 1;
}

.kicker {
    color: #e2b36a;
    text-style: italic;
}

.muted {
    color: #7d8b99;
}

.warn {
    color: #e2b36a;
}

.err {
    color: #ef6f6c;
}

.card {
    background: #141b24;
    border: tall #1e2a38;
    padding: 1 2;
    margin-bottom: 1;
}

Button {
    background: #1a2834;
    color: #d7e0ea;
    border: none;
}

Button.-primary {
    background: #7ee0c6;
    color: #0c1117;
    text-style: bold;
}

Button.-danger {
    background: #ef6f6c;
    color: #0c1117;
}

OptionList {
    background: #141b24;
    border: tall #1e2a38;
    height: 1fr;
}

Checkbox {
    background: #141b24;
    padding: 0 1;
}

#palette-overlay {
    align: center middle;
    background: #0c1117 70%;
}

#palette {
    width: 72;
    height: 22;
    background: #141b24;
    border: tall #7ee0c6;
    padding: 1 1;
}

#palette-title {
    text-style: bold;
    color: #7ee0c6;
}

#help-box {
    width: 78;
    height: auto;
    max-height: 24;
    background: #141b24;
    border: tall #e2b36a;
    padding: 1 2;
}

Footer {
    background: #101820;
    color: #7d8b99;
}
"""


class HelpModal(ModalScreen[None]):
    BINDINGS = [Binding("escape,q", "close", "chiudi", show=False)]

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold #e2b36a]tasti[/]\n\n"
            "[bold]j / k[/]  o frecce     sposta selezione / scorre\n"
            "[bold]tab[/]                 cambia pannello\n"
            "[bold]enter[/]               conferma / toggle\n"
            "[bold]n / p[/]               passo successivo / precedente\n"
            "[bold]ctrl+p[/]              palette comandi\n"
            "[bold]r[/]                   ri-scansiona hardware\n"
            "[bold]?[/]                   questo aiuto\n"
            "[bold]q[/]                   esci (chiede conferma dal passo applica)\n\n"
            "[dim]TUI originale. Nessun codice di altri prodotti è stato usato.",
            id="help-box",
        )

    def action_close(self) -> None:
        self.dismiss(None)


class TesseraApp(App[None]):
    CSS = CSS
    TITLE = "tessera"
    BINDINGS = [
        Binding("q", "quit_app", "esci", show=True),
        Binding("question_mark", "help", "aiuto", show=True),
        Binding("ctrl+p", "palette", "comandi", show=True),
        Binding("n", "next_step", "avanti", show=True),
        Binding("p", "prev_step", "indietro", show=True),
        Binding("r", "rescan", "scan", show=False),
        Binding("j", "cursor_down", "giù", show=False),
        Binding("k", "cursor_up", "su", show=False),
    ]

    def __init__(self, lang: str = "it") -> None:
        super().__init__()
        self.i18n = I18n(lang)
        self.session = Session(lang=lang)
        self.session.choices.language = lang
        self.step = "welcome"
        self._palette_open = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="chrome"):
            yield Rail(self.step)
            with Vertical(id="main"):
                yield Static(id="topbar")
                with VerticalScroll(id="body"):
                    yield Static(id="pane")
                yield StatusBar()
        yield Footer()

    def on_mount(self) -> None:
        self._render_top()
        self._render_pane()
        self.query_one(StatusBar).set_host("—", "in attesa della scansione")

    def _render_top(self) -> None:
        num, name = {
            "welcome": ("01", "ingresso"),
            "hardware": ("02", "hardware"),
            "power": ("03", "profilo"),
            "roles": ("04", "ruoli"),
            "security": ("05", "sicurezza"),
            "packages": ("06", "strumenti"),
            "managers": ("07", "gestori"),
            "review": ("08", "revisione"),
            "apply": ("09", "applica"),
        }[self.step]
        self.query_one("#topbar", Static).update(topbar_markup(num, name, __version__))
        self.query_one(Rail).set_current(self.step)

    def goto(self, step: str) -> None:
        if step not in STEPS:
            return
        if step != "welcome" and self.session.snapshot is None:
            if not self._collect():
                return
        self.step = step
        self._render_top()
        self._render_pane()

    def action_next_step(self) -> None:
        i = STEPS.index(self.step)
        if i + 1 < len(STEPS):
            self.goto(STEPS[i + 1])

    def action_prev_step(self) -> None:
        i = STEPS.index(self.step)
        if i > 0:
            self.goto(STEPS[i - 1])

    def action_help(self) -> None:
        self.push_screen(HelpModal())

    def action_palette(self) -> None:
        if self._palette_open:
            return

        class PaletteModal(ModalScreen[str | None]):
            CSS = CSS

            def compose(self) -> ComposeResult:
                with Vertical(id="palette-overlay"):
                    pal = Palette(id="palette")
                    yield pal

            def on_palette_chosen(self, event: Palette.Chosen) -> None:
                self.dismiss(event.command)

            def on_key(self, event) -> None:  # noqa: ANN001
                if event.key == "escape":
                    self.dismiss(None)

        def _done(cmd: str | None) -> None:
            self._palette_open = False
            if cmd:
                self._run_command(cmd)

        self._palette_open = True
        self.push_screen(PaletteModal(), _done)

    def _run_command(self, cmd: str) -> None:
        if cmd == "quit":
            self.exit()
            return
        if cmd == "scan":
            self._scan()
            return
        if cmd == "export":
            self._export()
            return
        if cmd.startswith("goto:"):
            self.goto(cmd.split(":", 1)[1])
            return
        if cmd.startswith("lang:"):
            self.session.lang = cmd.split(":", 1)[1]
            self.notify(f"lingua → {self.session.lang}")

    def action_quit_app(self) -> None:
        self.exit()

    def action_rescan(self) -> None:
        self._scan()

    def action_cursor_down(self) -> None:
        self._nudge_list(1)

    def action_cursor_up(self) -> None:
        self._nudge_list(-1)

    def _nudge_list(self, delta: int) -> None:
        try:
            ol = self.query_one(OptionList)
        except Exception:
            ol = None
        if ol is not None and ol.option_count:
            cur = ol.highlighted or 0
            ol.highlighted = max(0, min(ol.option_count - 1, cur + delta))
            ol.focus()
            return
        boxes = list(self.query(Checkbox))
        if not boxes:
            return
        focused = next((i for i, b in enumerate(boxes) if b.has_focus), -1)
        nxt = min(len(boxes) - 1, max(0, focused + delta))
        boxes[nxt].focus()

    def _collect(self) -> bool:
        pane = self.query_one("#pane", Static)
        pane.update("[italic #9aabba]lettura di /sys, /proc, os-release…[/]")
        try:
            snap = collect_snapshot()
        except TesseraError as exc:
            self.session.scan_error = exc.render()
            pane.update(f"[bold #ef6f6c]{exc.render()}[/]")
            return False
        self.session.snapshot = snap
        self.session.reco = recommend(snap)
        self.session.adopt_recommendation()
        self.session.ensure_managers()
        self.session.seed_packages()
        self.query_one(StatusBar).set_host(
            snap.hostname,
            snap.distro.pretty,
            f"{snap.cpu.cores_logical} cpu · {snap.memory.total_gib:.1f} GiB · {snap.chassis.value}",
        )
        return True

    def _scan(self) -> None:
        if not self._collect():
            return
        self.goto("hardware" if self.step == "welcome" else self.step)

    def _export(self) -> None:
        if not self.session.snapshot:
            self.notify("prima la scansione", severity="warning")
            return
        plan = build_plan(self.session.snapshot, self.session.choices)
        path = save_plan(plan, dry_run=self.session.choices.dry_run)
        self.session.last_plan_path = str(path)
        self.notify(f"piano → {path}")

    def _render_pane(self) -> None:
        body = self.query_one("#body", VerticalScroll)
        extra = [child for child in body.children if child.id != "pane"]
        if extra:
            body.remove_children(extra)
        pane = self.query_one("#pane", Static)
        fn = {
            "welcome": self._pane_welcome,
            "hardware": self._pane_hardware,
            "power": self._pane_power,
            "roles": self._pane_roles,
            "security": self._pane_security,
            "packages": self._pane_packages,
            "managers": self._pane_managers,
            "review": self._pane_review,
            "apply": self._pane_apply,
        }[self.step]
        fn(pane, body)

    def _pane_welcome(self, pane: Static, body: VerticalScroll) -> None:
        pane.update(
            welcome_banner(__version__)
            + "\n"
            + "[#d7e0ea]Tessera legge l'hardware di [bold]questa[/] macchina, propone un profilo "
            "energetico deterministico, e ti fa scegliere ruoli combinabili "
            "(cyber di laboratorio, sviluppo, ops, dati, creativo, quotidiano, privacy, server).\n\n"
            "La sicurezza è a livelli, tutti [bold]modificabili[/]: firewall, sysctl, "
            "politica password, cifratura [italic]verificata ma mai imposta formattando un disco in uso[/].\n\n"
            "[#e2b36a]Uso cyber: solo su sistemi e reti per cui hai autorizzazione scritta. "
            "Nessun exploit è incluso, nessun accesso non autorizzato.[/]\n\n"
            "[dim]Invio o [bold]n[/] per scansionare. Funziona su Debian, Ubuntu, Kali, Arch, "
            "EndeavourOS, Fedora, openSUSE, Alpine, Void e famiglie vicine.[/]"
        )
        row = Horizontal()
        body.mount(row)
        row.mount(Button("scansiona hardware", id="btn-scan", classes="-primary"))
        row.mount(Button("esci", id="btn-quit"))

    def _pane_hardware(self, pane: Static, body: VerticalScroll) -> None:
        snap = self.session.snapshot
        if snap is None:
            pane.update("[italic]nessuna scansione. premi n oppure il pulsante.[/]")
            body.mount(Button("scansiona", id="btn-scan", classes="-primary"))
            return
        gpu_lines = "\n".join(
            f"  • {g.vendor} {g.name}  [dim]{g.driver or 'driver ?'} {'discreta' if g.discrete else 'integrata'}[/]"
            for g in snap.gpu.devices
        ) or "  • nessuna GPU enumerata"
        disks = "\n".join(
            f"  • {d.name}  {d.model}  {d.size_bytes/1e9:.0f} GB  "
            f"{'HDD' if d.rotational else 'SSD/NVMe'}  "
            f"{'cifrato' if d.encrypted else 'in chiaro'}"
            for d in snap.storage.devices[:12]
        ) or "  • —"
        nets = "\n".join(
            f"  • {n.name}  {'up' if n.up else 'down'}  {'wifi' if n.wireless else 'cavo'}  "
            f"{', '.join(n.ipv4) or 'no-ip'}"
            for n in snap.network.interfaces[:10]
        ) or "  • —"
        notes = "\n".join(f"  [yellow]![/] {n.message}" for n in snap.notes[:12])
        therm = ", ".join(
            f"{t.name} {t.celsius:.0f}°C" for t in snap.thermals if t.celsius is not None
        ) or "n/d"
        pane.update(
            f"[class=title]{snap.dmi.vendor or ''} {snap.dmi.product or snap.hostname}[/]\n"
            f"[dim]{snap.distro.pretty} · kernel {snap.distro.kernel} · init {snap.distro.init or '?'} · "
            f"telaio {snap.chassis.value}[/]\n\n"
            f"[#7ee0c6]cpu[/]  {snap.cpu.model}\n"
            f"     {snap.cpu.cores_physical} fisici / {snap.cpu.cores_logical} thread · "
            f"{snap.cpu.arch} · {snap.cpu.max_mhz or 0:.0f} MHz max\n"
            f"     virt: {', '.join(snap.cpu.virtualization_flags) or 'nessun flag'}\n\n"
            f"[#7ee0c6]ram[/]  {snap.memory.total_gib:.1f} GiB  (liberi {snap.memory.available_gib:.1f})  "
            f"swap {snap.memory.swap_bytes/1024**3:.1f} GiB\n\n"
            f"[#7ee0c6]gpu[/]\n{gpu_lines}\n\n"
            f"[#7ee0c6]dischi[/]  root LUKS: {'sì' if snap.storage.root_encrypted else 'no'}\n{disks}\n\n"
            f"[#7ee0c6]rete[/]  host {snap.network.hostname}\n{nets}\n\n"
            f"[#7ee0c6]batteria[/]  "
            + (
                f"{snap.battery.status} {snap.battery.capacity_percent}%"
                if snap.battery.present
                else "assente (desktop/VM)"
            )
            + f"\n[#7ee0c6]termica[/]  {therm}\n"
            + (f"\n{notes}" if notes else "")
        )

    def _pane_power(self, pane: Static, body: VerticalScroll) -> None:
        reco = self.session.reco
        if reco is None:
            pane.update("scansiona prima.")
            return
        lines = [
            "[class=title]profilo energetico[/]",
            f"[class=kicker]consiglio deterministico: {reco.power.value}[/]",
            "",
        ]
        for br in reco.scores:
            mark = "►" if br.profile == self.session.choices.power else " "
            bar = "█" * max(0, min(20, br.score // 5)) + "░" * (20 - max(0, min(20, br.score // 5)))
            lines.append(f"{mark} [bold]{br.profile.value:<12}[/] {bar}  {br.score}")
        lines.append("")
        lines.append("[dim]" + " · ".join(reco.rationale[:6]) + "[/]")
        pane.update("\n".join(lines))
        opts = OptionList(
            *[
                Option(f"{p.value}", id=p.value)
                for p in PowerProfile
            ],
            id="power-list",
        )
        body.mount(opts)
        ids = [p.value for p in PowerProfile]
        try:
            opts.highlighted = ids.index(self.session.choices.power.value)
        except ValueError:
            pass

    def _pane_roles(self, pane: Static, body: VerticalScroll) -> None:
        pane.update(
            "[class=title]ruoli combinabili[/]\n"
            "[dim]Spunta tutte le vite che questa macchina deve fare. "
            "cyber + developer è una workstation da lab perfettamente lecita sulla [bold]tua[/] rete.[/]"
        )
        labels = {
            RoleId.CYBER: "cyber — lab autorizzato, pentest, forensics, blue/red team",
            RoleId.DEVELOPER: "developer — compilatori, git, container, linguaggi",
            RoleId.OPS: "ops / sre — ansible, kubectl, firewall, audit",
            RoleId.DATA: "dati — jupyter, numpy, R",
            RoleId.CREATIVE: "creativo — gimp, obs, blender, kdenlive",
            RoleId.DAILY: "quotidiano — browser, vlc, snapshot, password manager",
            RoleId.PRIVACY: "privacy — firejail, tor launcher, unbound, MAC random",
            RoleId.SERVER: "server — sshd opzionale, cron, headless",
        }
        for role, label in labels.items():
            cb = Checkbox(label, value=role in self.session.choices.roles, id=f"role-{role.value}")
            body.mount(cb)

    def _pane_security(self, pane: Static, body: VerticalScroll) -> None:
        reco = self.session.reco
        hint = reco.security.value if reco else "standard"
        pane.update(
            f"[class=title]livello di sicurezza[/]\n"
            f"[class=kicker]consiglio: {hint}[/]  — ogni controllo è modificabile. "
            f"LUKS non formatta mai un disco già in uso.\n"
        )
        ol = OptionList(
            Option("rilassato — cofanetto password, poco altro", id="relaxed"),
            Option("standard — firewall, aggiornamenti, pwquality, MAC wifi", id="standard"),
            Option("rafforzato — + sysctl, apparmor, auditd, ssh ristretto", id="hardened"),
            Option("fortezza — + usbguard, /tmp tmpfs, firejail, deny default totale", id="fortress"),
            Option("personalizzato — parti dal rafforzato e spunta a mano", id="custom"),
            id="sec-list",
        )
        body.mount(ol)
        for ctrl in CONTROLS:
            enabled = next((t.enabled for t in self.session.choices.toggles if t.id == ctrl.id), False)
            body.mount(
                Checkbox(
                    f"{ctrl.title_it}  [dim]{ctrl.risk}[/]",
                    value=enabled,
                    id=f"sec-{ctrl.id}",
                )
            )

    def _pane_packages(self, pane: Static, body: VerticalScroll) -> None:
        roles = self.session.choices.roles
        if not roles:
            pane.update("[class=title]strumenti[/]\nnessun ruolo: torna indietro e scegline almeno uno.")
            return
        pkgs = for_roles(roles)
        pane.update(
            f"[class=title]strumenti per {', '.join(r.value for r in roles)}[/]\n"
            f"[dim]{len(pkgs)} voci di catalogo. I pesanti sono auto-esclusi sotto gli 8 GiB. "
            f"Puoi spuntare/togliere qualunque cosa. Solo repository ufficiali / AUR / Flathub.[/]"
        )
        selected = set(self.session.choices.selected_packages)
        for pkg in pkgs:
            mark = " · ".join(r.value for r in pkg.roles if r in roles)
            heavy = "  [dim]pesante[/]" if pkg.heavy else ""
            body.mount(
                Checkbox(
                    f"{pkg.id} — {pkg.summary_it}  [dim]{mark}[/]{heavy}",
                    value=pkg.id in selected,
                    id=f"pkg-{pkg.id}",
                )
            )

    def _pane_managers(self, pane: Static, body: VerticalScroll) -> None:
        snap = self.session.snapshot
        if not snap:
            pane.update("scansiona prima.")
            return
        present = [m for m in snap.managers if m.present]
        lines = [
            "[class=title]gestori pacchetti[/]",
            "[dim]yay/paru sono helper AUR: non sostituiscono pacman e non «hanno tutti» i pacchetti "
            "cyber/developer. Dipendono da extra/multilib, da BlackArch (opt-in) e da ciò che esiste in AUR. "
            "Se un tool manca, Tessera propone helper diversi o Flatpak [bold]senza toccare[/] i programmi già installati.[/]",
            "",
        ]
        for m in present:
            tag = []
            if m.native:
                tag.append("nativo")
            if m.helper:
                tag.append("helper")
            if m.locked:
                tag.append("LOCK")
            if m.extra_repos:
                tag.append("repos:" + ",".join(m.extra_repos))
            cur = " ►" if m.kind == self.session.choices.primary_manager else ""
            lines.append(f"{cur} [bold]{m.kind.value}[/]  {m.version or ''}  [dim]{' '.join(tag)}[/]")
            for n in m.notes:
                lines.append(f"     [dim]{n.message}[/]")
        missing = [m.kind.value for m in snap.managers if not m.present and m.kind in {ManagerKind.YAY, ManagerKind.PARU, ManagerKind.NALA, ManagerKind.FLATPAK, ManagerKind.PIPX}]
        if missing:
            lines.append("")
            lines.append("[dim]non presenti (installabili come extra): " + ", ".join(missing) + "[/]")
        pane.update("\n".join(lines))

        ol = OptionList(id="mgr-list")
        body.mount(ol)
        for m in present:
            if m.kind in {ManagerKind.SNAP}:
                continue
            ol.add_option(Option(f"primario: {m.kind.value}", id=f"pri-{m.kind.value}"))
        body.mount(Checkbox("abilita extra BlackArch (solo Arch, strap ufficiale tuo)", value=self.session.choices.enable_blackarch, id="opt-blackarch"))
        body.mount(Checkbox("usa Flatpak/Flathub come extra (non rimuove nulla)", value=self.session.choices.enable_flatpak, id="opt-flatpak"))
        body.mount(Checkbox("usa pipx come extra per tool Python isolati", value=ManagerKind.PIPX in self.session.choices.extra_managers, id="opt-pipx"))
        yay = next((m for m in present if m.kind == ManagerKind.YAY), None)
        paru = next((m for m in present if m.kind == ManagerKind.PARU), None)
        if yay:
            body.mount(
                Checkbox(
                    "dismetti yay (i pacchetti AUR restano in pacman; non usa -Rns)",
                    value=ManagerKind.YAY in self.session.choices.retire_helpers,
                    id="ret-yay",
                )
            )
        if paru:
            body.mount(
                Checkbox(
                    "dismetti paru (stesso trattamento: solo l'helper, non le app)",
                    value=ManagerKind.PARU in self.session.choices.retire_helpers,
                    id="ret-paru",
                )
            )
        nala = next((m for m in present if m.kind == ManagerKind.NALA), None)
        if nala:
            body.mount(
                Checkbox(
                    "dismetti nala (apt resta, i .deb restano)",
                    value=ManagerKind.NALA in self.session.choices.retire_helpers,
                    id="ret-nala",
                )
            )

    def _pane_review(self, pane: Static, body: VerticalScroll) -> None:
        if not self.session.snapshot:
            pane.update("scansiona prima.")
            return
        plan = build_plan(self.session.snapshot, self.session.choices)
        warns = "\n".join(f"[yellow]![/] {w}" for w in plan.warnings) or "[dim]nessun warning[/]"
        steps = "\n".join(
            f"  [dim]{s.risk:>6}[/]  {s.title}  [dim]{' '.join(s.command[:4])}[/]"
            for s in plan.steps[:80]
        )
        pane.update(
            f"[class=title]revisione piano[/]  [dim]{plan.journal_id} · {len(plan.steps)} passi[/]\n"
            f"{warns}\n\n{steps}"
        )
        body.mount(
            Checkbox(
                "dry-run (nessuna modifica reale) — lascia acceso finché non sei sicuro",
                value=self.session.choices.dry_run,
                id="opt-dry",
            )
        )
        body.mount(Button("esporta script", id="btn-export"))

    def _pane_apply(self, pane: Static, body: VerticalScroll) -> None:
        pane.update(
            "[class=title]applica[/]\n"
            "Il default è la [bold]simulazione[/]. L'esecuzione reale richiede il pulsante rosso "
            "e, per i passi privileged, sudo/root.\n"
            "[dim]I journal stanno in ~/.local/state/tessera/journal — i piani in ~/.local/share/tessera/plans.[/]"
        )
        log = RichLog(id="apply-log", highlight=True, markup=True)
        body.mount(log)
        for line in self.session.apply_log[-50:]:
            log.write(line)
        row = Horizontal()
        body.mount(row)
        row.mount(Button("simula", id="btn-dry", classes="-primary"))
        row.mount(Button("applica sul serio", id="btn-live", classes="-danger"))
        row.mount(Button("esporta script", id="btn-export"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("step-"):
            self.goto(bid[5:])
            return
        if bid == "btn-quit":
            self.exit()
        elif bid == "btn-scan":
            self._scan()
        elif bid == "btn-export":
            self._export()
        elif bid == "btn-dry":
            self._do_apply(dry=True, confirm=True)
        elif bid == "btn-live":
            self._do_apply(dry=False, confirm=True)

    def _do_apply(self, *, dry: bool, confirm: bool) -> None:
        if not self.session.snapshot:
            self.notify("scansiona prima", severity="error")
            return
        self.session.choices.dry_run = dry
        plan = build_plan(self.session.snapshot, self.session.choices)
        logw = None
        try:
            logw = self.query_one("#apply-log", RichLog)
        except Exception:
            pass
        try:
            results = apply_plan(plan, dry_run=dry, confirm_live=confirm)
        except TesseraError as exc:
            self.session.apply_log.append(exc.render())
            if logw:
                logw.write(f"[red]{exc.render()}[/]")
            self.notify(exc.args[0], severity="error")
            return
        for r in results:
            flag = "skip" if r.skipped else ("ok" if r.ok else "fail")
            line = f"{flag}  {r.title}  {r.output[:160]}"
            self.session.apply_log.append(line)
            if logw:
                logw.write(line)
        self.notify(f"{'simulati' if dry else 'eseguiti'} {len(results)} passi")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cid = event.checkbox.id or ""
        val = event.value
        if cid.startswith("role-"):
            role = RoleId(cid.split("-", 1)[1])
            if val and role not in self.session.choices.roles:
                self.session.choices.roles.append(role)
            if not val and role in self.session.choices.roles:
                self.session.choices.roles.remove(role)
            if val:
                # add recommended packages of this role
                self.session.seed_packages()
            return
        if cid.startswith("pkg-"):
            pid = cid[4:]
            if val and pid not in self.session.choices.selected_packages:
                self.session.choices.selected_packages.append(pid)
            if not val and pid in self.session.choices.selected_packages:
                self.session.choices.selected_packages.remove(pid)
            return
        if cid.startswith("sec-"):
            sid = cid[4:]
            for t in self.session.choices.toggles:
                if t.id == sid:
                    t.enabled = val
                    break
            self.session.choices.security = SecurityLevel.CUSTOM
            return
        if cid == "opt-blackarch":
            self.session.choices.enable_blackarch = val
        elif cid == "opt-flatpak":
            self.session.choices.enable_flatpak = val
            if val and ManagerKind.FLATPAK not in self.session.choices.extra_managers:
                self.session.choices.extra_managers.append(ManagerKind.FLATPAK)
            if not val and ManagerKind.FLATPAK in self.session.choices.extra_managers:
                self.session.choices.extra_managers.remove(ManagerKind.FLATPAK)
        elif cid == "opt-pipx":
            if val and ManagerKind.PIPX not in self.session.choices.extra_managers:
                self.session.choices.extra_managers.append(ManagerKind.PIPX)
            if not val and ManagerKind.PIPX in self.session.choices.extra_managers:
                self.session.choices.extra_managers.remove(ManagerKind.PIPX)
        elif cid == "ret-yay":
            self._retire(ManagerKind.YAY, val)
        elif cid == "ret-paru":
            self._retire(ManagerKind.PARU, val)
        elif cid == "ret-nala":
            self._retire(ManagerKind.NALA, val)
        elif cid == "opt-dry":
            self.session.choices.dry_run = val

    def _retire(self, kind: ManagerKind, val: bool) -> None:
        if val and kind not in self.session.choices.retire_helpers:
            self.session.choices.retire_helpers.append(kind)
        if not val and kind in self.session.choices.retire_helpers:
            self.session.choices.retire_helpers.remove(kind)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option_id or event.option.id or ""
        if self.step == "power" and oid in {p.value for p in PowerProfile}:
            self.session.choices.power = PowerProfile(oid)
            self._render_pane()
        elif self.step == "security" and oid in {s.value for s in SecurityLevel}:
            self.session.set_security(SecurityLevel(oid))
            self._render_pane()
        elif oid.startswith("pri-"):
            self.session.choices.primary_manager = ManagerKind(oid[4:])
            self._render_pane()
