from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.events import MouseScrollDown, MouseScrollUp
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Static

from planner_ai.read_run_archive import (
    ArchivedRunSummary,
    list_archived_runs,
    read_archived_run,
)
from planner_ai.ui.result_browser import ResultBrowser
from planner_ai.write_run_archive import ARCHIVE_DIR


def clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


class HistoryRow(Static):
    """Clickable archived-run row."""

    def __init__(
        self,
        index: int,
        run: ArchivedRunSummary,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__("", id=id, classes=classes)
        self.index = index
        self.run = run
        self.can_focus = False

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, HistoryScreen):
                parent.on_row_click(self.index)
                return
            parent = parent.parent


class HistoryBackLink(Static):
    """Clickable back-to-list action on the error pane."""

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, HistoryScreen):
                parent.back_to_list_from_error()
                return
            parent = parent.parent


class HistoryScreen(Widget):
    """History tab: list archived runs, open detail via ResultBrowser."""

    DEFAULT_CSS = """
    HistoryScreen {
        height: 1fr;
        layout: vertical;
    }

    HistoryScreen #hist-switcher {
        height: 1fr;
    }

    HistoryScreen #hist-list,
    HistoryScreen #hist-loading,
    HistoryScreen #hist-error,
    HistoryScreen #hist-detail {
        height: 1fr;
        layout: vertical;
    }

    HistoryScreen #hist-title,
    HistoryScreen #hist-loading-title,
    HistoryScreen #hist-error-title {
        text-style: bold;
        height: 1;
    }

    HistoryScreen #hist-subtitle,
    HistoryScreen #hist-loading-msg,
    HistoryScreen #hist-empty,
    HistoryScreen #hist-footer {
        color: #888888;
        height: auto;
    }

    HistoryScreen #hist-list-error {
        color: red;
        height: auto;
    }

    HistoryScreen #hist-error-msg {
        color: red;
        height: auto;
        margin-bottom: 1;
    }

    HistoryScreen #hist-back {
        color: cyan;
        height: 1;
    }

    HistoryScreen #hist-rows {
        height: 1fr;
        layout: vertical;
        margin-top: 1;
        margin-bottom: 1;
    }

    HistoryScreen HistoryRow {
        height: 1;
        width: 100%;
    }

    HistoryScreen HistoryRow.-focused {
        color: black;
        background: cyan;
    }

    HistoryScreen #hist-empty.-hidden,
    HistoryScreen #hist-list-error.-hidden,
    HistoryScreen #hist-rows.-hidden,
    HistoryScreen #hist-loading-indicator.-hidden {
        display: none;
    }

    HistoryScreen #hist-loading-indicator {
        color: #888888;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("pageup", "page_up", show=False),
        Binding("pagedown", "page_down", show=False),
        Binding("enter", "activate", show=False),
        Binding("space", "activate", show=False),
        Binding("r", "reload", show=False),
        Binding("escape", "error_back", show=False),
        Binding("q", "error_back", show=False),
    ]

    can_focus = True
    cursor: reactive[int] = reactive(0)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._runs: list[ArchivedRunSummary] = []
        self._list_error: str | None = None
        self._loading_list = False
        self._view: str = "list"
        self._error_message: str | None = None
        self._loading_dir: str | None = None
        self._remount_token = 0

    def compose(self) -> ComposeResult:
        with ContentSwitcher(id="hist-switcher", initial="hist-list"):
            with Vertical(id="hist-list"):
                yield Static("History", id="hist-title")
                yield Static(
                    f"Archived runs in {ARCHIVE_DIR}/",
                    id="hist-subtitle",
                )
                yield Static("Loading…", id="hist-loading-indicator")
                yield Static("", id="hist-list-error", classes="-hidden")
                yield Static(
                    f"No archived runs in {ARCHIVE_DIR}",
                    id="hist-empty",
                    classes="-hidden",
                )
                with VerticalScroll(id="hist-rows", classes="-hidden"):
                    pass
                yield Static(
                    "r refresh · Ctrl+1–5 switch tabs",
                    id="hist-footer",
                )
            with Vertical(id="hist-loading"):
                yield Static("History", id="hist-loading-title")
                yield Static("", id="hist-loading-msg")
            with Vertical(id="hist-error"):
                yield Static("History", id="hist-error-title")
                yield Static("", id="hist-error-msg")
                yield HistoryBackLink(
                    "← Back to list (Esc)",
                    id="hist-back",
                )
            with Vertical(id="hist-detail"):
                yield ResultBrowser(id="hist-result-browser")

    def on_mount(self) -> None:
        self.reload()

    def show_list_and_reload(self) -> None:
        """Reset to list view and refresh (called when History tab is entered)."""
        self._view = "list"
        self.query_one("#hist-switcher", ContentSwitcher).current = "hist-list"
        self.reload()
        self.focus()

    def reload(self) -> None:
        self._loading_list = True
        self._list_error = None
        self._apply_list_chrome()
        try:
            next_runs = list_archived_runs()
            self._runs = next_runs
            if next_runs:
                self.cursor = clamp(self.cursor, 0, len(next_runs) - 1)
            else:
                self.cursor = 0
        except OSError as err:
            self._runs = []
            self._list_error = str(err) if str(err) else repr(err)
            self.cursor = 0
        finally:
            self._loading_list = False
            self._remount_rows()
            self._apply_list_chrome()

    def _remount_rows(self) -> None:
        self._remount_token += 1
        token = self._remount_token
        self.run_worker(
            self._remount_rows_async(token),
            exclusive=True,
            name="hist-remount-rows",
        )

    async def _remount_rows_async(self, token: int) -> None:
        rows = self.query_one("#hist-rows", VerticalScroll)
        await rows.remove_children()
        if token != self._remount_token:
            return
        widgets: list[HistoryRow] = []
        for index, run in enumerate(self._runs):
            count_label = (
                "1 proposer"
                if run.output_count == 1
                else f"{run.output_count} proposers"
            )
            focused = index == self.cursor
            prefix = "> " if focused else "  "
            label = (
                f"{prefix}{run.kind}  ·  {run.timestamp_label}  ·  {count_label}"
            )
            row = HistoryRow(
                index,
                run,
                id=f"hist-row-{index}",
                classes="-focused" if focused else None,
            )
            row.update(label)
            widgets.append(row)
        if widgets:
            await rows.mount(*widgets)
        if token != self._remount_token:
            return
        self._apply_list_chrome()

    def back_to_list(self) -> None:
        """Return from detail ResultBrowser; reload list."""
        self._view = "list"
        self.query_one("#hist-switcher", ContentSwitcher).current = "hist-list"
        self.reload()
        self.focus()

    def back_to_list_from_error(self) -> None:
        """Return from error pane without requiring a reload."""
        self._view = "list"
        self._error_message = None
        self.query_one("#hist-switcher", ContentSwitcher).current = "hist-list"
        self._apply_list_chrome()
        self.focus()

    def action_reload(self) -> None:
        if self._view != "list":
            return
        self.reload()

    def action_error_back(self) -> None:
        if self._view != "error":
            return
        self.back_to_list_from_error()

    def action_move_up(self) -> None:
        if self._view != "list" or not self._runs:
            return
        self.cursor = clamp(self.cursor - 1, 0, len(self._runs) - 1)

    def action_move_down(self) -> None:
        if self._view != "list" or not self._runs:
            return
        self.cursor = clamp(self.cursor + 1, 0, len(self._runs) - 1)

    def action_page_up(self) -> None:
        if self._view != "list" or not self._runs:
            return
        page = max(1, self.query_one("#hist-rows", VerticalScroll).size.height)
        self.cursor = clamp(self.cursor - page, 0, len(self._runs) - 1)

    def action_page_down(self) -> None:
        if self._view != "list" or not self._runs:
            return
        page = max(1, self.query_one("#hist-rows", VerticalScroll).size.height)
        self.cursor = clamp(self.cursor + page, 0, len(self._runs) - 1)

    def action_activate(self) -> None:
        if self._view == "error":
            self.back_to_list_from_error()
            return
        if self._view != "list" or not self._runs:
            return
        if 0 <= self.cursor < len(self._runs):
            self.open_run(self._runs[self.cursor])

    def on_row_click(self, index: int) -> None:
        if not (0 <= index < len(self._runs)):
            return
        self.cursor = index
        self.open_run(self._runs[index])

    def open_run(self, run: ArchivedRunSummary) -> None:
        self._view = "loading"
        self._loading_dir = run.dir_name
        switcher = self.query_one("#hist-switcher", ContentSwitcher)
        switcher.current = "hist-loading"
        self.query_one("#hist-loading-msg", Static).update(
            f"Loading {run.dir_name}…"
        )
        try:
            archived = read_archived_run(run.path)
        except OSError as err:
            self._view = "error"
            self._error_message = str(err) if str(err) else repr(err)
            switcher.current = "hist-error"
            self.query_one("#hist-error-msg", Static).update(self._error_message)
            self.focus()
            return

        self._view = "detail"
        switcher.current = "hist-detail"
        browser = self.query_one("#hist-result-browser", ResultBrowser)
        browser.sync(
            mode=archived.kind,
            plan_path=None,
            archive_path=str(run.path),
            plan=archived.plan,
            proposals=archived.proposals,
            title=f"Archived · {archived.kind} · {run.timestamp_label}",
            on_exit=True,
        )
        browser.focus()

    def _apply_list_chrome(self) -> None:
        subtitle = self.query_one("#hist-subtitle", Static)
        loading = self.query_one("#hist-loading-indicator", Static)
        empty = self.query_one("#hist-empty", Static)
        list_error = self.query_one("#hist-list-error", Static)
        rows = self.query_one("#hist-rows", VerticalScroll)
        footer = self.query_one("#hist-footer", Static)

        n = len(self._runs)
        if n > 0:
            scroll_hint = f" · {n} run{'s' if n != 1 else ''}"
        else:
            scroll_hint = ""
        subtitle.update(f"Archived runs in {ARCHIVE_DIR}/{scroll_hint}")

        if self._loading_list:
            loading.remove_class("-hidden")
            empty.add_class("-hidden")
            list_error.add_class("-hidden")
            rows.add_class("-hidden")
        elif self._list_error:
            loading.add_class("-hidden")
            empty.add_class("-hidden")
            list_error.remove_class("-hidden")
            list_error.update(self._list_error)
            rows.add_class("-hidden")
        elif n == 0:
            loading.add_class("-hidden")
            empty.remove_class("-hidden")
            list_error.add_class("-hidden")
            rows.add_class("-hidden")
        else:
            loading.add_class("-hidden")
            empty.add_class("-hidden")
            list_error.add_class("-hidden")
            rows.remove_class("-hidden")

        if n == 0:
            footer.update("r refresh · Ctrl+1–5 switch tabs")
        else:
            footer.update(
                "↑↓/wheel/PgUp/PgDn · Enter open · r refresh · Ctrl+1–5 tabs"
            )

    def watch_cursor(self, _cursor: int) -> None:
        if self._view != "list":
            return
        for row in self.query(HistoryRow):
            focused = row.index == self.cursor
            row.set_class(focused, "-focused")
            count_label = (
                "1 proposer"
                if row.run.output_count == 1
                else f"{row.run.output_count} proposers"
            )
            prefix = "> " if focused else "  "
            row.update(
                f"{prefix}{row.run.kind}  ·  {row.run.timestamp_label}  ·  {count_label}"
            )
            if focused:
                row.scroll_visible(animate=False)

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        if self._view != "list" or not self._runs:
            return
        event.stop()
        self.cursor = clamp(self.cursor - 1, 0, len(self._runs) - 1)

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        if self._view != "list" or not self._runs:
            return
        event.stop()
        self.cursor = clamp(self.cursor + 1, 0, len(self._runs) - 1)
