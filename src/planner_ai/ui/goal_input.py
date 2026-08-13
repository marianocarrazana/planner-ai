from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Input, Static

from planner_ai.pipeline.types import RunMode

if TYPE_CHECKING:
    from planner_ai.app import PlannerApp


class ModePill(Static):
    """Clickable Plan / Ask mode toggle pill."""

    def __init__(self, mode: RunMode, label: str, *, id: str | None = None) -> None:
        super().__init__(f" {label} ", id=id)
        self.mode = mode
        self.can_focus = False

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, GoalInput):
                parent.set_mode(self.mode)
                return
            parent = parent.parent


class GoalInput(Widget):
    """Plan/Ask toggle + goal/question input."""

    DEFAULT_CSS = """
    GoalInput {
        height: auto;
        layout: vertical;
    }

    GoalInput #mode-row {
        height: 1;
        layout: horizontal;
        margin-bottom: 1;
    }

    GoalInput ModePill {
        width: auto;
        height: 1;
        margin-right: 2;
        color: #888888;
    }

    GoalInput ModePill.-active {
        color: black;
        background: cyan;
    }

    GoalInput #goal-prompt {
        height: 1;
        margin-bottom: 1;
    }

    GoalInput #goal-row {
        height: 1;
        layout: horizontal;
    }

    GoalInput #goal-prefix {
        color: #888888;
        width: 2;
        height: 1;
    }

    GoalInput #goal-field {
        width: 1fr;
        height: 1;
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

    @property
    def planner_app(self) -> PlannerApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        with Horizontal(id="mode-row"):
            yield ModePill("plan", "Plan", id="pill-plan")
            yield ModePill("ask", "Ask", id="pill-ask")
        yield Static("What goal should we plan for?", id="goal-prompt")
        with Horizontal(id="goal-row"):
            yield Static("> ", id="goal-prefix")
            yield Input(placeholder="Describe the goal…", id="goal-field")

    def on_mount(self) -> None:
        self.sync_mode(self.planner_app.run_mode)

    def sync_mode(self, mode: RunMode) -> None:
        self._mode = mode
        self.query_one("#pill-plan", ModePill).set_class(mode == "plan", "-active")
        self.query_one("#pill-ask", ModePill).set_class(mode == "ask", "-active")
        prompt = self.query_one("#goal-prompt", Static)
        field = self.query_one("#goal-field", Input)
        if mode == "ask":
            prompt.update("What do you want to ask?")
            field.placeholder = "Ask a question…"
        else:
            prompt.update("What goal should we plan for?")
            field.placeholder = "Describe the goal…"

    def set_mode(self, mode: RunMode) -> None:
        self.planner_app.set_run_mode(mode)
        self.sync_mode(mode)

    def focus_input(self) -> None:
        self.query_one("#goal-field", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        trimmed = event.value.strip()
        if trimmed:
            self.planner_app.submit_goal(trimmed)
