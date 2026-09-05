"""Typed failures used across detection, planning, and apply."""

from __future__ import annotations


class TesseraError(Exception):
    """Base error. Always carries a user-facing message and a stable code."""

    def __init__(self, message: str, *, code: str = "generic", hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint

    def render(self) -> str:
        text = f"[{self.code}] {self.args[0]}"
        if self.hint:
            text += f"\n  → {self.hint}"
        return text


class ProbeError(TesseraError):
    """A hardware or distro probe failed but the rest of the scan can continue."""


class UnsupportedPlatformError(TesseraError):
    """Not a Linux host we can safely configure."""


class PackageManagerError(TesseraError):
    """Package manager missing, locked, or refused an operation."""


class PermissionPlanError(TesseraError):
    """The plan needs privileges the current user does not have."""


class ApplyError(TesseraError):
    """An apply step failed; the journal should already contain the partial state."""


class CatalogError(TesseraError):
    """A role or package mapping is incomplete for this distro family."""


class UserAbort(TesseraError):
    """The operator cancelled a destructive or privileged step."""
