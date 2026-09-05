"""Execute a plan: journal every step, stop on failure unless skippable."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tessera.apply import internal
from tessera.apply.planner import plan_to_script
from tessera.exceptions import ApplyError, UserAbort
from tessera.models import ApplyPlan, PlanStep
from tessera.paths import ensure_layout, journal_dir, plans_dir


@dataclass
class StepResult:
    id: str
    title: str
    ok: bool
    output: str
    skipped: bool = False


def save_plan(plan: ApplyPlan, *, dry_run: bool) -> Path:
    ensure_layout()
    stamp = plan.journal_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = plans_dir() / f"{stamp}.sh"
    dest.write_text(plan_to_script(plan, dry_run=dry_run), encoding="utf-8")
    dest.chmod(0o750)
    json_path = plans_dir() / f"{stamp}.json"
    from tessera.apply.planner import plan_json

    json_path.write_text(plan_json(plan), encoding="utf-8")
    return dest


def apply_plan(plan: ApplyPlan, *, dry_run: bool, confirm_live: bool) -> list[StepResult]:
    if not dry_run and not confirm_live:
        raise UserAbort("Applicazione reale senza conferma.", code="apply.noconfirm")
    ensure_layout()
    journal = journal_dir() / f"{plan.journal_id}.jsonl"
    results: list[StepResult] = []
    script = save_plan(plan, dry_run=dry_run)
    _log(journal, {"event": "start", "dry_run": dry_run, "script": str(script), "steps": len(plan.steps)})

    for step in plan.steps:
        if step.skip_if == "container" and _in_container():
            res = StepResult(step.id, step.title, True, "skipped: container", skipped=True)
            results.append(res)
            _log(journal, {"event": "skip", **_step_dict(res)})
            continue
        try:
            output = _run_step(step, dry_run=dry_run)
            res = StepResult(step.id, step.title, True, output)
        except Exception as exc:  # noqa: BLE001
            res = StepResult(step.id, step.title, False, str(exc))
            results.append(res)
            _log(journal, {"event": "fail", **_step_dict(res)})
            raise ApplyError(
                f"Passo «{step.title}» fallito: {exc}",
                code="apply.step",
                hint=f"Journal: {journal}. I passi precedenti restano applicati; niente rollback automatico dei pacchetti.",
            ) from exc
        results.append(res)
        _log(journal, {"event": "ok", **_step_dict(res)})
    _log(journal, {"event": "done", "ok": True})
    return results


def _run_step(step: PlanStep, *, dry_run: bool) -> str:
    if not step.command or step.command == ("true",) or step.kind == "info":
        return step.notes or "info"
    if step.command[0] == "tessera-internal":
        verb = step.command[1] if len(step.command) > 1 else ""
        extra = list(step.command[2:])
        return internal.dispatch(verb, extra, dry=dry_run)
    if dry_run:
        return "DRY " + " ".join(step.command)
    proc = subprocess.run(
        list(step.command),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=1800,
        env={**os.environ, "LC_ALL": "C", "DEBIAN_FRONTEND": "noninteractive"},
    )
    if proc.returncode != 0:
        raise ApplyError(proc.stdout[-4000:] or f"exit {proc.returncode}", code="apply.cmd")
    return (proc.stdout or "ok")[-2000:]


def _in_container() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def _log(path: Path, payload: dict) -> None:
    payload = {**payload, "ts": time.time()}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _step_dict(res: StepResult) -> dict:
    return {"id": res.id, "title": res.title, "ok": res.ok, "skipped": res.skipped, "output": res.output[-500:]}
