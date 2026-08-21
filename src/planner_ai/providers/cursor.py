from __future__ import annotations

import asyncio
import shutil
import tempfile
from dataclasses import dataclass

from planner_ai.providers.call_abort import (
    ProviderAbortError,
    create_call_abort,
    is_abort_error,
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

READ_TOOLS = ["read", "grep", "glob", "ls", "semSearch"]


async def run_prompt(
    api_key: str,
    model_id: str,
    prompt: str,
    options: ProviderCallOptions | None = None,
) -> str:
    from cursor_sdk import (
        AgentOptions,
        AsyncClient,
        CursorAgentError,
        LocalAgentOptions,
        LocalAgentStoreConfig,
    )

    cwd = get_workspace_cwd()
    abort = create_call_abort(options)
    abort.throw_if_aborted()
    store_dir = tempfile.mkdtemp(prefix="planner-ai-cursor-")

    try:
        async with await AsyncClient.launch_bridge(
            workspace=str(cwd)
        ) as client:
            async with await client.agents.create(
                AgentOptions(
                    model=model_id,
                    api_key=api_key,
                    tools=list(READ_TOOLS),
                    local=LocalAgentOptions(
                        cwd=str(cwd),
                        setting_sources=["project"],
                        store=LocalAgentStoreConfig(
                            type="jsonl",
                            root_dir=store_dir,
                        ),
                    ),
                ),
            ) as agent:
                run = await agent.send(prompt)

                async def on_abort() -> None:
                    if run.supports("cancel"):
                        await run.cancel()

                cancel_watch: asyncio.Task[None] | None = None
                if abort.event.is_set():
                    await on_abort()
                else:

                    async def watch() -> None:
                        await abort.event.wait()
                        await on_abort()

                    cancel_watch = asyncio.create_task(watch())

                try:
                    result = await run.wait()

                    if abort.event.is_set() or result.status == "cancelled":
                        if isinstance(abort.reason, BaseException):
                            raise abort.reason
                        raise ProviderAbortError("Aborted")

                    if result.status != "finished":
                        err_obj = getattr(result, "error", None)
                        detail = (
                            getattr(err_obj, "message", None)
                            if err_obj is not None
                            else None
                        )
                        if not detail:
                            detail = result.status
                        raise RuntimeError(f"Cursor agent failed: {detail}")

                    text = (
                        result.result.strip()
                        if isinstance(result.result, str)
                        else None
                    )
                    if not text:
                        raise RuntimeError("Cursor returned empty text")
                    return text
                finally:
                    if cancel_watch is not None:
                        cancel_watch.cancel()
                        try:
                            await cancel_watch
                        except asyncio.CancelledError:
                            pass
    except BaseException as err:
        if isinstance(err, CursorAgentError):
            raise
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
        shutil.rmtree(store_dir, ignore_errors=True)


@dataclass
class CursorProposer:
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
class CursorConsensus:
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


def create_cursor_proposer(
    api_key: str,
    model_id: str,
    label: str,
) -> ModelProvider:
    return CursorProposer(
        id=f"cursor:{model_id}",
        label=label,
        _api_key=api_key,
        _model_id=model_id,
    )


def create_cursor_consensus(
    api_key: str,
    model_id: str,
) -> ConsensusProvider:
    return CursorConsensus(_api_key=api_key, _model_id=model_id)
