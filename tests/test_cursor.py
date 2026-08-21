from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from planner_ai.providers.call_abort import ProviderAbortError
from planner_ai.providers.cursor import (
    READ_TOOLS,
    create_cursor_consensus,
    create_cursor_proposer,
)
from planner_ai.providers.types import ProviderCallOptions


@dataclass
class FakeRunResult:
    status: str
    result: str | None = None
    error: Any = None


@dataclass
class FakeRun:
    result: FakeRunResult
    cancelled: list[bool] = field(default_factory=list)
    support_cancel: bool = True

    def supports(self, op: str) -> bool:
        return op == "cancel" and self.support_cancel

    async def cancel(self) -> None:
        self.cancelled.append(True)

    async def wait(self) -> FakeRunResult:
        await asyncio.sleep(0.01)
        if self.cancelled:
            return FakeRunResult(status="cancelled")
        return self.result


@dataclass
class FakeAgent:
    run: FakeRun
    create_kwargs: dict[str, Any] = field(default_factory=dict)

    async def send(self, prompt: str) -> FakeRun:
        self.create_kwargs["last_prompt"] = prompt
        return self.run

    async def __aenter__(self) -> FakeAgent:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


@dataclass
class FakeAgents:
    agent: FakeAgent

    async def create(self, options: Any = None, **kwargs: Any) -> FakeAgent:
        self.agent.create_kwargs.update(kwargs)
        if options is not None:
            self.agent.create_kwargs["options"] = options
        return self.agent


@dataclass
class FakeClient:
    agents: FakeAgents

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeCursorAgentError(Exception):
    pass


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: FakeRunResult | None = None,
    raise_on_create: BaseException | None = None,
    support_cancel: bool = True,
    wait_delay: float = 0.01,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    run = FakeRun(
        result=result
        or FakeRunResult(status="finished", result="  # Cursor plan  "),
        support_cancel=support_cancel,
    )

    async def wait_override() -> FakeRunResult:
        await asyncio.sleep(wait_delay)
        if run.cancelled:
            return FakeRunResult(status="cancelled")
        return run.result

    run.wait = wait_override  # type: ignore[method-assign]
    agent = FakeAgent(run=run)
    agents = FakeAgents(agent=agent)
    client = FakeClient(agents=agents)

    class FakeAsyncClient:
        @staticmethod
        async def launch_bridge(*, workspace: str) -> FakeClient:
            captured["workspace"] = workspace
            return client

    class FakeLocalAgentStoreConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeLocalAgentOptions:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            captured["local"] = kwargs

    class FakeAgentOptions:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            captured["options"] = kwargs
            for key, value in kwargs.items():
                setattr(self, key, value)

    async def create_override(
        options: Any = None, **kwargs: Any
    ) -> FakeAgent:
        captured["create"] = kwargs
        captured["create_options"] = options
        if raise_on_create is not None:
            raise raise_on_create
        agents.agent.create_kwargs.update(kwargs)
        if options is not None:
            agents.agent.create_kwargs["options"] = options
        return agents.agent

    agents.create = create_override  # type: ignore[method-assign]

    fake_sdk = MagicMock()
    fake_sdk.AsyncClient = FakeAsyncClient
    fake_sdk.AgentOptions = FakeAgentOptions
    fake_sdk.LocalAgentOptions = FakeLocalAgentOptions
    fake_sdk.LocalAgentStoreConfig = FakeLocalAgentStoreConfig
    fake_sdk.CursorAgentError = FakeCursorAgentError

    import sys

    monkeypatch.setitem(sys.modules, "cursor_sdk", fake_sdk)
    captured["run"] = run
    captured["agent"] = agent
    return captured


def test_cursor_propose_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured = _install_fakes(monkeypatch)

    proposer = create_cursor_proposer("ckey", "composer-2.5", "Composer")
    assert proposer.id == "cursor:composer-2.5"

    body = asyncio.run(proposer.propose("Ship it"))
    assert body == "# Cursor plan"

    opts = captured["options"]
    assert opts["api_key"] == "ckey"
    assert opts["model"] == "composer-2.5"
    assert opts["tools"] == READ_TOOLS
    assert captured["create"] == {}
    assert captured["local"]["cwd"] == str(tmp_path.resolve())
    assert captured["local"]["setting_sources"] == ["project"]
    store = captured["local"]["store"]
    assert store.type == "jsonl"
    assert Path(store.root_dir).name.startswith("planner-ai-cursor-")
    assert str(store.root_dir).startswith(tempfile.gettempdir())
    assert not Path(store.root_dir).exists()
    prompt = captured["agent"].create_kwargs["last_prompt"]
    assert "You are a planning assistant." in prompt
    assert "Goal:\nShip it" in prompt


def test_cursor_status_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    @dataclass
    class Err:
        message: str = "ran and failed"

    _install_fakes(
        monkeypatch,
        result=FakeRunResult(status="error", error=Err()),
    )
    proposer = create_cursor_proposer("ckey", "auto", "Auto")
    with pytest.raises(RuntimeError, match=r"Cursor agent failed: ran and failed"):
        asyncio.run(proposer.propose("goal"))


def test_cursor_empty_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_fakes(
        monkeypatch,
        result=FakeRunResult(status="finished", result="  "),
    )
    proposer = create_cursor_proposer("ckey", "auto", "Auto")
    with pytest.raises(RuntimeError, match=r"Cursor returned empty text"):
        asyncio.run(proposer.propose("goal"))


def test_cursor_agent_error_not_wrapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_fakes(
        monkeypatch,
        raise_on_create=FakeCursorAgentError("never started"),
    )
    proposer = create_cursor_proposer("ckey", "auto", "Auto")
    with pytest.raises(FakeCursorAgentError, match=r"never started"):
        asyncio.run(proposer.propose("goal"))


def test_cursor_abort_cancels_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured = _install_fakes(monkeypatch, wait_delay=1.0)

    async def run() -> None:
        cancel = asyncio.Event()
        proposer = create_cursor_proposer("ckey", "auto", "Auto")

        async def fire() -> None:
            await asyncio.sleep(0.02)
            cancel.set()

        fire_task = asyncio.create_task(fire())
        with pytest.raises(ProviderAbortError):
            await proposer.propose(
                "goal",
                ProviderCallOptions(cancel_event=cancel),
            )
        await fire_task
        assert captured["run"].cancelled == [True]

    asyncio.run(run())


def test_cursor_consensus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured = _install_fakes(
        monkeypatch,
        result=FakeRunResult(status="finished", result="Merged"),
    )
    consensus = create_cursor_consensus("ckey", "auto")
    body = asyncio.run(
        consensus.reconcile("goal", [{"id": "a", "body": "A"}])
    )
    assert body == "Merged"
    prompt = captured["agent"].create_kwargs["last_prompt"]
    assert "### Proposal: a" in prompt
