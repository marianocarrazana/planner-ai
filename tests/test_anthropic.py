from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from planner_ai.providers import anthropic as anthropic_mod
from planner_ai.providers.anthropic import (
    DISALLOWED_TOOLS,
    READ_TOOLS,
    create_anthropic_consensus,
    create_anthropic_proposer,
)
from planner_ai.providers.call_abort import ProviderAbortError
from planner_ai.providers.types import ProviderCallOptions


@dataclass
class FakeResultMessage:
    subtype: str
    result: str | None = None
    errors: list[str] | None = None


def _patch_query(
    monkeypatch: pytest.MonkeyPatch,
    messages: list[Any],
    captured: dict[str, Any],
) -> None:
    async def collect(prompt: str, options: object):
        captured["prompt"] = prompt
        captured["options"] = options
        result_text: str | None = None
        error_detail: str | None = None
        for message in messages:
            if not isinstance(message, FakeResultMessage):
                continue
            if message.subtype == "success":
                raw = message.result
                result_text = raw.strip() if isinstance(raw, str) else None
            else:
                errors = message.errors
                if isinstance(errors, list) and len(errors) > 0:
                    error_detail = "; ".join(str(e) for e in errors)
                else:
                    error_detail = message.subtype
        return result_text, error_detail

    monkeypatch.setattr(anthropic_mod, "_collect_query", collect)


def test_anthropic_propose_plan_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, Any] = {}
    _patch_query(
        monkeypatch,
        [FakeResultMessage(subtype="success", result="  # Plan\n\nDo it  ")],
        captured,
    )

    proposer = create_anthropic_proposer("oauth-token", "claude-sonnet", "Sonnet")
    assert proposer.id == "anthropic:claude-sonnet"
    assert proposer.label == "Sonnet"

    body = asyncio.run(proposer.propose("Ship feature X"))
    assert body == "# Plan\n\nDo it"

    opts = captured["options"]
    assert opts.model == "claude-sonnet"
    assert opts.cwd == str(tmp_path.resolve())
    assert opts.tools == READ_TOOLS
    assert opts.allowed_tools == READ_TOOLS
    assert opts.disallowed_tools == DISALLOWED_TOOLS
    assert opts.permission_mode == "dontAsk"
    assert opts.setting_sources == ["project"]
    assert opts.env["CLAUDE_CODE_OAUTH_TOKEN"] == "oauth-token"
    assert opts.env["ANTHROPIC_API_KEY"] == ""
    assert "You are a planning assistant." in opts.system_prompt
    assert "Goal:\nShip feature X" in captured["prompt"]
    assert "Working directory:" in captured["prompt"]


def test_anthropic_propose_ask_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, Any] = {}
    _patch_query(
        monkeypatch,
        [FakeResultMessage(subtype="success", result="Answer text")],
        captured,
    )

    proposer = create_anthropic_proposer("tok", "m1", "M1")
    body = asyncio.run(
        proposer.propose(
            "What does workspace.py do?",
            ProviderCallOptions(mode="ask"),
        )
    )
    assert body == "Answer text"
    assert "You are a codebase Q&A assistant." in captured["options"].system_prompt
    assert "Question:\nWhat does workspace.py do?" in captured["prompt"]


def test_anthropic_empty_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_query(
        monkeypatch,
        [FakeResultMessage(subtype="success", result="   ")],
        {},
    )
    proposer = create_anthropic_proposer("tok", "m1", "M1")
    with pytest.raises(RuntimeError, match=r"Claude Agent SDK returned empty text"):
        asyncio.run(proposer.propose("goal"))


def test_anthropic_error_subtype(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _patch_query(
        monkeypatch,
        [
            FakeResultMessage(
                subtype="error_during_execution",
                errors=["boom", "again"],
            )
        ],
        {},
    )
    proposer = create_anthropic_proposer("tok", "m1", "M1")
    with pytest.raises(RuntimeError, match=r"Claude Agent SDK failed: boom; again"):
        asyncio.run(proposer.propose("goal"))


def test_anthropic_abort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    async def slow_collect(prompt: str, options: object):
        await asyncio.sleep(1)
        return "late", None

    monkeypatch.setattr(anthropic_mod, "_collect_query", slow_collect)

    async def run() -> None:
        cancel = asyncio.Event()
        proposer = create_anthropic_proposer("tok", "m1", "M1")

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

    asyncio.run(run())


def test_anthropic_consensus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, Any] = {}
    _patch_query(
        monkeypatch,
        [FakeResultMessage(subtype="success", result="Merged")],
        captured,
    )
    consensus = create_anthropic_consensus("tok", "m1")
    body = asyncio.run(
        consensus.reconcile(
            "Ship it",
            [{"id": "a", "body": "Plan A"}],
        )
    )
    assert body == "Merged"
    assert "### Proposal: a" in captured["prompt"]
    assert "You reconcile multiple planning proposals" in captured[
        "options"
    ].system_prompt
