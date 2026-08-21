from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from planner_ai.providers.codex_auth import (
    CodexLoginDetails,
    login_codex_chatgpt,
    logout_codex,
    read_codex_auth_status,
)


@dataclass
class FakeLoginResult:
    success: bool
    error: str | None = None


class FakeHandle:
    auth_url = "https://example.test/browser"
    verification_url = "https://example.test/device"
    user_code = "ABCD-EFGH"

    def __init__(self, result: FakeLoginResult | None = None) -> None:
        self.result = result or FakeLoginResult(True)
        self.cancelled = False
        self.wait_forever = False

    async def wait(self) -> FakeLoginResult:
        if self.wait_forever:
            await asyncio.Event().wait()
        return self.result

    async def cancel(self) -> None:
        self.cancelled = True


class FakeCodex:
    account_response = SimpleNamespace(account=None)
    handle = FakeHandle()
    logged_out = False

    async def __aenter__(self) -> FakeCodex:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def account(self) -> object:
        return self.account_response

    async def login_chatgpt(self) -> FakeHandle:
        return self.handle

    async def login_chatgpt_device_code(self) -> FakeHandle:
        return self.handle

    async def logout(self) -> None:
        type(self).logged_out = True


@pytest.fixture(autouse=True)
def fake_openai_codex(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeCodex.account_response = SimpleNamespace(account=None)
    FakeCodex.handle = FakeHandle()
    FakeCodex.logged_out = False
    module = MagicMock()
    module.AsyncCodex = FakeCodex
    monkeypatch.setitem(sys.modules, "openai_codex", module)


def test_read_chatgpt_status_without_identity() -> None:
    account = SimpleNamespace(
        root=SimpleNamespace(
            type="chatgpt",
            plan_type=SimpleNamespace(value="plus"),
            email="private@example.test",
        )
    )
    FakeCodex.account_response = SimpleNamespace(account=account)

    status = asyncio.run(read_codex_auth_status())

    assert status.authenticated is True
    assert status.method == "chatgpt"
    assert status.plan == "plus"
    assert "private" not in repr(status)


def test_read_api_key_and_missing_status() -> None:
    account = SimpleNamespace(root=SimpleNamespace(type="apiKey"))
    FakeCodex.account_response = SimpleNamespace(account=account)
    assert asyncio.run(read_codex_auth_status()).method == "apiKey"

    FakeCodex.account_response = SimpleNamespace(account=None)
    assert asyncio.run(read_codex_auth_status()).authenticated is False


def test_read_status_failure_is_non_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_account(_self) -> object:
        raise RuntimeError("private@example.test")

    monkeypatch.setattr(FakeCodex, "account", fail_account)
    status = asyncio.run(read_codex_auth_status())
    assert status.authenticated is False
    assert status.error == "Unable to check the shared Codex login"
    assert "private" not in repr(status)


def test_browser_login_opens_and_publishes_url() -> None:
    opened: list[str] = []
    details: list[CodexLoginDetails] = []
    status = asyncio.run(
        login_codex_chatgpt(
            "browser",
            details.append,
            browser_opener=opened.append,
        )
    )

    assert details == [
        CodexLoginDetails(
            method="browser",
            url="https://example.test/browser",
        )
    ]
    assert opened == ["https://example.test/browser"]
    assert status.authenticated is True
    assert status.method == "chatgpt"


def test_browser_open_failure_keeps_login_alive() -> None:
    def fail_open(_url: str) -> None:
        raise OSError("no browser")

    details: list[CodexLoginDetails] = []
    status = asyncio.run(
        login_codex_chatgpt(
            "browser",
            details.append,
            browser_opener=fail_open,
        )
    )
    assert details[0].url == "https://example.test/browser"
    assert status.authenticated is True


def test_device_login_publishes_code() -> None:
    details: list[CodexLoginDetails] = []
    asyncio.run(login_codex_chatgpt("device", details.append))
    assert details == [
        CodexLoginDetails(
            method="device",
            url="https://example.test/device",
            user_code="ABCD-EFGH",
        )
    ]


def test_failed_login_raises_and_cancels() -> None:
    FakeCodex.handle = FakeHandle(FakeLoginResult(False, "denied"))
    with pytest.raises(RuntimeError, match="denied"):
        asyncio.run(login_codex_chatgpt("device", lambda _details: None))
    assert FakeCodex.handle.cancelled is False


def test_cancelled_login_cancels_handle() -> None:
    FakeCodex.handle.wait_forever = True

    async def run() -> None:
        task = asyncio.create_task(
            login_codex_chatgpt("device", lambda _details: None)
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert FakeCodex.handle.cancelled is True


def test_logout_uses_shared_codex_session() -> None:
    asyncio.run(logout_codex())
    assert FakeCodex.logged_out is True
