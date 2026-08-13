from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static, Tab, Tabs

from planner_ai.pipeline.types import ProposalState, RunMode

if TYPE_CHECKING:
    from planner_ai.app import PlannerApp

PRIMARY_TAB_ID = "primary"


def _sanitize_tab_id(tab_id: str) -> str:
    return tab_id.replace(":", "-").replace("/", "-").replace(".", "-")


class ResultTabs(Tabs):
    """Inner result tabs; keyboard focus stays on ResultBrowser."""

    can_focus = False


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

    ResultBrowser ResultTabs {
        height: auto;
        width: 100%;
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
    """

    BINDINGS = [
        Binding("n", "plan_another", show=False),
        Binding("enter", "exit", show=False),
        Binding("q", "exit", show=False),
        Binding("escape", "exit", show=False),
        Binding("left", "prev_tab", "Prev tab"),
        Binding("right", "next_tab", "Next tab"),
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
        self._widget_to_logical: dict[str, str] = {}
        self._remount_token = 0
        self._syncing_rb_tabs = False
        self._rebuild_widget_map()

    def _id_prefix(self) -> str:
        return self.id or "rb"

    def _tab_widget_id(self, tab_id: str) -> str:
        return f"{self._id_prefix()}-tab-{_sanitize_tab_id(tab_id)}"

    def _tabs_widget_id(self) -> str:
        return f"{self._id_prefix()}-tabs"

    def _rebuild_widget_map(self) -> None:
        self._widget_to_logical = {
            self._tab_widget_id(tab_id): tab_id for tab_id, _ in self._tabs
        }

    @property
    def planner_app(self) -> PlannerApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield Static("Plan ready", id="rb-heading")
        yield Static("", id="rb-errors", classes="-hidden")
        yield ResultTabs(
            Tab("Plan", id=self._tab_widget_id(PRIMARY_TAB_ID)),
            id=self._tabs_widget_id(),
        )
        yield Static("", id="rb-path")
        with VerticalScroll(id="rb-body"):
            yield Static("", id="rb-body-text")
        yield PlanAnotherLink("→ Plan another (or press n)", id="rb-another")

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
        self._rebuild_widget_map()

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
        tabs = self.query_one(ResultTabs)
        self._syncing_rb_tabs = True
        try:
            await tabs.clear()
            if token != self._remount_token:
                return
            for tab_id, label in self._tabs:
                await tabs.add_tab(Tab(label, id=self._tab_widget_id(tab_id)))
                if token != self._remount_token:
                    return
            desired = self._tab_widget_id(self._active_tab)
            if self._tabs and tabs.active != desired:
                tabs.active = desired
        finally:
            self._syncing_rb_tabs = False

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if not isinstance(event.tabs, ResultTabs):
            return
        event.stop()
        if self._syncing_rb_tabs:
            return
        if event.tab is None or event.tab.id is None:
            return
        logical = self._widget_to_logical.get(event.tab.id)
        if logical is None:
            return
        self._apply_tab(logical)

    def select_tab(self, tab_id: str) -> None:
        if not any(t[0] == tab_id for t in self._tabs):
            return
        tabs = self.query_one(ResultTabs)
        widget_id = self._tab_widget_id(tab_id)
        if tabs.active == widget_id and self._active_tab == tab_id:
            return
        if tabs.active != widget_id:
            tabs.active = widget_id
        else:
            self._apply_tab(tab_id)

    def _apply_tab(self, tab_id: str) -> None:
        self._active_tab = tab_id
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
