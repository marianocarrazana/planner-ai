from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Static

from planner_ai.pipeline.types import Phase, ProposalState, RunMode
from planner_ai.ui.consensus_view import ConsensusView
from planner_ai.ui.goal_input import GoalInput
from planner_ai.ui.plan_helpers import PlanGate, error_hint
from planner_ai.ui.proposal_list import ProposalList
from planner_ai.ui.result_browser import ResultBrowser

if TYPE_CHECKING:
    from planner_ai.app import PlannerApp


class PlanLink(Static):
    """Clickable cyan action row on PlanScreen."""

    def __init__(
        self,
        action: str,
        label: str,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(label, id=id, classes=classes)
        self.action = action
        self.can_focus = False

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, PlanScreen):
                parent.on_link_click(self.action)
                return
            parent = parent.parent


class PlanScreen(Widget):
    """Plan tab: gates, goal input, live run status, result, errors."""

    DEFAULT_CSS = """
    PlanScreen {
        height: 1fr;
        layout: vertical;
    }

    PlanScreen #plan-switcher {
        height: 1fr;
    }

    PlanScreen #need-auth,
    PlanScreen #need-models,
    PlanScreen #idle,
    PlanScreen #running,
    PlanScreen #done,
    PlanScreen #error {
        height: 1fr;
        layout: vertical;
    }

    PlanScreen #gate-title,
    PlanScreen #error-title {
        text-style: bold;
        height: 1;
    }

    PlanScreen #error-title,
    PlanScreen #error-message {
        color: red;
    }

    PlanScreen .gate-body,
    PlanScreen #error-hint {
        color: #888888;
        height: auto;
        margin-bottom: 1;
    }

    PlanScreen #gate-title-auth,
    PlanScreen #gate-title-models {
        text-style: bold;
        height: 1;
    }

    PlanScreen PlanLink {
        color: cyan;
        height: 1;
        width: 100%;
    }

    PlanScreen #error-proposals {
        margin-top: 1;
        margin-bottom: 1;
    }

    PlanScreen #error-clear.-hidden,
    PlanScreen #error-proposals.-hidden {
        display: none;
    }

    PlanScreen #run-consensus.-hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("enter", "retry", show=False),
        Binding("escape", "back_to_idle", show=False),
        Binding("r", "reset_failing", show=False),
        Binding("q", "quit_app", show=False),
    ]

    can_focus = True

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._phase: Phase = "idle"
        self._gate: PlanGate = "need-auth"
        self._mode: RunMode = "plan"
        self._proposals: list[ProposalState] = []
        self._consensus_started_at: int | None = None
        self._plan_path: str | None = None
        self._archive_path: str | None = None
        self._plan: str | None = None
        self._error: str | None = None
        self._failing_labels: list[str] = []

    @property
    def planner_app(self) -> PlannerApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        with ContentSwitcher(id="plan-switcher", initial="need-auth"):
            with Vertical(id="need-auth"):
                yield Static("Plan", id="gate-title-auth")
                yield Static(
                    "Add at least one provider token (or skip both for mocks) on the Auth "
                    "tab, then pick proposers and consensus.",
                    id="gate-body-auth",
                    classes="gate-body",
                )
                yield PlanLink(
                    "go-auth",
                    "→ Open Auth tab (or Ctrl+4)",
                    id="link-go-auth",
                )
            with Vertical(id="need-models"):
                yield Static("Plan", id="gate-title-models")
                yield Static(
                    "Select proposers and a consensus model before running a plan or ask.",
                    id="gate-body-models",
                    classes="gate-body",
                )
                yield PlanLink(
                    "go-models",
                    "→ Open Proposers tab (or Ctrl+2)",
                    id="link-go-models",
                )
            with Vertical(id="idle"):
                yield GoalInput(id="goal-input")
            with Vertical(id="running"):
                yield ProposalList(id="run-proposals")
                yield ConsensusView(id="run-consensus")
            with Vertical(id="done"):
                yield ResultBrowser(id="result-browser")
            with Vertical(id="error"):
                yield Static("Error", id="error-title")
                yield Static("", id="error-message")
                yield ProposalList(id="error-proposals")
                yield Static("", id="error-hint")
                yield PlanLink("retry", "→ Retry (or press Enter)", id="error-retry")
                yield PlanLink(
                    "back",
                    "→ Plan another (or press Esc)",
                    id="error-back",
                )
                yield PlanLink(
                    "reset",
                    "→ Clear failing credentials (or press r)",
                    id="error-clear",
                    classes="-hidden",
                )

    def sync(
        self,
        *,
        phase: Phase,
        gate: PlanGate,
        mode: RunMode,
        proposals: list[ProposalState],
        consensus_started_at: int | float | None,
        plan_path: str | Path | None,
        archive_path: str | Path | None,
        plan: str | None,
        error: str | None,
        failing_labels: list[str],
    ) -> None:
        self._phase = phase
        self._gate = gate
        self._mode = mode
        self._proposals = list(proposals)
        self._consensus_started_at = (
            int(consensus_started_at) if consensus_started_at is not None else None
        )
        self._plan_path = str(plan_path) if plan_path is not None else None
        self._archive_path = (
            str(archive_path) if archive_path is not None else None
        )
        self._plan = plan
        self._error = error
        self._failing_labels = list(failing_labels)
        self._apply()

    def _apply(self) -> None:
        switcher = self.query_one("#plan-switcher", ContentSwitcher)
        consensus = self.query_one("#run-consensus", ConsensusView)

        if self._gate == "need-auth":
            switcher.current = "need-auth"
            return
        if self._gate == "need-models":
            switcher.current = "need-models"
            return

        if self._phase == "idle":
            switcher.current = "idle"
            goal = self.query_one("#goal-input", GoalInput)
            goal.sync_mode(self._mode)
            goal.sync_models()
            return

        if self._phase in ("proposing", "consensus", "writing"):
            switcher.current = "running"
            self.query_one("#run-proposals", ProposalList).sync(self._proposals)
            writing = self._phase == "writing"
            show_consensus = self._phase in ("consensus", "writing")
            consensus.set_class(not show_consensus, "-hidden")
            if show_consensus:
                consensus.sync(
                    mode=self._mode,
                    writing=writing,
                    started_at=None if writing else self._consensus_started_at,
                )
            return

        if (
            self._phase == "done"
            and self._plan is not None
            and self._archive_path
        ):
            switcher.current = "done"
            self.query_one("#result-browser", ResultBrowser).sync(
                mode=self._mode,
                plan_path=self._plan_path,
                archive_path=self._archive_path,
                plan=self._plan,
                proposals=self._proposals,
                on_exit=False,
            )
            return

        if self._phase == "error":
            switcher.current = "error"
            self.query_one("#error-message", Static).update(
                self._error or "Something went wrong"
            )
            error_list = self.query_one("#error-proposals", ProposalList)
            if self._proposals:
                error_list.remove_class("-hidden")
                error_list.sync(self._proposals)
            else:
                error_list.add_class("-hidden")
            another = "Ask another" if self._mode == "ask" else "Plan another"
            self.query_one("#error-back", PlanLink).update(
                f"→ {another} (or press Esc)"
            )
            self.query_one("#error-hint", Static).update(
                error_hint(mode=self._mode, failing_labels=self._failing_labels)
            )
            clear = self.query_one("#error-clear", PlanLink)
            clear.set_class(len(self._failing_labels) == 0, "-hidden")
            return

        switcher.current = "idle"

    def focus_for_state(self) -> None:
        if self._gate != "ready":
            self.focus()
            return
        if self._phase == "idle":
            self.query_one("#goal-input", GoalInput).focus_input()
        elif self._phase == "done":
            self.query_one("#result-browser", ResultBrowser).focus()
        else:
            self.focus()

    def _active_for_error_keys(self) -> bool:
        return (
            self.planner_app.active_tab == "plan"
            and self._gate == "ready"
            and self._phase == "error"
        )

    def action_retry(self) -> None:
        if not self._active_for_error_keys():
            return
        self.planner_app.retry_run()

    def action_back_to_idle(self) -> None:
        if not self._active_for_error_keys():
            return
        self.planner_app.back_to_idle()

    def action_reset_failing(self) -> None:
        if not self._active_for_error_keys():
            return
        if not self._failing_labels:
            return
        self.planner_app.reset_failing_keys()

    def action_quit_app(self) -> None:
        if not self._active_for_error_keys():
            return
        self.app.exit()

    def on_link_click(self, action: str) -> None:
        match action:
            case "go-auth":
                self.planner_app.go_tab("auth")
            case "go-models":
                self.planner_app.go_tab("proposers")
            case "retry":
                self.planner_app.retry_run()
            case "back":
                self.planner_app.back_to_idle()
            case "reset":
                self.planner_app.reset_failing_keys()
