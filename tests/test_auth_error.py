from __future__ import annotations

from planner_ai.pipeline.types import ProposalState
from planner_ai.providers.auth_error import (
    AUTH_ERROR_PATTERNS,
    collect_failing_credential_keys,
    credential_key_for_provider,
    is_auth_error_message,
)


def test_auth_error_patterns_match() -> None:
    samples = [
        "Invalid auth token",
        "Unauthorized request",
        "HTTP 401 from API",
        "Invalid authorization header",
        "Invalid API key provided",
        "Expired token detected",
        "Authentication failed",
        "Error: missing external auth",
    ]
    assert len(AUTH_ERROR_PATTERNS) == 8
    for sample in samples:
        assert is_auth_error_message(sample), sample


def test_non_auth_message() -> None:
    assert not is_auth_error_message("All proposals failed")
    assert not is_auth_error_message("network timeout")


def test_credential_key_for_provider() -> None:
    assert credential_key_for_provider("anthropic") == "claudeCodeOAuthToken"
    assert credential_key_for_provider("anthropic:claude-sonnet") == (
        "claudeCodeOAuthToken"
    )
    assert credential_key_for_provider("cursor:composer-2.5") == "cursorApiKey"
    assert credential_key_for_provider("codex:gpt-5.2") == "codexApiKey"
    assert credential_key_for_provider(
        "codex:gpt-5.2",
        codex_uses_config_key=False,
    ) == "codexSession"
    assert credential_key_for_provider("alpha") is None
    assert credential_key_for_provider("mock:alpha") is None


def test_collect_from_failed_proposers() -> None:
    keys = collect_failing_credential_keys(
        proposals=[
            ProposalState(
                id="cursor:composer-2.5",
                label="Composer",
                status="error",
                error="Unauthorized",
            ),
            ProposalState(
                id="alpha",
                label="Alpha",
                status="error",
                error="Unauthorized",
            ),
            ProposalState(
                id="codex:gpt-5.2",
                label="Codex",
                status="done",
                body="ok",
            ),
        ],
        error_message="All proposals failed",
        consensus_source="mock:consensus",
    )
    assert keys == ["cursorApiKey"]


def test_collect_from_consensus_source() -> None:
    keys = collect_failing_credential_keys(
        proposals=[],
        error_message="Invalid API key",
        consensus_source="anthropic:claude",
    )
    assert keys == ["claudeCodeOAuthToken"]


def test_collect_fallback_from_message_when_mock_consensus() -> None:
    keys = collect_failing_credential_keys(
        proposals=[],
        error_message="Claude Agent SDK failed: authentication required",
        consensus_source="alpha",
    )
    assert "claudeCodeOAuthToken" in keys

    keys = collect_failing_credential_keys(
        proposals=[],
        error_message="Cursor agent failed: unauthorized",
        consensus_source="alpha",
    )
    assert "cursorApiKey" in keys

    keys = collect_failing_credential_keys(
        proposals=[],
        error_message="Codex returned empty text with CODEX_API_KEY issue — unauthorized",
        consensus_source="alpha",
    )
    assert "codexApiKey" in keys

    keys = collect_failing_credential_keys(
        proposals=[],
        error_message="Codex authentication required",
        consensus_source="mock:alpha",
        codex_uses_config_key=False,
    )
    assert "codexSession" in keys
