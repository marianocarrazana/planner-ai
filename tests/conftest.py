from __future__ import annotations

import pytest

from planner_ai.providers.codex_auth import CodexAuthStatus


@pytest.fixture(autouse=True)
def isolate_shared_codex_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let app-shell tests inspect or mutate a developer's Codex login."""

    async def signed_out() -> CodexAuthStatus:
        return CodexAuthStatus(authenticated=False)

    monkeypatch.setattr(
        "planner_ai.app.read_codex_auth_status",
        signed_out,
    )
