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


async def run_prompt(
    api_key: str,
    model_id: str,
    prompt: str,
    options: ProviderCallOptions | None = None,
) -> str:
    from openai_codex import ApprovalMode, AsyncCodex, Sandbox
    from openai_codex.client import CodexConfig

    cwd = get_workspace_cwd()
    abort = create_call_abort(options)
    abort.throw_if_aborted()

    try:
        async with AsyncCodex(
            CodexConfig(env={"CODEX_API_KEY": api_key})
        ) as codex:
            await codex.login_api_key(api_key)
            thread = await codex.thread_start(
                model=model_id,
                cwd=str(cwd),
                sandbox=Sandbox.read_only,
                approval_mode=ApprovalMode.deny_all,
            )

            handle = await thread.turn(prompt)

            async def on_cancel() -> None:
                await handle.interrupt()

            turn = await wait_or_abort(
                handle.run(),
                abort,
                on_cancel=on_cancel,
            )

            text = (
                turn.final_response.strip()
                if isinstance(turn.final_response, str)
                else None
            )
            if not text:
                raise RuntimeError("Codex returned empty text")
            return text
    except BaseException as err:
        if is_abort_error(err) or abort.event.is_set():
            if isinstance(abort.reason, BaseException):
                raise abort.reason from err
            if isinstance(err, ProviderAbortError):
                raise
            raise ProviderAbortError(
                str(err) if str(err) else "Aborted"
            ) from err
        raise
    finally:
        abort.cleanup()


@dataclass
class CodexProposer:
    id: str
    label: str
    _api_key: str
    _model_id: str

    async def propose(
        self,
        goal: str,
        options: ProviderCallOptions | None = None,
    ) -> str:
        cwd = get_workspace_cwd()
        mode = options.mode if options else None
        resolved = resolve_propose_prompts(mode, goal, str(cwd))
        return await run_prompt(
            self._api_key,
            self._model_id,
            f"{resolved.system}\n\n{resolved.user}",
            options,
        )


@dataclass
class CodexConsensus:
    _api_key: str
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
        return await run_prompt(
            self._api_key,
            self._model_id,
            f"{resolved.system}\n\n{resolved.user}",
            options,
        )


def create_codex_proposer(
    api_key: str,
    model_id: str,
    label: str,
) -> ModelProvider:
    return CodexProposer(
        id=f"codex:{model_id}",
        label=label,
        _api_key=api_key,
        _model_id=model_id,
    )


def create_codex_consensus(
    api_key: str,
    model_id: str,
) -> ConsensusProvider:
    return CodexConsensus(_api_key=api_key, _model_id=model_id)
