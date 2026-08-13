from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Button, ContentSwitcher, LoadingIndicator, OptionList, Static
from textual.widgets.option_list import Option

from planner_ai.read_run_archive import ArchivedRunSummary, list_archived_runs, read_archived_run
from planner_ai.ui.result_browser import ResultBrowser
from planner_ai.write_run_archive import ARCHIVE_DIR


class HistoryScreen(Widget):
    DEFAULT_CSS = """
    HistoryScreen { height: 1fr; layout: vertical; }
    HistoryScreen #hist-switcher,
    HistoryScreen #hist-list,
    HistoryScreen #hist-loading,
    HistoryScreen #hist-error,
    HistoryScreen #hist-detail { height: 1fr; }
    HistoryScreen #hist-title,
    HistoryScreen #hist-loading-title,
    HistoryScreen #hist-error-title { text-style: bold; height: 1; }
    HistoryScreen #hist-subtitle,
    HistoryScreen #hist-loading-msg,
    HistoryScreen #hist-empty { color: #888888; height: auto; }
    HistoryScreen #hist-list-error,
    HistoryScreen #hist-error-msg { color: red; height: auto; }
    HistoryScreen #hist-back {
        color: cyan; background: transparent; border: none;
        width: auto; min-width: 0; height: 3; padding: 0;
    }
    HistoryScreen #hist-rows { height: 1fr; margin: 1 0; }
    HistoryScreen #hist-loading-indicator { height: 3; color: #888888; }
    HistoryScreen .-hidden { display: none; }
    """
    BINDINGS = [
        Binding("r", "reload", "Refresh"),
        Binding("escape", "error_back", show=False),
        Binding("q", "error_back", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._runs: list[ArchivedRunSummary] = []
        self._list_error: str | None = None
        self._loading_list = False
        self._view = "list"

    def compose(self) -> ComposeResult:
        with ContentSwitcher(id="hist-switcher", initial="hist-list"):
            with Vertical(id="hist-list"):
                yield Static("History", id="hist-title")
                yield Static(f"Archived runs in {ARCHIVE_DIR}/", id="hist-subtitle")
                yield LoadingIndicator(id="hist-loading-indicator")
                yield Static("", id="hist-list-error", classes="-hidden")
                yield Static(f"No archived runs in {ARCHIVE_DIR}", id="hist-empty", classes="-hidden")
                yield OptionList(id="hist-rows", classes="-hidden")
            with Vertical(id="hist-loading"):
                yield Static("History", id="hist-loading-title")
                yield LoadingIndicator()
                yield Static("", id="hist-loading-msg")
            with Vertical(id="hist-error"):
                yield Static("History", id="hist-error-title")
                yield Static("", id="hist-error-msg")
                yield Button("← Back to list (Esc)", id="hist-back", flat=True)
            with Vertical(id="hist-detail"):
                yield ResultBrowser(id="hist-result-browser")

    def on_mount(self) -> None:
        self.reload()

    def show_list_and_reload(self) -> None:
        self._view = "list"
        self.query_one("#hist-switcher", ContentSwitcher).current = "hist-list"
        self.reload()
        self._focus_list()

    def reload(self) -> None:
        self._loading_list = True
        self._list_error = None
        self._apply_list_chrome()
        try:
            self._runs = list_archived_runs()
        except OSError as err:
            self._runs = []
            self._list_error = str(err) or repr(err)
        self._loading_list = False
        rows = self.query_one("#hist-rows", OptionList)
        rows.clear_options()
        for run in self._runs:
            count = "1 proposer" if run.output_count == 1 else f"{run.output_count} proposers"
            rows.add_option(Option(f"{run.kind}  ·  {run.timestamp_label}  ·  {count}", id=run.dir_name))
        if self._runs:
            rows.highlighted = 0
        self._apply_list_chrome()

    def _focus_list(self) -> None:
        if self._view == "list" and self._runs:
            self.query_one("#hist-rows", OptionList).focus()
        else:
            self.focus()

    @on(OptionList.OptionSelected, "#hist-rows")
    def on_run_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        run = next((item for item in self._runs if item.dir_name == event.option.id), None)
        if run is not None:
            self.open_run(run)

    def back_to_list(self) -> None:
        self._view = "list"
        self.query_one("#hist-switcher", ContentSwitcher).current = "hist-list"
        self.reload()
        self._focus_list()

    def back_to_list_from_error(self) -> None:
        self._view = "list"
        self.query_one("#hist-switcher", ContentSwitcher).current = "hist-list"
        self._apply_list_chrome()
        self._focus_list()

    def action_reload(self) -> None:
        if self._view == "list":
            self.reload()

    def action_error_back(self) -> None:
        if self._view == "error":
            self.back_to_list_from_error()

    @on(Button.Pressed, "#hist-back")
    def on_back_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.back_to_list_from_error()

    def open_run(self, run: ArchivedRunSummary) -> None:
        self._view = "loading"
        switcher = self.query_one("#hist-switcher", ContentSwitcher)
        switcher.current = "hist-loading"
        self.query_one("#hist-loading-msg", Static).update(f"Loading {run.dir_name}…")
        try:
            archived = read_archived_run(run.path)
        except OSError as err:
            self._view = "error"
            switcher.current = "hist-error"
            self.query_one("#hist-error-msg", Static).update(str(err) or repr(err))
            self.focus()
            return
        self._view = "detail"
        switcher.current = "hist-detail"
        browser = self.query_one("#hist-result-browser", ResultBrowser)
        browser.sync(
            mode=archived.kind, plan_path=None, archive_path=str(run.path),
            plan=archived.plan, proposals=archived.proposals,
            title=f"Archived · {archived.kind} · {run.timestamp_label}", on_exit=True,
        )
        browser.focus()

    def _apply_list_chrome(self) -> None:
        n = len(self._runs)
        suffix = f" · {n} run{'s' if n != 1 else ''}" if n else ""
        self.query_one("#hist-subtitle", Static).update(f"Archived runs in {ARCHIVE_DIR}/{suffix}")
        loading = self.query_one("#hist-loading-indicator", LoadingIndicator)
        empty = self.query_one("#hist-empty", Static)
        error = self.query_one("#hist-list-error", Static)
        rows = self.query_one("#hist-rows", OptionList)
        loading.set_class(not self._loading_list, "-hidden")
        empty.set_class(self._loading_list or bool(self._list_error) or n > 0, "-hidden")
        error.set_class(self._loading_list or not self._list_error, "-hidden")
        rows.set_class(self._loading_list or bool(self._list_error) or n == 0, "-hidden")
        if self._list_error:
            error.update(self._list_error)
