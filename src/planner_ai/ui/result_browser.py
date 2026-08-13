from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Label, Static

from planner_ai.pipeline.types import ProposalState, RunMode

if TYPE_CHECKING:
    from planner_ai.app import PlannerApp

PRIMARY_TAB_ID = "primary"


class ResultTabLabel(Static):
    """Clickable inner tab label for ResultBrowser."""

    def __init__(
        self,
        tab_id: str,
        label: str,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(f" {label} ", id=id, classes=classes)
        self.tab_id = tab_id
        self.tab_label = label
        self.can_focus = False

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, ResultBrowser):
                parent.select_tab(self.tab_id)
                return
            parent = parent.parent


class PlanAnotherLink(Static):
    """Clickable Plan/Ask another action."""

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, ResultBrowser):
                parent.action_plan_another()
                return
            parent = parent.parent


class ResultBrowser(Widget):
    """Primary Plan/Answer tab + per-proposer tabs; live or History detail."""

    DEFAULT_CSS = """
    ResultBrowser {
        height: 1fr;
        layout: vertical;
    }

    ResultBrowser #rb-heading {
        color: green;
        text-style: bold;
        height: 1;
    }

    ResultBrowser #rb-errors {
        color: #888888;
        height: 1;
    }

    ResultBrowser #rb-errors.-hidden {
        display: none;
    }

    ResultBrowser #rb-tab-row {
        height: 1;
        layout: horizontal;
        width: 100%;
    }

    ResultBrowser ResultTabLabel {
        width: auto;
        height: 1;
        margin-right: 2;
        color: #888888;
    }

    ResultBrowser ResultTabLabel.-active {
        color: black;
        background: cyan;
    }

    ResultBrowser #rb-tab-underline {
        height: 1;
        color: cyan;
    }

    ResultBrowser #rb-path {
        color: #888888;
        height: auto;
        margin-bottom: 1;
    }

    ResultBrowser #rb-path.-error {
        color: red;
    }

    ResultBrowser #rb-body {
        height: 1fr;
        border: none;
    }

    ResultBrowser #rb-body-text {
        height: auto;
        width: 100%;
    }

    ResultBrowser #rb-another {
        color: cyan;
        height: 1;
        margin-top: 1;
    }

    ResultBrowser #rb-another.-hidden {
        display: none;
    }

    ResultBrowser #rb-hints {
        color: #888888;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("n", "plan_another", show=False),
        Binding("enter", "exit", show=False),
        Binding("q", "exit", show=False),
        Binding("escape", "exit", show=False),
        Binding("left", "prev_tab", show=False),
        Binding("right", "next_tab", show=False),
        Binding("left_square_bracket", "prev_tab", show=False),
        Binding("right_square_bracket", "next_tab", show=False),
        Binding("up", "scroll_up", show=False),
        Binding("down", "scroll_down", show=False),
        Binding("pageup", "page_up", show=False),
        Binding("pagedown", "page_down", show=False),
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
        self._mode: RunMode = "plan"
        self._plan_path: str | None = None
        self._archive_path: str | None = None
        self._plan: str = ""
        self._proposals: list[ProposalState] = []
        self._title: str | None = None
        self._on_exit = False
        self._active_tab: str = PRIMARY_TAB_ID
        self._tabs: list[tuple[str, str]] = [(PRIMARY_TAB_ID, "Plan")]
        self._remount_token = 0

    @property
    def planner_app(self) -> PlannerApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield Static("Plan ready", id="rb-heading")
        yield Static("", id="rb-errors", classes="-hidden")
        with Vertical(id="rb-tabs"):
            with Horizontal(id="rb-tab-row"):
                yield ResultTabLabel(PRIMARY_TAB_ID, "Plan", id="rb-tab-primary")
            yield Label("", id="rb-tab-underline")
        yield Static("", id="rb-path")
        with VerticalScroll(id="rb-body"):
            yield Static("", id="rb-body-text")
        yield PlanAnotherLink("→ Plan another (or press n)", id="rb-another")
        yield Static(
            "←→/[ ] tabs · ↑↓/wheel/PgUp/PgDn scroll · n plan another · Enter or q exit",
            id="rb-hints",
        )

    def sync(
        self,
        *,
        mode: RunMode,
        plan_path: str | None,
        archive_path: str | None,
        plan: str,
        proposals: list[ProposalState],
        title: str | None = None,
        on_exit: bool = False,
    ) -> None:
        self._mode = mode
        self._plan_path = plan_path
        self._archive_path = archive_path
        self._plan = plan
        self._proposals = list(proposals)
        self._title = title
        self._on_exit = on_exit
        self._active_tab = PRIMARY_TAB_ID

        is_ask = mode == "ask"
        primary_label = "Answer" if is_ask else "Plan"
        self._tabs = [(PRIMARY_TAB_ID, primary_label)]
        for proposal in self._proposals:
            self._tabs.append((proposal.id, proposal.label))

        if title is not None:
            heading = title
        elif on_exit:
            heading = "Archived run"
        elif is_ask:
            heading = "Answer ready"
        else:
            heading = "Plan ready"
        self.query_one("#rb-heading", Static).update(heading)

        has_errors = any(p.status == "error" for p in self._proposals)
        errors = self.query_one("#rb-errors", Static)
        if has_errors:
            done_count = sum(1 for p in self._proposals if p.status == "done")
            errors.update(
                f"consensus used {done_count} of {len(self._proposals)} proposers"
            )
            errors.remove_class("-hidden")
        else:
            errors.update("")
            errors.add_class("-hidden")

        another = self.query_one("#rb-another", PlanAnotherLink)
        if on_exit:
            another.add_class("-hidden")
        else:
            another_label = "Ask another" if is_ask else "Plan another"
            another.update(f"→ {another_label} (or press n)")
            another.remove_class("-hidden")

        if on_exit:
            hints = "←→/[ ] tabs · ↑↓/wheel/PgUp/PgDn scroll · Esc/Enter/q back"
        else:
            another_lower = (
                "ask another" if is_ask else "plan another"
            )
            hints = (
                f"←→/[ ] tabs · ↑↓/wheel/PgUp/PgDn scroll · "
                f"n {another_lower} · Enter or q exit"
            )
        self.query_one("#rb-hints", Static).update(hints)

        self._remount_tabs()
        self._refresh_body()

    def _remount_tabs(self) -> None:
        self._remount_token += 1
        token = self._remount_token
        self.run_worker(
            self._remount_tabs_async(token),
            exclusive=True,
            name="rb-remount-tabs",
        )

    async def _remount_tabs_async(self, token: int) -> None:
        row = self.query_one("#rb-tab-row", Horizontal)
        await row.remove_children()
        if token != self._remount_token:
            return
        widgets: list[ResultTabLabel] = []
        for tab_id, label in self._tabs:
            safe = (
                tab_id.replace(":", "-")
                .replace("/", "-")
                .replace(".", "-")
            )
            widgets.append(
                ResultTabLabel(
                    tab_id,
                    label,
                    id=f"rb-tab-{safe}",
                    classes="-active" if tab_id == self._active_tab else None,
                )
            )
        if widgets:
            await row.mount(*widgets)
        if token != self._remount_token:
            return
        self._refresh_tab_styles()

    def _refresh_tab_styles(self) -> None:
        for label in self.query(ResultTabLabel):
            label.set_class(label.tab_id == self._active_tab, "-active")

        underline = self.query_one("#rb-tab-underline", Label)
        parts: list[str] = []
        for i, (_tab_id, label) in enumerate(self._tabs):
            if i > 0:
                parts.append("  ")
            width = len(label) + 2
            if _tab_id == self._active_tab:
                parts.append("▬" * width)
            else:
                parts.append(" " * width)
        underline.update("".join(parts))

    def select_tab(self, tab_id: str) -> None:
        if tab_id == self._active_tab:
            return
        if not any(t[0] == tab_id for t in self._tabs):
            return
        self._active_tab = tab_id
        self._refresh_tab_styles()
        self._refresh_body()
        body = self.query_one("#rb-body", VerticalScroll)
        body.scroll_home(animate=False)

    def _active_proposal(self) -> ProposalState | None:
        if self._active_tab == PRIMARY_TAB_ID:
            return None
        for proposal in self._proposals:
            if proposal.id == self._active_tab:
                return proposal
        return None

    def _refresh_body(self) -> None:
        proposal = self._active_proposal()
        path = self.query_one("#rb-path", Static)

        if self._active_tab == PRIMARY_TAB_ID:
            if self._on_exit:
                path_label = self._archive_path or ""
            elif self._plan_path:
                path_label = (
                    f"Wrote {self._plan_path} · archived {self._archive_path}"
                )
            else:
                path_label = f"Archived {self._archive_path}"
            path.update(path_label)
            path.remove_class("-error")
            body_text = self._plan or "(empty)"
        elif proposal is not None and proposal.error:
            path.update(f"Error · {proposal.label}")
            path.add_class("-error")
            body_text = proposal.error or "(empty)"
        else:
            label = proposal.label if proposal is not None else "Proposal"
            path.update(label)
            path.remove_class("-error")
            body = proposal.body if proposal is not None else None
            body_text = body if body else "(empty)"

        self.query_one("#rb-body-text", Static).update(body_text)

    def _move_tab(self, delta: int) -> None:
        if not self._tabs:
            return
        ids = [t[0] for t in self._tabs]
        try:
            index = ids.index(self._active_tab)
        except ValueError:
            index = 0
        next_index = (index + delta) % len(ids)
        self.select_tab(ids[next_index])

    def action_prev_tab(self) -> None:
        self._move_tab(-1)

    def action_next_tab(self) -> None:
        self._move_tab(1)

    def action_scroll_up(self) -> None:
        self.query_one("#rb-body", VerticalScroll).scroll_up(animate=False)

    def action_scroll_down(self) -> None:
        self.query_one("#rb-body", VerticalScroll).scroll_down(animate=False)

    def action_page_up(self) -> None:
        self.query_one("#rb-body", VerticalScroll).scroll_page_up(animate=False)

    def action_page_down(self) -> None:
        self.query_one("#rb-body", VerticalScroll).scroll_page_down(animate=False)

    def action_plan_another(self) -> None:
        if self._on_exit:
            return
        self.planner_app.plan_another()

    def action_exit(self) -> None:
        if self._on_exit:
            parent = self.parent
            while parent is not None:
                # Avoid circular import: duck-type HistoryScreen
                back = getattr(parent, "back_to_list", None)
                if callable(back):
                    back()
                    return
                parent = parent.parent
            return
        self.app.exit()
