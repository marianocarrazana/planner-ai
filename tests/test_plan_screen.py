from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from planner_ai import config as config_mod
from planner_ai.app import PlannerApp
from planner_ai.config import load_config, save_config
from planner_ai.pipeline.types import ProposalState
from planner_ai.providers.models import MOCK_MODELS, ModelSelection
from planner_ai.providers.resolve import ResolvedProviders
from planner_ai.providers.types import ProviderCallOptions
from planner_ai.ui.plan_helpers import (
    consensus_body,
    consensus_title,
    error_hint,
    format_elapsed_seconds,
    plan_gate,
    status_label,
)
from planner_ai.ui.plan_screen import PlanScreen
from planner_ai.ui.result_browser import ResultBrowser
from textual.widgets import ContentSwitcher, Input, Static


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config_mod, "get_config_dir", lambda: tmp_path)
    return tmp_path


def test_plan_gate_ready_need_auth_need_models() -> None:
    assert plan_gate(None, {}) == "need-auth"
    assert plan_gate(None, {"cursorApiKey": "k"}) == "need-models"

    class _C:
        async def reconcile(self, goal, proposals, options=None) -> str:
            return ""

    providers = ResolvedProviders(
        proposers=[],
        consensus=_C(),
        sources={
            "proposers": ["mock:alpha"],
            "consensus": "mock:gamma",
        },
    )
    assert plan_gate(providers, {}) == "ready"


def test_status_label_and_elapsed() -> None:
    assert format_elapsed_seconds(3) == "3s"
    assert status_label("pending") == "pending"
    assert status_label("streaming") == "working…"
    assert status_label("streaming", 2) == "working… 2s"
    assert status_label("done") == "done"
    assert status_label("error") == "error"


def test_consensus_copy() -> None:
    assert consensus_title(writing=False, mode="plan") == "Consensus"
    assert consensus_title(writing=True, mode="plan") == "Writing plan"
    assert consensus_title(writing=True, mode="ask") == "Saving answer"
    assert (
        consensus_body(writing=False, mode="plan")
        == "Reconciling proposals into one plan…"
    )
    assert (
        consensus_body(writing=False, mode="plan", elapsed_seconds=4)
        == "Reconciling proposals into one plan… 4s"
    )
    assert (
        consensus_body(writing=False, mode="ask")
        == "Reconciling answers into one response…"
    )
    assert consensus_body(writing=True, mode="plan") == "Saving plan.md…"
    assert consensus_body(writing=True, mode="ask") == "Archiving answer…"


def test_error_hint() -> None:
    assert "Press r to remove Cursor API key" in error_hint(
        mode="plan",
        failing_labels=["Cursor API key"],
    )
    assert "ask another" in error_hint(mode="ask", failing_labels=[])
    assert "Press r" not in error_hint(mode="plan", failing_labels=[])


def _mock_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_choices(_creds, _opts=None):
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
    return ws


MOCK_SELECTION: ModelSelection = {
    "proposers": [
        {"provider": "mock", "modelId": "alpha"},
        {"provider": "mock", "modelId": "beta"},
    ],
    "consensus": {"provider": "mock", "modelId": "gamma"},
}


def test_need_auth_gate(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_choices(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+1")
            await pilot.pause()
            assert app.active_tab == "plan"
            switcher = app.query_one("#plan-switcher", ContentSwitcher)
            assert switcher.current == "need-auth"
            await pilot.click("#link-go-auth")
            await pilot.pause()
            assert app.active_tab == "auth"

    asyncio.run(run())


def test_need_models_gate(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_choices(monkeypatch)
    monkeypatch.setattr(
        "planner_ai.app.load_config",
        lambda: {
            "cursorApiKey": "k",
            "modelSelection": {
                "proposers": [{"provider": "anthropic", "modelId": "missing"}],
                "consensus": {"provider": "anthropic", "modelId": "missing"},
            },
        },
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Invalid selection → proposers startup; go to Plan
            await pilot.press("ctrl+1")
            await pilot.pause()
            switcher = app.query_one("#plan-switcher", ContentSwitcher)
            assert switcher.current == "need-models"
            await pilot.click("#link-go-models")
            await pilot.pause()
            assert app.active_tab == "proposers"

    asyncio.run(run())


def test_ready_after_continue(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_choices(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+2")
            await pilot.pause()
            ms = app.query_one("#proposers")
            ms.focus()
            await pilot.press("c")
            for _ in range(30):
                if app.active_tab == "plan" and app.providers is not None:
                    break
                await pilot.pause()
            switcher = app.query_one("#plan-switcher", ContentSwitcher)
            assert switcher.current == "idle"
            prompt = str(app.query_one("#goal-prompt", Static).render())
            assert "goal" in prompt.lower()

    asyncio.run(run())


def test_plan_ask_toggle(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_choices(monkeypatch)
    save_config(
        {
            "cursorApiKey": "dummy",
            "includeMocks": True,
            "modelSelection": MOCK_SELECTION,
        }
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.active_tab == "plan"
            assert "goal" in str(app.query_one("#goal-prompt", Static).render()).lower()
            field = app.query_one("#goal-field", Input)
            assert field.outer_size.height >= 3
            assert (
                app.query_one("#mode-row").region.y
                > app.query_one("#goal-row").region.y
            )
            models = app.query_one("#goal-models")
            proposers = app.query_one("#goal-proposers", Static)
            consensus = app.query_one("#goal-consensus", Static)
            assert models.region.y > app.query_one("#mode-row").region.y
            assert consensus.region.y > proposers.region.y
            assert str(proposers.render()).startswith("proposers:")
            assert str(consensus.render()).startswith("consensus:")
            await pilot.click("#pill-ask")
            await pilot.pause()
            assert app.run_mode == "ask"
            assert "ask" in str(app.query_one("#goal-prompt", Static).render()).lower()
            # Header goal hidden until submit
            assert "Goal:" not in app.sub_title
            assert "Question:" not in app.sub_title

    asyncio.run(run())


def test_mock_plan_run(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    save_config(
        {
            "cursorApiKey": "dummy",
            "includeMocks": True,
            "modelSelection": MOCK_SELECTION,
        }
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.active_tab == "plan"
            assert app.providers is not None
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press(*list("ship it"))
            await pilot.press("enter")
            for _ in range(50):
                if app.phase == "done":
                    break
                await pilot.pause()
            assert app.phase == "done"
            assert "Goal: ship it" in app.sub_title
            rb = app.query_one(ResultBrowser)
            assert "Plan ready" in str(rb.query_one("#rb-heading").render())
            assert (ws / "plan.md").exists()
            archives = list((ws / ".planner-ai").glob("plan-*"))
            assert len(archives) == 1

    asyncio.run(run())


def test_mock_ask_run_no_plan_md(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    save_config(
        {
            "cursorApiKey": "dummy",
            "includeMocks": True,
            "modelSelection": MOCK_SELECTION,
        }
    )

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
            for _ in range(50):
                if app.phase == "done":
                    break
                await pilot.pause()
            assert app.phase == "done"
            assert app.run_mode == "ask"
            assert "Question: what is this" in app.sub_title
            rb = app.query_one(ResultBrowser)
            assert "Answer ready" in str(rb.query_one("#rb-heading").render())
            assert not (ws / "plan.md").exists()
            archives = list((ws / ".planner-ai").glob("ask-*"))
            assert len(archives) == 1
            assert (archives[0] / "answer.md").exists()

    asyncio.run(run())


class _FailAuthProposer:
    id = "cursor:auto"
    label = "Cursor Auto"

    async def propose(
        self,
        goal: str,
        options: ProviderCallOptions | None = None,
    ) -> str:
        raise RuntimeError("unauthorized: invalid api key")


class _FailAllConsensus:
    async def reconcile(self, goal, proposals, options=None) -> str:
        return "# never\n"


def test_error_r_clears_auth_and_opens_auth(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    save_config(
        {
            "cursorApiKey": "bad-key",
            "includeMocks": True,
            "modelSelection": MOCK_SELECTION,
        }
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.providers is not None
            # Force all proposers to auth-fail so pipeline errors with auth keys
            app.providers = ResolvedProviders(
                proposers=[_FailAuthProposer()],
                consensus=_FailAllConsensus(),
                sources={
                    "proposers": ["cursor:auto"],
                    "consensus": "cursor:auto",
                },
            )
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press(*list("go"))
            await pilot.press("enter")
            for _ in range(50):
                if app.phase == "error":
                    break
                await pilot.pause()
            assert app.phase == "error"
            assert "cursorApiKey" in app.failing_keys
            app.query_one(PlanScreen).focus()
            await pilot.press("r")
            for _ in range(40):
                if app.active_tab == "auth":
                    break
                await pilot.pause()
            assert app.active_tab == "auth"
            assert "cursorApiKey" not in load_config()

    asyncio.run(run())


def test_error_esc_back_enter_retry(
    config_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = _workspace(tmp_path, monkeypatch)
    _noop_sleep(monkeypatch)
    _mock_choices(monkeypatch)
    save_config(
        {
            "cursorApiKey": "dummy",
            "includeMocks": True,
            "modelSelection": MOCK_SELECTION,
        }
    )

    calls = {"n": 0}

    class Boom:
        id = "mock:alpha"
        label = "Mock Alpha"

        async def propose(self, goal, options=None) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return "# recovered\n"

    class Consensus:
        async def reconcile(self, goal, proposals, options=None) -> str:
            return "# consensus\n"

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.providers = ResolvedProviders(
                proposers=[Boom()],
                consensus=Consensus(),
                sources={
                    "proposers": ["mock:alpha"],
                    "consensus": "mock:gamma",
                },
            )
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press(*list("retry me"))
            await pilot.press("enter")
            for _ in range(50):
                if app.phase == "error":
                    break
                await pilot.pause()
            assert app.phase == "error"
            app.query_one(PlanScreen).focus()
            await pilot.press("escape")
            await pilot.pause()
            assert app.phase == "idle"
            switcher = app.query_one("#plan-switcher", ContentSwitcher)
            assert switcher.current == "idle"

            await app.start("retry me", "plan")
            for _ in range(50):
                if app.phase in ("done", "error"):
                    break
                await pilot.pause()
            assert app.phase == "done"
            assert (ws / "plan.md").exists()

    asyncio.run(run())


def test_ctrl_tabs_while_goal_focused(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_choices(monkeypatch)
    save_config(
        {
            "cursorApiKey": "dummy",
            "includeMocks": True,
            "modelSelection": MOCK_SELECTION,
        }
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            field = app.query_one("#goal-field", Input)
            field.focus()
            await pilot.press("ctrl+2")
            assert app.active_tab == "proposers"
            await pilot.press("ctrl+1")
            assert app.active_tab == "plan"
            await pilot.press("ctrl+4")
            assert app.active_tab == "auth"
            await pilot.press("ctrl+1")
            assert app.active_tab == "plan"

    asyncio.run(run())


def test_proposal_state_elapsed_label_helper() -> None:
    p = ProposalState(
        id="mock:alpha",
        label="Alpha",
        status="streaming",
        started_at=0,
    )
    assert status_label(p.status, 0) == "working… 0s"
