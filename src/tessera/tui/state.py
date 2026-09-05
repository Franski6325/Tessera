"""Mutable session shared by every TUI pane."""

from __future__ import annotations

from dataclasses import dataclass, field

from tessera.catalog.packages import for_roles
from tessera.catalog.security import defaults_for
from tessera.engine.recommend import recommend
from tessera.models import (
    HardwareSnapshot,
    ManagerKind,
    PowerProfile,
    Recommendation,
    RoleId,
    SecurityLevel,
    UserChoices,
)


STEPS = (
    "welcome",
    "hardware",
    "power",
    "roles",
    "security",
    "packages",
    "managers",
    "review",
    "apply",
)


@dataclass
class Session:
    lang: str = "it"
    snapshot: HardwareSnapshot | None = None
    reco: Recommendation | None = None
    choices: UserChoices = field(default_factory=UserChoices)
    scan_error: str | None = None
    apply_log: list[str] = field(default_factory=list)
    last_plan_path: str | None = None

    def adopt_recommendation(self) -> None:
        if not self.reco:
            return
        self.choices.power = self.reco.power
        self.choices.security = self.reco.security
        self.choices.toggles = defaults_for(self.reco.security)
        if not self.choices.roles:
            self.choices.roles = list(self.reco.roles_hint)

    def set_security(self, level: SecurityLevel) -> None:
        self.choices.security = level
        current = {t.id: t.enabled for t in self.choices.toggles}
        fresh = defaults_for(level)
        if level == SecurityLevel.CUSTOM:
            # keep existing flips
            ids = {t.id for t in fresh}
            for t in fresh:
                t.enabled = current.get(t.id, t.enabled)
            self.choices.toggles = fresh
            return
        self.choices.toggles = fresh

    def toggle_role(self, role: RoleId) -> None:
        if role in self.choices.roles:
            self.choices.roles.remove(role)
        else:
            self.choices.roles.append(role)
        # drop packages that no longer belong
        valid = {p.id for p in for_roles(self.choices.roles)}
        self.choices.selected_packages = [p for p in self.choices.selected_packages if p in valid]

    def seed_packages(self) -> None:
        pkgs = for_roles(self.choices.roles)
        low_ram = bool(self.snapshot and self.snapshot.memory.total_gib < 8)
        selected = []
        for p in pkgs:
            if not p.recommended:
                continue
            if p.heavy and low_ram:
                continue
            selected.append(p.id)
        self.choices.selected_packages = selected

    def ensure_managers(self) -> None:
        if not self.snapshot:
            return
        native = next((m for m in self.snapshot.managers if m.native and m.present), None)
        helpers = [m for m in self.snapshot.managers if m.helper and m.present]
        if self.choices.primary_manager is None and native:
            # prefer helper for AUR-capable if already installed
            aur = next((h for h in helpers if h.kind in {ManagerKind.YAY, ManagerKind.PARU}), None)
            self.choices.primary_manager = aur.kind if aur else native.kind
        if ManagerKind.FLATPAK in [m.kind for m in self.snapshot.managers if m.present]:
            if ManagerKind.FLATPAK not in self.choices.extra_managers:
                pass  # do not auto-enable extras
