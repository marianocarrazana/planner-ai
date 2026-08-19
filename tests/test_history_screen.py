from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from planner_ai import config as config_mod
from planner_ai.app import PlannerApp
from planner_ai.config import save_config
from planner_ai.pipeline.types import ProposalState
from planner_ai.providers.models import ModelSelection
from planner_ai.ui.history_screen import HistoryScreen
from planner_ai.ui.result_browser import ResultBrowser
from planner_ai.write_run_archive import ARCHIVE_DIR, write_run_archive
from textual.widgets import ContentSwitcher, Markdown, OptionList, Static, Tab

FIXED = datetime(2026, 8, 13, 16, 48, 0)
LATER = datetime(2026, 8, 13, 16, 49, 0)


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config_mod, "get_config_dir", lambda: tmp_path)
    return tmp_path


def _mock_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_choices(_creds, _opts=None):
        from planner_ai.providers.models import MOCK_MODELS

        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)


def _workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    for mod in (
        "planner_ai.workspace.get_workspace_cwd",
        "planner_ai.write_run_archive.get_workspace_cwd",
        "planner_ai.read_run_archive.get_workspace_cwd",
    ):
        monkeypatch.setattr(mod, lambda: ws)
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


def _done(proposal_id: str, body: str = "# Ok\n") -> ProposalState:
    return ProposalState(id=proposal_id, label=proposal_id, status="done", body=body)


def test_history_empty(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(tmp_path, monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+5")
            await pilot.pause()
            assert app.active_tab == "history"
            hist = app.query_one("#history", HistoryScreen)
            empty = hist.query_one("#hist-empty", Static)
            assert "-hidden" not in empty.classes
            assert ARCHIVE_DIR in str(empty.render())
            hist.query_one("#hist-rows", OptionList).focus()
            await pilot.press("r")
            await pilot.pause()
            assert "-hidden" not in empty.classes

    asyncio.run(run())


def test_history_lists_plan_and_ask_newest_first(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _workspace(tmp_path, monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()
    write_run_archive(
        kind="plan",
        plan="# plan body",
        proposals=[_done("a")],
        cwd=ws,
        date=FIXED,
    )
    write_run_archive(
        kind="ask",
        plan="# answer body",
        proposals=[_done("b")],
        cwd=ws,
        date=LATER,
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+5")
            for _ in range(20):
                hist = app.query_one("#history", HistoryScreen)
                if len(hist._runs) == 2:
                    break
                await pilot.pause()
            hist = app.query_one("#history", HistoryScreen)
            assert [r.kind for r in hist._runs] == ["ask", "plan"]
            rows = hist.query_one("#hist-rows", OptionList)
            assert rows.option_count == 2
            text0 = str(rows.get_option_at_index(0).prompt)
            text1 = str(rows.get_option_at_index(1).prompt)
            assert "ask" in text0
            assert "plan" in text1
            assert "2026-08-13" in text0

    asyncio.run(run())


def test_history_open_ask_shows_answer_tab(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _workspace(tmp_path, monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()
    write_run_archive(
        kind="plan",
        plan="# plan body",
        proposals=[_done("a")],
        cwd=ws,
        date=FIXED,
    )
    write_run_archive(
        kind="ask",
        plan="# consensus answer\n",
        proposals=[_done("cursor-composer-2.5", "# Answer from Cursor\n")],
        cwd=ws,
        date=LATER,
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+5")
            for _ in range(20):
                hist = app.query_one("#history", HistoryScreen)
                if len(hist._runs) == 2:
                    break
                await pilot.pause()
            hist = app.query_one("#history", HistoryScreen)
            hist.query_one("#hist-rows", OptionList).focus()
            # Newest (ask) is cursor 0
            await pilot.press("enter")
            for _ in range(20):
                switcher = hist.query_one("#hist-switcher", ContentSwitcher)
                if switcher.current == "hist-detail":
                    break
                await pilot.pause()
            assert hist._view == "detail"
            rb = hist.query_one("#hist-result-browser", ResultBrowser)
            heading = str(rb.query_one("#rb-heading").render())
            assert "Archived" in heading
            assert "ask" in heading
            labels = [t.label_text for t in rb.query(Tab)]
            assert "Answer" in labels
            body = rb.query_one("#rb-body-markdown", Markdown).source
            assert "consensus answer" in body

            rb.focus()
            await pilot.press("escape")
            await pilot.pause()
            for _ in range(20):
                if hist._view == "list":
                    break
                await pilot.pause()
            assert hist._view == "list"
            assert len(hist._runs) == 2

    asyncio.run(run())


def test_history_read_error_and_back(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _workspace(tmp_path, monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()
    run_dir = write_run_archive(
        kind="plan",
        plan="# plan",
        proposals=[_done("a")],
        cwd=ws,
        date=FIXED,
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+5")
            for _ in range(20):
                hist = app.query_one("#history", HistoryScreen)
                if len(hist._runs) == 1:
                    break
                await pilot.pause()
            hist = app.query_one("#history", HistoryScreen)

            # Remove archive so open fails
            import shutil

            shutil.rmtree(run_dir)

            hist.query_one("#hist-rows", OptionList).focus()
            await pilot.press("enter")
            for _ in range(20):
                if hist._view == "error":
                    break
                await pilot.pause()
            assert hist._view == "error"
            err = str(hist.query_one("#hist-error-msg").render())
            assert len(err) > 0

            hist.query_one("#hist-rows", OptionList).focus()
            await pilot.press("escape")
            await pilot.pause()
            assert hist._view == "list"

    asyncio.run(run())


def test_history_reload_picks_up_new_archive(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _workspace(tmp_path, monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()
    write_run_archive(
        kind="plan",
        plan="# plan",
        proposals=[_done("a")],
        cwd=ws,
        date=FIXED,
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+5")
            for _ in range(20):
                hist = app.query_one("#history", HistoryScreen)
                if len(hist._runs) == 1:
                    break
                await pilot.pause()
            hist = app.query_one("#history", HistoryScreen)
            assert len(hist._runs) == 1

            write_run_archive(
                kind="ask",
                plan="# answer",
                proposals=[_done("b")],
                cwd=ws,
                date=LATER,
            )
            hist.query_one("#hist-rows", OptionList).focus()
            await pilot.press("r")
            for _ in range(20):
                if len(hist._runs) == 2:
                    break
                await pilot.pause()
            assert len(hist._runs) == 2
            assert hist._runs[0].kind == "ask"

    asyncio.run(run())


def test_history_typescript_shaped_fixture(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _workspace(tmp_path, monkeypatch)
    _mock_choices(monkeypatch)
    _save_mock_config()

    root = ws / ARCHIVE_DIR
    plan_dir = root / "plan-2026-08-13T16-48-00"
    ask_dir = root / "ask-2026-08-13T16-49-00"
    plan_dir.mkdir(parents=True)
    ask_dir.mkdir(parents=True)
    (plan_dir / "anthropic-claude-sonnet-4-5-output.md").write_text(
        "# Proposal from Claude\n", encoding="utf-8"
    )
    (plan_dir / "plan.md").write_text("# Consensus plan\n", encoding="utf-8")
    (ask_dir / "cursor-composer-2.5-output.md").write_text(
        "# Answer from Cursor\n", encoding="utf-8"
    )
    (ask_dir / "answer.md").write_text("# Consensus answer\n", encoding="utf-8")

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+5")
            for _ in range(20):
                hist = app.query_one("#history", HistoryScreen)
                if len(hist._runs) == 2:
                    break
                await pilot.pause()
            hist = app.query_one("#history", HistoryScreen)
            assert [r.dir_name for r in hist._runs] == [
                "ask-2026-08-13T16-49-00",
                "plan-2026-08-13T16-48-00",
            ]
            hist.query_one("#hist-rows", OptionList).focus()
            await pilot.press("enter")
            for _ in range(20):
                if hist._view == "detail":
                    break
                await pilot.pause()
            rb = hist.query_one("#hist-result-browser", ResultBrowser)
            assert "Answer" in [t.label_text for t in rb.query(Tab)]
            assert "Consensus answer" in rb.query_one("#rb-body-markdown", Markdown).source
            rb.focus()
            await pilot.press("right")
            await pilot.pause()
            body = rb.query_one("#rb-body-markdown", Markdown).source
            assert "Answer from Cursor" in body

    asyncio.run(run())
