"""CLI: TUI by default, plus machine-readable subcommands for scripting."""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tessera import __version__
from tessera.apply import apply_plan, save_plan
from tessera.apply.internal import dispatch
from tessera.apply.planner import build_plan, plan_json
from tessera.detect import collect_snapshot
from tessera.engine.recommend import recommend
from tessera.exceptions import TesseraError
from tessera.i18n import detect_lang
from tessera.models import (
    PowerProfile,
    RoleId,
    SecurityLevel,
    UserChoices,
)
from tessera.catalog.security import defaults_for
from tessera.serialize import dumps
from tessera.tui.brand import STAR_GLYPH, wordmark

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    pretty_exceptions_enable=False,
    help="Tessera — mosaico hardware, ruoli, sicurezza e pacchetti per Linux.",
)
console = Console(stderr=False)


def _fail(exc: BaseException) -> None:
    if isinstance(exc, TesseraError):
        console.print(f"[red]{exc.render()}[/]")
    else:
        console.print(f"[red]{type(exc).__name__}: {exc}[/]")
    raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="Versione"),
    lang: Optional[str] = typer.Option(None, "--lang", help="it|en"),
) -> None:
    if version:
        console.print(wordmark(__version__))
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        from tessera.tui.app import TesseraApp

        TesseraApp(lang=detect_lang(lang)).run()


@app.command("detect")
def cmd_detect(
    json_out: bool = typer.Option(False, "--json", help="JSON sullo stdout"),
) -> None:
    """Scansiona hardware, distro e gestori pacchetti."""
    try:
        snap = collect_snapshot()
    except TesseraError as exc:
        _fail(exc)
        return
    if json_out:
        console.print(dumps(snap))
        return
    _print_snapshot(snap)


@app.command("recommend")
def cmd_recommend(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Profilo energetico e sicurezza deterministici."""
    try:
        snap = collect_snapshot()
        reco = recommend(snap)
    except TesseraError as exc:
        _fail(exc)
        return
    if json_out:
        console.print(dumps(reco))
        return
    table = Table(title="punteggi profilo", show_header=True, header_style="bold")
    table.add_column("profilo")
    table.add_column("score", justify="right")
    table.add_column("perché")
    for br in reco.scores:
        mark = "► " if br.profile == reco.power else "  "
        table.add_row(mark + br.profile.value, str(br.score), "; ".join(br.reasons[:3]))
    console.print(table)
    console.print(f"sicurezza consigliata: [bold]{reco.security.value}[/]")
    console.print("ruoli suggeriti: " + ", ".join(r.value for r in reco.roles_hint))


@app.command("managers")
def cmd_managers(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Elenca gestori visibili e lock."""
    try:
        snap = collect_snapshot()
    except TesseraError as exc:
        _fail(exc)
        return
    if json_out:
        console.print(dumps(list(snap.managers)))
        return
    table = Table(title="gestori")
    table.add_column("kind")
    table.add_column("presente")
    table.add_column("nativo")
    table.add_column("helper")
    table.add_column("lock")
    table.add_column("repos")
    for m in snap.managers:
        if not m.present:
            continue
        table.add_row(
            m.kind.value,
            "sì",
            "sì" if m.native else "",
            "sì" if m.helper else "",
            m.lock_reason or "",
            ",".join(m.extra_repos),
        )
    console.print(table)
    console.print(
        "[dim]yay/paru non sono un catalogo completo: wrapper AUR sopra pacman. "
        "I pacchetti cyber extra su Arch stanno in BlackArch o in AUR, non «dentro yay».[/]"
    )


@app.command("plan")
def cmd_plan(
    power: Optional[str] = typer.Option(None, "--power"),
    roles: Optional[str] = typer.Option(None, "--roles", help="csv: cyber,developer"),
    security: Optional[str] = typer.Option(None, "--security"),
    dry_run: bool = typer.Option(True, "--dry-run/--live"),
    json_out: bool = typer.Option(False, "--json"),
    export: bool = typer.Option(False, "--export", help="Scrive script in XDG data dir"),
) -> None:
    """Costruisce il piano senza eseguirlo."""
    try:
        snap = collect_snapshot()
        reco = recommend(snap)
        choices = UserChoices(
            power=PowerProfile(power) if power else reco.power,
            roles=_parse_roles(roles) or list(reco.roles_hint),
            security=SecurityLevel(security) if security else reco.security,
            toggles=defaults_for(SecurityLevel(security) if security else reco.security),
            dry_run=dry_run,
        )
        from tessera.tui.state import Session

        sess = Session(snapshot=snap, reco=reco, choices=choices)
        sess.ensure_managers()
        sess.seed_packages()
        plan = build_plan(snap, sess.choices)
    except (TesseraError, ValueError) as exc:
        _fail(exc)
        return
    if json_out:
        console.print(plan_json(plan))
        return
    for w in plan.warnings:
        console.print(f"[yellow]![/] {w}")
    table = Table(title=f"piano {plan.journal_id}")
    table.add_column("#", justify="right")
    table.add_column("rischio")
    table.add_column("passo")
    table.add_column("comando")
    for i, s in enumerate(plan.steps, 1):
        table.add_row(str(i), s.risk, s.title, " ".join(s.command[:6]))
    console.print(table)
    if export:
        path = save_plan(plan, dry_run=dry_run)
        console.print(f"script → {path}")


@app.command("apply")
def cmd_apply(
    power: Optional[str] = typer.Option(None, "--power"),
    roles: Optional[str] = typer.Option(None, "--roles"),
    security: Optional[str] = typer.Option(None, "--security"),
    dry_run: bool = typer.Option(True, "--dry-run/--live"),
    yes: bool = typer.Option(False, "--yes", help="Conferma applicazione live"),
) -> None:
    """Esegue il piano (default: simulazione)."""
    try:
        snap = collect_snapshot()
        reco = recommend(snap)
        choices = UserChoices(
            power=PowerProfile(power) if power else reco.power,
            roles=_parse_roles(roles) or list(reco.roles_hint),
            security=SecurityLevel(security) if security else reco.security,
            toggles=defaults_for(SecurityLevel(security) if security else reco.security),
            dry_run=dry_run,
        )
        from tessera.tui.state import Session

        sess = Session(snapshot=snap, reco=reco, choices=choices)
        sess.ensure_managers()
        sess.seed_packages()
        plan = build_plan(snap, sess.choices)
        results = apply_plan(plan, dry_run=dry_run, confirm_live=yes or dry_run)
    except TesseraError as exc:
        _fail(exc)
        return
    for r in results:
        style = "dim" if r.skipped else ("green" if r.ok else "red")
        console.print(f"[{style}]{'skip' if r.skipped else 'ok' if r.ok else 'fail'}[/] {r.title}")


@app.command("apply-internal")
def cmd_apply_internal(
    verb: str = typer.Argument(...),
    extra: list[str] = typer.Argument(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Passi di hardening idempotenti (usati dallo script esportato)."""
    try:
        msg = dispatch(verb, extra or [], dry=dry_run)
    except TesseraError as exc:
        _fail(exc)
        return
    console.print(msg)


def _parse_roles(raw: str | None) -> list[RoleId]:
    if not raw:
        return []
    out: list[RoleId] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(RoleId(part))
    return out


def _print_snapshot(snap) -> None:  # noqa: ANN001
    head = Text()
    head.append(snap.hostname + "\n", style="bold cyan")
    head.append(f"{snap.distro.pretty} · {snap.chassis.value} · {snap.cpu.arch}\n", style="dim")
    console.print(Panel(head, title=f"{STAR_GLYPH} tessera detect", border_style="cyan"))
    t = Table(show_header=False)
    t.add_row("cpu", f"{snap.cpu.model} ({snap.cpu.cores_physical}c/{snap.cpu.cores_logical}t)")
    t.add_row("ram", f"{snap.memory.total_gib:.1f} GiB")
    t.add_row(
        "gpu",
        ", ".join(f"{g.vendor} {g.name}" for g in snap.gpu.devices) or "—",
    )
    t.add_row(
        "dischi",
        ", ".join(d.name for d in snap.storage.devices) or "—",
    )
    t.add_row("luks root", "sì" if snap.storage.root_encrypted else "no")
    t.add_row(
        "batteria",
        f"{snap.battery.capacity_percent}%" if snap.battery.present else "no",
    )
    console.print(t)
    if snap.notes:
        console.print("[yellow]note[/]")
        for n in snap.notes[:15]:
            console.print(f"  • {n.message}")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[dim]interrotto[/]")
        sys.exit(130)


if __name__ == "__main__":
    main()
