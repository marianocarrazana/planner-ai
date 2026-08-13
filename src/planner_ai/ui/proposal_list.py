from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from planner_ai.pipeline.types import ProposalState
from planner_ai.ui.plan_helpers import status_label


class ProposalList(Widget):
    """Live proposal status rows with a shared 1s elapsed timer."""

    DEFAULT_CSS = """
    ProposalList {
        height: auto;
        layout: vertical;
    }

    ProposalList #proposals-title {
        text-style: bold;
        height: 1;
    }

    ProposalList #proposals-summary {
        color: #888888;
        height: auto;
    }

    ProposalList #proposals-summary.-hidden {
        display: none;
    }

    ProposalList #proposals-rows {
        height: auto;
        layout: vertical;
    }

    ProposalList .proposal-row {
        height: 1;
        width: 100%;
    }

    ProposalList .status-pending {
        color: #888888;
    }

    ProposalList .status-streaming {
        color: yellow;
    }

    ProposalList .status-done {
        color: green;
    }

    ProposalList .status-error {
        color: red;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._proposals: list[ProposalState] = []
        self._elapsed: int | None = None
        self._timer = None
        self._remount_token = 0

    def compose(self) -> ComposeResult:
        yield Static("Proposals", id="proposals-title")
        yield Static("", id="proposals-summary", classes="-hidden")
        yield Vertical(id="proposals-rows")

    def on_unmount(self) -> None:
        self._stop_timer()

    def sync(self, proposals: list[ProposalState]) -> None:
        self._proposals = list(proposals)
        streaming = [p for p in proposals if p.status == "streaming"]
        any_streaming = len(streaming) > 0
        if any_streaming:
            started = next(
                (p.started_at for p in streaming if p.started_at is not None),
                None,
            )
            if started is not None:
                self._elapsed = max(
                    0, int((time.time() * 1000 - started) // 1000)
                )
            else:
                self._elapsed = None
            self._ensure_timer()
        else:
            self._elapsed = None
            self._stop_timer()
        if self.is_mounted:
            self._schedule_render()

    def _ensure_timer(self) -> None:
        if self._timer is None:
            self._timer = self.set_interval(1.0, self._tick)

    def _stop_timer(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _tick(self) -> None:
        streaming = [p for p in self._proposals if p.status == "streaming"]
        if not streaming:
            self._stop_timer()
            return
        started = next(
            (p.started_at for p in streaming if p.started_at is not None),
            None,
        )
        if started is None:
            return
        self._elapsed = max(0, int((time.time() * 1000 - started) // 1000))
        if self.is_mounted:
            self._schedule_render()

    def _schedule_render(self) -> None:
        self._remount_token += 1
        token = self._remount_token
        self.run_worker(
            self._render_rows(token),
            exclusive=True,
            name=f"proposal-list-{id(self)}",
        )

    async def _render_rows(self, token: int) -> None:
        if not self.is_mounted:
            return
        has_errors = any(p.status == "error" for p in self._proposals)
        done_count = sum(1 for p in self._proposals if p.status == "done")
        summary = self.query_one("#proposals-summary", Static)
        if has_errors:
            summary.update(
                f"consensus used {done_count} of {len(self._proposals)} proposers"
            )
            summary.remove_class("-hidden")
        else:
            summary.update("")
            summary.add_class("-hidden")

        rows = self.query_one("#proposals-rows", Vertical)
        await rows.remove_children()
        if token != self._remount_token or not self.is_mounted:
            return

        widgets: list[Static] = []
        for proposal in self._proposals:
            elapsed = (
                self._elapsed if proposal.status == "streaming" else None
            )
            label = status_label(proposal.status, elapsed)
            text = f"[{label}] {proposal.label}"
            if proposal.error:
                text += f" — {proposal.error}"
            widgets.append(
                Static(
                    text,
                    classes=f"proposal-row status-{proposal.status}",
                )
            )
        if widgets and self.is_mounted:
            await rows.mount(*widgets)
