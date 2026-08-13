from __future__ import annotations

import asyncio
import time

import pytest

from planner_ai.providers.call_abort import (
    ProviderAbortError,
    abortable_sleep,
    create_call_abort,
    is_abort_error,
    wait_or_abort,
)
from planner_ai.providers.types import ProviderCallOptions


def test_abortable_sleep_completes_without_abort() -> None:
    async def run() -> None:
        await abortable_sleep(50)

    started = time.monotonic()
    asyncio.run(run())
    elapsed = time.monotonic() - started
    assert elapsed >= 0.04


def test_abortable_sleep_parent_event_cancels() -> None:
    async def run() -> None:
        cancel = asyncio.Event()
        abort = create_call_abort(ProviderCallOptions(cancel_event=cancel))
        try:

            async def fire() -> None:
                await asyncio.sleep(0.02)
                cancel.set()

            fire_task = asyncio.create_task(fire())
            with pytest.raises(ProviderAbortError):
                await abortable_sleep(500, abort)
            await fire_task
        finally:
            abort.cleanup()

    started = time.monotonic()
    asyncio.run(run())
    elapsed = time.monotonic() - started
    assert elapsed < 0.3


def test_create_call_abort_timeout() -> None:
    async def run() -> None:
        abort = create_call_abort(ProviderCallOptions(timeout_ms=20))
        try:
            with pytest.raises(ProviderAbortError, match=r"Timed out after 20ms"):
                await abortable_sleep(500, abort)
        finally:
            abort.cleanup()

    asyncio.run(run())


def test_is_abort_error() -> None:
    assert is_abort_error(ProviderAbortError())
    assert is_abort_error(ProviderAbortError("Timed out after 1ms"))
    assert is_abort_error(asyncio.CancelledError())
    assert not is_abort_error(ValueError("nope"))
    assert not is_abort_error("Aborted")


def test_wait_or_abort_completes() -> None:
    async def run() -> str:
        abort = create_call_abort()
        try:

            async def work() -> str:
                await asyncio.sleep(0.02)
                return "ok"

            return await wait_or_abort(work(), abort)
        finally:
            abort.cleanup()

    assert asyncio.run(run()) == "ok"


def test_wait_or_abort_cancels_and_calls_on_cancel() -> None:
    async def run() -> None:
        cancel = asyncio.Event()
        abort = create_call_abort(ProviderCallOptions(cancel_event=cancel))
        cancelled: list[str] = []
        try:

            async def work() -> str:
                await asyncio.sleep(1)
                return "late"

            async def on_cancel() -> None:
                cancelled.append("yes")

            async def fire() -> None:
                await asyncio.sleep(0.02)
                cancel.set()

            fire_task = asyncio.create_task(fire())
            with pytest.raises(ProviderAbortError):
                await wait_or_abort(work(), abort, on_cancel=on_cancel)
            await fire_task
            assert cancelled == ["yes"]
        finally:
            abort.cleanup()

    started = time.monotonic()
    asyncio.run(run())
    assert time.monotonic() - started < 0.5
