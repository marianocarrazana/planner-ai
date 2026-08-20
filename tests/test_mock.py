from __future__ import annotations

import asyncio
import time

import pytest

from planner_ai.providers.call_abort import ProviderAbortError
from planner_ai.providers.mock import MockProposer, mock_consensus, mock_proposers
from planner_ai.providers.types import ProviderCallOptions


def _alpha() -> MockProposer:
    return next(p for p in mock_proposers if p.id == "alpha")


def _beta() -> MockProposer:
    return next(p for p in mock_proposers if p.id == "beta")


def test_mock_propose_plan_mode() -> None:
    async def run() -> str:
        return await _alpha().propose("Ship feature X")

    body = asyncio.run(run())
    assert body.startswith("# Proposal from Model Alpha\n")
    assert "Goal: Ship feature X" in body
    assert "## Approach (breadth-first)" in body
    assert body.endswith("\n")


def test_mock_propose_ask_mode() -> None:
    async def run() -> str:
        return await _alpha().propose(
            "What does main do?",
            ProviderCallOptions(mode="ask"),
        )

    body = asyncio.run(run())
    assert body.startswith("# Answer from Model Alpha\n")
    assert "Question: What does main do?" in body
    assert "## Take (breadth-first)" in body


def test_mock_propose_improve_mode() -> None:
    async def run() -> str:
        return await _alpha().propose(
            "Commits in this branch",
            ProviderCallOptions(mode="improve"),
        )

    body = asyncio.run(run())
    assert body.startswith("# Improvements from Model Alpha\n")
    assert "Scope: Commits in this branch" in body
    assert "## Findings (breadth-first)" in body


def test_mock_reconcile_plan_mode() -> None:
    async def run() -> str:
        return await mock_consensus.reconcile(
            "Ship it",
            [
                {"id": "alpha", "body": "a"},
                {"id": "beta", "body": "b"},
            ],
        )

    body = asyncio.run(run())
    assert body.startswith("# Plan\n")
    assert "## Goal\n\nShip it\n" in body
    assert "- alpha\n- beta" in body
    assert "## Notes" in body


def test_mock_reconcile_ask_mode() -> None:
    async def run() -> str:
        return await mock_consensus.reconcile(
            "What is X?",
            [{"id": "alpha", "body": "a"}],
            ProviderCallOptions(mode="ask"),
        )

    body = asyncio.run(run())
    assert body.startswith("# Answer\n")
    assert "## Question\n\nWhat is X?\n" in body
    assert "## Response" in body
    assert "free of a planning template" in body


def test_mock_reconcile_improve_mode() -> None:
    async def run() -> str:
        return await mock_consensus.reconcile(
            "Whole repo",
            [{"id": "alpha", "body": "a"}],
            ProviderCallOptions(mode="improve"),
        )

    body = asyncio.run(run())
    assert body.startswith("# Improvements\n")
    assert "## Scope\n\nWhole repo\n" in body
    assert "## Prioritized list" in body
    assert "## Notes" in body


def test_mock_propose_timeout_cancels_sleep() -> None:
    async def run() -> None:
        with pytest.raises(ProviderAbortError, match=r"Timed out after 1ms"):
            await _beta().propose(
                "slow",
                ProviderCallOptions(timeout_ms=1),
            )

    started = time.monotonic()
    asyncio.run(run())
    elapsed = time.monotonic() - started
    assert elapsed < 0.5


def test_mock_propose_pre_set_cancel_event() -> None:
    async def run() -> None:
        cancel = asyncio.Event()
        cancel.set()
        with pytest.raises(ProviderAbortError):
            await _beta().propose(
                "cancelled",
                ProviderCallOptions(cancel_event=cancel),
            )

    started = time.monotonic()
    asyncio.run(run())
    elapsed = time.monotonic() - started
    assert elapsed < 0.3
