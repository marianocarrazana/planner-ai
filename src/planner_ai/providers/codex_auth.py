from __future__ import annotations

import asyncio
import webbrowser
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal

CodexAuthMethod = Literal["chatgpt", "apiKey"]
CodexLoginMethod = Literal["browser", "device"]


@dataclass(frozen=True)
class CodexAuthStatus:
    authenticated: bool
    method: CodexAuthMethod | None = None
    plan: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class CodexLoginDetails:
    method: CodexLoginMethod
    url: str
    user_code: str | None = None


def api_key_auth_status() -> CodexAuthStatus:
    return CodexAuthStatus(authenticated=True, method="apiKey")


def _status_from_account(account: object | None) -> CodexAuthStatus:
    if account is None:
        return CodexAuthStatus(authenticated=False)

    root = getattr(account, "root", None)
    method = getattr(root, "type", None)
    if method == "chatgpt":
        plan = getattr(root, "plan_type", None)
        plan_value = getattr(plan, "value", plan)
        return CodexAuthStatus(
            authenticated=True,
            method="chatgpt",
            plan=plan_value if isinstance(plan_value, str) else None,
        )
    if method == "apiKey":
        return api_key_auth_status()
    return CodexAuthStatus(authenticated=False)


async def read_codex_auth_status() -> CodexAuthStatus:
    """Read Codex's shared cached account without exposing account identity."""
    try:
        from openai_codex import AsyncCodex

        async with AsyncCodex() as codex:
            response = await codex.account()
    except Exception:
        return CodexAuthStatus(
            authenticated=False,
            error="Unable to check the shared Codex login",
        )

    return _status_from_account(response.account)


async def login_codex_chatgpt(
    method: CodexLoginMethod,
    on_ready: Callable[[CodexLoginDetails], None],
    *,
    browser_opener: Callable[[str], object] = webbrowser.open,
) -> CodexAuthStatus:
    """Run a cancellable ChatGPT login and return the resulting account state."""
    from openai_codex import AsyncCodex

    handle = None
    completed = False
    async with AsyncCodex() as codex:
        try:
            if method == "browser":
                handle = await codex.login_chatgpt()
                details = CodexLoginDetails(method=method, url=handle.auth_url)
                on_ready(details)
                with suppress(Exception):
                    await asyncio.to_thread(browser_opener, handle.auth_url)
            else:
                handle = await codex.login_chatgpt_device_code()
                details = CodexLoginDetails(
                    method=method,
                    url=handle.verification_url,
                    user_code=handle.user_code,
                )
                on_ready(details)

            result = await handle.wait()
            completed = True
            if not result.success:
                raise RuntimeError(result.error or "ChatGPT login failed")
            with suppress(Exception):
                status = _status_from_account((await codex.account()).account)
                if status.authenticated:
                    return status
            return CodexAuthStatus(authenticated=True, method="chatgpt")
        finally:
            if handle is not None and not completed:
                with suppress(Exception, asyncio.CancelledError):
                    await asyncio.shield(handle.cancel())


async def logout_codex() -> None:
    from openai_codex import AsyncCodex

    async with AsyncCodex() as codex:
        await codex.logout()


def logout_codex_sync() -> None:
    from openai_codex import Codex

    with Codex() as codex:
        codex.logout()
