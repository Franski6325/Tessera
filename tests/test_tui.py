import pytest

from tessera.tui.app import TesseraApp


@pytest.mark.asyncio
async def test_tui_welcome_then_hardware():
    app = TesseraApp(lang="it")
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        assert app.step == "welcome"
        await pilot.press("n")
        await pilot.pause()
        assert app.session.snapshot is not None
        assert app.step == "hardware"
        pane = app.query_one("#pane")
        text = pane.renderable if hasattr(pane, "renderable") else str(pane)
        blob = str(text).lower()
        assert "cpu" in blob or "ram" in blob or app.session.snapshot.cpu.model


@pytest.mark.asyncio
async def test_tui_power_select_does_not_duplicate_ids():
    app = TesseraApp(lang="it")
    async with app.run_test(size=(140, 46)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert app.step == "power"
        ol = app.query_one("#power-list")
        ol.highlighted = 2  # battery
        ol.action_select()
        await pilot.pause()
        lists = list(app.query("#power-list"))
        assert len(lists) == 1
        assert app.session.choices.power.value == "battery"
        # second select must also stay unique
        lists[0].highlighted = 1
        lists[0].action_select()
        await pilot.pause()
        assert len(list(app.query("#power-list"))) == 1


@pytest.mark.asyncio
async def test_tui_roles_and_security_navigation():
    app = TesseraApp(lang="it")
    async with app.run_test(size=(140, 46)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert app.step == "power"
        await pilot.press("n")
        await pilot.pause()
        assert app.step == "roles"
        boxes = list(app.query("Checkbox"))
        assert boxes
        await pilot.press("n")
        await pilot.pause()
        assert app.step == "security"
        await pilot.press("p")
        await pilot.pause()
        assert app.step == "roles"
