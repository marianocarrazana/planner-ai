from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from planner_ai.providers.types import ProviderCallOptions

T = TypeVar("T")


class ProviderAbortError(Exception):
    def __init__(self, message: str = "Aborted") -> None:
        super().__init__(message)


@dataclass
class CallAbortHandle:
    event: asyncio.Event
    cleanup: Callable[[], None]
    throw_if_aborted: Callable[[], None]
    reason: BaseException | None = None


def create_call_abort(
    options: ProviderCallOptions | None = None,
) -> CallAbortHandle:
    """Combine an optional parent cancel Event with an optional wall-clock timeout."""
    loop = asyncio.get_running_loop()
    event = asyncio.Event()
    reason_box: dict[str, BaseException | None] = {"reason": None}
    parent_task: asyncio.Task[None] | None = None
    timer_handle: asyncio.TimerHandle | None = None

    def abort(reason: BaseException | None = None) -> None:
        if event.is_set():
            return
        if reason is not None:
            reason_box["reason"] = reason
        event.set()
        handle.reason = reason_box["reason"]

    def cleanup() -> None:
        nonlocal timer_handle, parent_task
        if timer_handle is not None:
            timer_handle.cancel()
            timer_handle = None
        if parent_task is not None:
            parent_task.cancel()
            parent_task = None

    def throw_if_aborted() -> None:
        if not event.is_set():
            return
        reason = reason_box["reason"]
        if isinstance(reason, BaseException):
            raise reason
        raise ProviderAbortError("Aborted")

    handle = CallAbortHandle(
        event=event,
        cleanup=cleanup,
        throw_if_aborted=throw_if_aborted,
    )

    parent = options.cancel_event if options else None
    if parent is not None:
        if parent.is_set():
            abort(ProviderAbortError("Aborted"))
        else:

            async def watch_parent() -> None:
                await parent.wait()
                abort(ProviderAbortError("Aborted"))

            parent_task = asyncio.create_task(watch_parent())

    timeout_ms = options.timeout_ms if options else None
    if (
        isinstance(timeout_ms, int)
        and timeout_ms > 0
        and not event.is_set()
    ):
        timer_handle = loop.call_later(
            timeout_ms / 1000,
            lambda: abort(
                ProviderAbortError(f"Timed out after {timeout_ms}ms")
            ),
        )

    return handle


def is_abort_error(err: object) -> bool:
    if isinstance(err, ProviderAbortError):
        return True
    if isinstance(err, asyncio.CancelledError):
        return True
    return False


def _raise_abort(abort: CallAbortHandle) -> None:
    abort.throw_if_aborted()
    raise ProviderAbortError("Aborted")


async def wait_or_abort(
    awaitable: Awaitable[T],
    abort: CallAbortHandle,
    on_cancel: Callable[[], Awaitable[None] | None] | None = None,
) -> T:
    """Await *awaitable*, or cancel it when *abort.event* fires.

    If aborted, optionally run *on_cancel* (e.g. Cursor ``run.cancel()`` /
    Codex ``turn.interrupt()``), cancel the work task, then raise the abort
    reason (or ``ProviderAbortError``).
    """
    abort.throw_if_aborted()

    work = asyncio.ensure_future(awaitable)
    abort_waiter = asyncio.create_task(abort.event.wait())

    try:
        done, _pending = await asyncio.wait(
            {work, abort_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if abort_waiter in done or abort.event.is_set():
            if on_cancel is not None:
                maybe = on_cancel()
                if maybe is not None:
                    await maybe
            work.cancel()
            try:
                await work
            except (asyncio.CancelledError, Exception):
                pass
            _raise_abort(abort)

        abort_waiter.cancel()
        try:
            await abort_waiter
        except asyncio.CancelledError:
            pass

        try:
            return await work
        except asyncio.CancelledError as err:
            if abort.event.is_set() or is_abort_error(err):
                _raise_abort(abort)
            raise
    finally:
        if not abort_waiter.done():
            abort_waiter.cancel()
            try:
                await abort_waiter
            except asyncio.CancelledError:
                pass
        if not work.done():
            work.cancel()
            try:
                await work
            except (asyncio.CancelledError, Exception):
                pass


async def abortable_sleep(
    ms: int,
    abort: CallAbortHandle | None = None,
) -> None:
    """Sleep for ms, or raise if abort.event fires first."""
    if abort is None:
        await asyncio.sleep(ms / 1000)
        return

    if abort.event.is_set():
        abort.throw_if_aborted()
        raise ProviderAbortError("Aborted")

    try:
        async with asyncio.timeout(ms / 1000):
            await abort.event.wait()
    except TimeoutError:
        # Sleep completed without abort.
        return

    abort.throw_if_aborted()
    raise ProviderAbortError("Aborted")
