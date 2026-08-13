from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from planner_ai import config as config_mod
from planner_ai.app import PlannerApp
from planner_ai.config import save_config
from planner_ai.pipeline.types import ProposalState
from planner_ai.providers.models import ModelSelection
from planner_ai.providers.resolve import ResolvedProviders
from planner_ai.ui.result_browser import PRIMARY_TAB_ID, ResultBrowser, ResultTabLabel
from textual.widgets import ContentSwitcher, Input, Static


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config_mod, "get_config_dir", lambda: tmp_path)
    return tmp_path


def _mock_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_choices(_creds, _opts=None):
        from planner_ai.providers.models import MOCK_MODELS

        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)


def _noop_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_ms: int, _abort=None) -> None:
        return None

    monkeypatch.setattr(
        "planner_ai.providers.mock.abortable_sleep",
        instant,
    )


def _workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setattr(
        "planner_ai.workspace.get_workspace_cwd",
        lambda: ws,
    )
    monkeypatch.setattr(
        "planner_ai.write_plan.get_workspace_cwd",
        lambda: ws,
    )
    monkeypatch.setattr(
        "planner_ai.write_run_archive.get_workspace_cwd",
        lambda: ws,
    )
    monkeypatch.setattr(
        "planner_ai.read_run_archive.get_workspace_cwd",
        lambda: ws,
    )
    return ws


MOCK_SELECTION: ModelSelection = {
    "proposers": [
        {"provider": "mock", "modelId": "alpha"},
        {"provider": "mock", "modelId": "beta"},
    ],
    "consensus": {"provider": "mock", "modelId": "gamma"},
}


def _save_mock_config() -> None:
    save_config(
        {
            "cursorApiKey": "dummy",
            "includeMocks": True,
            "modelSelection": MOCK_SELECTION,
        }
    )


async def _wait_done(app: PlannerApp, pilot, *, limit: int = 50) -> None:
    for _ in range(limit):
        if app.phase == "done":
            break
        await pilot.pause()


def test_plan_result_browser_tabs(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press(*list("ship it"))
            await pilot.press("enter")
            await _wait_done(app, pilot)
            assert app.phase == "done"

            rb = app.query_one("#result-browser", ResultBrowser)
            assert "Plan ready" in str(rb.query_one("#rb-heading").render())
            assert rb._active_tab == PRIMARY_TAB_ID

            labels = [t.tab_label for t in rb.query(ResultTabLabel)]
            assert "Plan" in labels
            assert any("Alpha" in label or "alpha" in label.lower() for label in labels)

            rb.focus()
            await pilot.press("right")
            await pilot.pause()
            assert rb._active_tab != PRIMARY_TAB_ID
            body = str(rb.query_one("#rb-body-text").render())
            assert "Proposal" in body or len(body) > 0

            await pilot.press("left")
            await pilot.pause()
            assert rb._active_tab == PRIMARY_TAB_ID

    asyncio.run(run())


def test_ask_result_browser_answer_tab(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#pill-ask")
            await pilot.pause()
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press(*list("what is this"))
            await pilot.press("enter")
            await _wait_done(app, pilot)

            rb = app.query_one("#result-browser", ResultBrowser)
            assert "Answer ready" in str(rb.query_one("#rb-heading").render())
            labels = [t.tab_label for t in rb.query(ResultTabLabel)]
            assert "Answer" in labels
            assert "Plan" not in labels

    asyncio.run(run())


def test_partial_error_consensus_line(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()

    class Ok:
        id = "mock:alpha"
        label = "Mock Alpha"

        async def propose(self, goal, options=None) -> str:
            return "# ok\n"

    class Boom:
        id = "mock:beta"
        label = "Mock Beta"

        async def propose(self, goal, options=None) -> str:
            raise RuntimeError("beta failed")

    class Consensus:
        async def reconcile(self, goal, proposals, options=None) -> str:
            return "# consensus\n"

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.providers = ResolvedProviders(
                proposers=[Ok(), Boom()],
                consensus=Consensus(),
                sources={
                    "proposers": ["mock:alpha", "mock:beta"],
                    "consensus": "mock:gamma",
                },
            )
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press(*list("partial"))
            await pilot.press("enter")
            await _wait_done(app, pilot)
            assert app.phase == "done"

            rb = app.query_one("#result-browser", ResultBrowser)
            errors = rb.query_one("#rb-errors", Static)
            assert "-hidden" not in errors.classes
            assert "consensus used 1 of 2 proposers" in str(errors.render())

            rb.focus()
            # Move to beta error tab (second proposer — may be index 2)
            await pilot.press("right")
            await pilot.pause()
            await pilot.press("right")
            await pilot.pause()
            body = str(rb.query_one("#rb-body-text").render())
            path = str(rb.query_one("#rb-path").render())
            # One of the tabs should show the error
            if "beta failed" not in body:
                await pilot.press("right")
                await pilot.pause()
                body = str(rb.query_one("#rb-body-text").render())
                path = str(rb.query_one("#rb-path").render())
            assert "beta failed" in body or "Error" in path

    asyncio.run(run())


def test_n_plan_another(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press(*list("go"))
            await pilot.press("enter")
            await _wait_done(app, pilot)

            rb = app.query_one("#result-browser", ResultBrowser)
            rb.focus()
            await pilot.press("n")
            await pilot.pause()
            assert app.phase == "idle"
            switcher = app.query_one("#plan-switcher", ContentSwitcher)
            assert switcher.current == "idle"

    asyncio.run(run())


def test_live_exit_quits_app(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press(*list("go"))
            await pilot.press("enter")
            await _wait_done(app, pilot)

            rb = app.query_one("#result-browser", ResultBrowser)
            rb.focus()
            await pilot.press("q")
            await pilot.pause()
            assert not app.is_running

    asyncio.run(run())


def test_proposal_state_for_typing() -> None:
    p = ProposalState(id="a", label="A", status="done", body="# hi")
    assert p.body == "# hi"
