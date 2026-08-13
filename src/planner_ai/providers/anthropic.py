from __future__ import annotations

from dataclasses import dataclass

from planner_ai.providers.call_abort import (
    ProviderAbortError,
    create_call_abort,
    is_abort_error,
    wait_or_abort,
)
from planner_ai.providers.prompts import (
    resolve_consensus_prompts,
    resolve_propose_prompts,
)
from planner_ai.providers.types import (
    ConsensusProvider,
    ModelProvider,
    ProposalRef,
    ProviderCallOptions,
)
from planner_ai.workspace import get_workspace_cwd

READ_TOOLS = ["Read", "Glob", "Grep"]
DISALLOWED_TOOLS = [
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "Bash",
    "BashOutput",
    "KillShell",
]


def _claude_env(token: str) -> dict[str, str]:
    # Merge overlay: Python SDK inherits os.environ then applies this.
    # Blank ANTHROPIC_API_KEY so an ambient Console key cannot beat OAuth.
    return {
        "CLAUDE_CODE_OAUTH_TOKEN": token,
        "ANTHROPIC_API_KEY": "",
    }


async def _collect_query(
    prompt: str,
    options: object,
) -> tuple[str | None, str | None]:
    from claude_agent_sdk import ResultMessage, query

    result_text: str | None = None
    error_detail: str | None = None

    async for message in query(prompt=prompt, options=options):
        if not isinstance(message, ResultMessage):
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


async def run_claude(
    token: str,
    model_id: str,
    system: str,
    prompt: str,
    options: ProviderCallOptions | None = None,
) -> str:
    from claude_agent_sdk import ClaudeAgentOptions

    cwd = get_workspace_cwd()
    abort = create_call_abort(options)
    result_text: str | None = None
    error_detail: str | None = None

    try:
        abort.throw_if_aborted()

        agent_options = ClaudeAgentOptions(
            model=model_id,
            system_prompt=system,
            cwd=str(cwd),
            setting_sources=["project"],
            tools=list(READ_TOOLS),
            allowed_tools=list(READ_TOOLS),
            disallowed_tools=list(DISALLOWED_TOOLS),
            permission_mode="dontAsk",
            env=_claude_env(token),
        )

        result_text, error_detail = await wait_or_abort(
            _collect_query(prompt, agent_options),
            abort,
        )
    except BaseException as err:
        if is_abort_error(err) or abort.event.is_set():
            if isinstance(abort.reason, BaseException):
                raise abort.reason from err
            if isinstance(err, ProviderAbortError):
                raise
            raise ProviderAbortError(
                str(err) if str(err) else "Aborted"
            ) from err
        raise RuntimeError(
            f"Claude Agent SDK failed: {err}"
            if isinstance(err, Exception)
            else f"Claude Agent SDK failed: {err!s}"
        ) from err
    finally:
        abort.cleanup()

    if result_text:
        return result_text

    if abort.event.is_set():
        if isinstance(abort.reason, BaseException):
            raise abort.reason
        raise ProviderAbortError("Aborted")

    if error_detail:
        raise RuntimeError(f"Claude Agent SDK failed: {error_detail}")
    raise RuntimeError("Claude Agent SDK returned empty text")


@dataclass
class AnthropicProposer:
    id: str
    label: str
    _token: str
    _model_id: str

    async def propose(
        self,
        goal: str,
        options: ProviderCallOptions | None = None,
    ) -> str:
        cwd = get_workspace_cwd()
        mode = options.mode if options else None
        resolved = resolve_propose_prompts(mode, goal, str(cwd))
        return await run_claude(
            self._token,
            self._model_id,
            resolved.system,
            resolved.user,
            options,
        )


@dataclass
class AnthropicConsensus:
    _token: str
    _model_id: str

    async def reconcile(
        self,
        goal: str,
        proposals: list[ProposalRef],
        options: ProviderCallOptions | None = None,
    ) -> str:
        cwd = get_workspace_cwd()
        mode = options.mode if options else None
        resolved = resolve_consensus_prompts(
            mode, goal, str(cwd), proposals
        )
        return await run_claude(
            self._token,
            self._model_id,
            resolved.system,
            resolved.user,
            options,
        )


def create_anthropic_proposer(
    token: str,
    model_id: str,
    label: str,
) -> ModelProvider:
    return AnthropicProposer(
        id=f"anthropic:{model_id}",
        label=label,
        _token=token,
        _model_id=model_id,
    )


def create_anthropic_consensus(
    token: str,
    model_id: str,
) -> ConsensusProvider:
    return AnthropicConsensus(_token=token, _model_id=model_id)
