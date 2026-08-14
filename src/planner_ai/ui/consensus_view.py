from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from planner_ai.pipeline.types import RunMode
from planner_ai.ui.plan_helpers import consensus_body, consensus_title


class ConsensusView(Widget):
    """Consensus / writing status with optional elapsed timer."""

    DEFAULT_CSS = """
    ConsensusView {
        height: auto;
        layout: vertical;
        margin-top: 1;
    }

    ConsensusView #consensus-title {
        text-style: bold;
        height: 1;
    }

    ConsensusView #consensus-body {
        color: #888888;
        height: auto;
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
        self._mode: RunMode = "plan"
        self._writing = False
        self._started_at: int | None = None
        self._elapsed: int | None = None
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Static("Consensus", id="consensus-title")
        yield Static("", id="consensus-body")

    def on_unmount(self) -> None:
        self._stop_timer()

    def sync(
        self,
        *,
        mode: RunMode = "plan",
        writing: bool = False,
        started_at: int | None = None,
    ) -> None:
        self._mode = mode
        self._writing = writing
        self._started_at = started_at
        active = not writing and started_at is not None
        if active and started_at is not None:
            self._elapsed = max(
                0, int((time.time() * 1000 - started_at) // 1000)
            )
            self._ensure_timer()
        else:
            self._elapsed = None
            self._stop_timer()
        if self.is_mounted:
            self._refresh_copy()

    def _ensure_timer(self) -> None:
        if self._timer is None:
            self._timer = self.set_interval(1.0, self._tick)

    def _stop_timer(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _tick(self) -> None:
        if self._writing or self._started_at is None:
            self._stop_timer()
            return
        self._elapsed = max(
            0, int((time.time() * 1000 - self._started_at) // 1000)
        )
        if self.is_mounted:
            self._refresh_copy()

    def _refresh_copy(self) -> None:
        self.query_one("#consensus-title", Static).update(
            consensus_title(writing=self._writing, mode=self._mode)
        )
        self.query_one("#consensus-body", Static).update(
            consensus_body(
                writing=self._writing,
                mode=self._mode,
                elapsed_seconds=self._elapsed,
            )
        )
