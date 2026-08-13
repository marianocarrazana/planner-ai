from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from planner_ai.providers.call_abort import ProviderAbortError
from planner_ai.providers.codex import (
    create_codex_consensus,
    create_codex_proposer,
)
from planner_ai.providers.types import ProviderCallOptions


@dataclass
class FakeTurnResult:
    final_response: str | None


@dataclass
class FakeTurnHandle:
    result: FakeTurnResult
    interrupted: list[bool] = field(default_factory=list)
    delay: float = 0.01

    async def interrupt(self) -> None:
        self.interrupted.append(True)

    async def run(self) -> FakeTurnResult:
        await asyncio.sleep(self.delay)
        if self.interrupted:
            raise asyncio.CancelledError()
        return self.result


@dataclass
class FakeThread:
    handle: FakeTurnHandle
    start_kwargs: dict[str, Any] = field(default_factory=dict)

    async def turn(self, prompt: str) -> FakeTurnHandle:
        self.start_kwargs["prompt"] = prompt
        return self.handle


@dataclass
class FakeCodex:
    thread: FakeThread
    config: Any = None
    logged_in: list[str] = field(default_factory=list)
    start_kwargs: dict[str, Any] = field(default_factory=dict)

    async def __aenter__(self) -> FakeCodex:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def login_api_key(self, api_key: str) -> None:
        self.logged_in.append(api_key)

    async def thread_start(self, **kwargs: Any) -> FakeThread:
        self.start_kwargs.update(kwargs)
        return self.thread


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    final_response: str | None = "  # Codex plan  ",
    delay: float = 0.01,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    handle = FakeTurnHandle(
        result=FakeTurnResult(final_response=final_response),
        delay=delay,
    )
    thread = FakeThread(handle=handle)

    class FakeApprovalMode:
        deny_all = "deny_all"
        auto_review = "auto_review"

    class FakeSandbox:
        read_only = "read-only"
        workspace_write = "workspace-write"
        full_access = "full-access"

    class FakeCodexConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            captured["config"] = kwargs

    instances: list[FakeCodex] = []

    def fake_async_codex(config: Any = None) -> FakeCodex:
        inst = FakeCodex(thread=thread, config=config)
        instances.append(inst)
        captured["codex"] = inst
        return inst

    fake_openai = MagicMock()
    fake_openai.ApprovalMode = FakeApprovalMode
    fake_openai.AsyncCodex = fake_async_codex
    fake_openai.Sandbox = FakeSandbox

    fake_client_mod = MagicMock()
    fake_client_mod.CodexConfig = FakeCodexConfig

    import sys

    monkeypatch.setitem(sys.modules, "openai_codex", fake_openai)
    monkeypatch.setitem(sys.modules, "openai_codex.client", fake_client_mod)
    captured["handle"] = handle
    captured["thread"] = thread
    captured["instances"] = instances
    return captured


def test_codex_propose_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured = _install_fakes(monkeypatch)

    proposer = create_codex_proposer("xkey", "gpt-5.2", "GPT-5.2")
    assert proposer.id == "codex:gpt-5.2"

    body = asyncio.run(proposer.propose("Ship it"))
    assert body == "# Codex plan"

    assert captured["config"]["env"] == {"CODEX_API_KEY": "xkey"}
    assert captured["codex"].logged_in == ["xkey"]
    start = captured["codex"].start_kwargs
    assert start["model"] == "gpt-5.2"
    assert start["cwd"] == str(tmp_path.resolve())
    assert start["sandbox"] == "read-only"
    assert start["approval_mode"] == "deny_all"
    prompt = captured["thread"].start_kwargs["prompt"]
    assert "You are a planning assistant." in prompt
    assert "Goal:\nShip it" in prompt


def test_codex_empty_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_fakes(monkeypatch, final_response="   ")
    proposer = create_codex_proposer("xkey", "gpt-5.2", "GPT-5.2")
    with pytest.raises(RuntimeError, match=r"Codex returned empty text"):
        asyncio.run(proposer.propose("goal"))


def test_codex_abort_interrupts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured = _install_fakes(monkeypatch, delay=1.0)

    async def run() -> None:
        cancel = asyncio.Event()
        proposer = create_codex_proposer("xkey", "gpt-5.2", "GPT-5.2")

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
        assert captured["handle"].interrupted == [True]

    asyncio.run(run())


def test_codex_consensus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured = _install_fakes(monkeypatch, final_response="Merged")
    consensus = create_codex_consensus("xkey", "gpt-5.2")
    body = asyncio.run(
        consensus.reconcile("goal", [{"id": "a", "body": "A"}])
    )
    assert body == "Merged"
    prompt = captured["thread"].start_kwargs["prompt"]
    assert "### Proposal: a" in prompt
