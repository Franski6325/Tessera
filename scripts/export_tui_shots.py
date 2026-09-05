"""Export SVG screenshots of the TUI for walkthrough artifacts."""

from __future__ import annotations

import asyncio
from pathlib import Path

from tessera.tui.app import TesseraApp


async def _shots(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    app = TesseraApp(lang="it")
    async with app.run_test(size=(128, 40)) as pilot:
        await pilot.pause()
        (dest / "tui_welcome.svg").write_text(app.export_screenshot(title="tessera welcome"), encoding="utf-8")
        await pilot.press("n")
        await pilot.pause()
        (dest / "tui_hardware.svg").write_text(app.export_screenshot(title="tessera hardware"), encoding="utf-8")
        await pilot.press("n")
        await pilot.pause()
        (dest / "tui_power.svg").write_text(app.export_screenshot(title="tessera power"), encoding="utf-8")
        await pilot.press("n")
        await pilot.pause()
        (dest / "tui_roles.svg").write_text(app.export_screenshot(title="tessera roles"), encoding="utf-8")
        await pilot.press("n")
        await pilot.pause()
        (dest / "tui_security.svg").write_text(app.export_screenshot(title="tessera security"), encoding="utf-8")
        app.goto("packages")
        await pilot.pause()
        (dest / "tui_packages.svg").write_text(app.export_screenshot(title="tessera packages"), encoding="utf-8")
        app.goto("managers")
        await pilot.pause()
        (dest / "tui_managers.svg").write_text(app.export_screenshot(title="tessera managers"), encoding="utf-8")
        app.goto("review")
        await pilot.pause()
        (dest / "tui_review.svg").write_text(app.export_screenshot(title="tessera review"), encoding="utf-8")


def main() -> None:
    dest = Path("/opt/cursor/artifacts")
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError:
        dest = Path("/workspace/artifacts")
        dest.mkdir(parents=True, exist_ok=True)
    asyncio.run(_shots(dest))
    print(f"shots → {dest}")


if __name__ == "__main__":
    main()
