from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

from planner_ai.providers.models import (
    ModelChoice,
    ModelPick,
    ModelSelection,
    ProviderKind,
    format_choice_label,
)

if TYPE_CHECKING:
    from planner_ai.app import PlannerApp

ModelSelectMode = Literal["proposers", "consensus"]

PROVIDER_ORDER: list[ProviderKind] = ["anthropic", "cursor", "codex", "mock"]

PROVIDER_HEADERS: dict[ProviderKind, str] = {
    "anthropic": "Claude",
    "cursor": "Cursor",
    "codex": "Codex",
    "mock": "Mock",
}


class HeaderRow(TypedDict):
    kind: Literal["header"]
    provider: ProviderKind
    label: str


class ChoiceRow(TypedDict):
    kind: Literal["choice"]
    choice: ModelChoice
    choiceIndex: int


DisplayRow = HeaderRow | ChoiceRow


def pick_key(pick: ModelPick | ModelChoice) -> str:
    return f"{pick['provider']}:{pick['modelId']}"


def provider_source_label(provider: ProviderKind) -> str:
    if provider == "anthropic":
        return "claude"
    return provider


def choice_matches_query(choice: ModelChoice, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    haystack = " ".join(
        [
            choice["label"],
            choice["modelId"],
            choice["provider"],
            provider_source_label(choice["provider"]),
        ]
    ).lower()
    return q in haystack


def build_display_rows(filtered: list[ModelChoice]) -> list[DisplayRow]:
    rows: list[DisplayRow] = []
    choice_index = 0
    for provider in PROVIDER_ORDER:
        group = [c for c in filtered if c["provider"] == provider]
        if not group:
            continue
        rows.append(
            {
                "kind": "header",
                "provider": provider,
                "label": PROVIDER_HEADERS[provider],
            }
        )
        for choice in group:
            rows.append(
                {
                    "kind": "choice",
                    "choice": choice,
                    "choiceIndex": choice_index,
                }
            )
            choice_index += 1
    return rows


def first_choice_row_index(rows: list[DisplayRow]) -> int:
    for i, row in enumerate(rows):
        if row["kind"] == "choice":
            return i
    return 0


def next_choice_row_index(
    rows: list[DisplayRow],
    from_index: int,
    direction: Literal[1, -1],
) -> int:
    i = from_index + direction
    while 0 <= i < len(rows):
        if rows[i]["kind"] == "choice":
            return i
        i += direction
    return from_index


def snap_to_choice_row(rows: list[DisplayRow], index: int) -> int:
    if not rows:
        return 0
    index = max(0, min(index, len(rows) - 1))
    row = rows[index]
    if row["kind"] == "choice":
        return index
    forward = next_choice_row_index(rows, index - 1, 1)
    if rows[forward]["kind"] == "choice":
        return forward
    return next_choice_row_index(rows, index + 1, -1)


def toggle_proposer(
    proposers: list[ModelPick],
    pick: ModelPick,
) -> list[ModelPick]:
    key = pick_key(pick)
    if any(pick_key(p) == key for p in proposers):
        return [p for p in proposers if pick_key(p) != key]
    return [*proposers, pick]


class ModelHeaderRow(Static):
    """Non-interactive provider group header."""

    def __init__(
        self,
        label: str,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(f"  ── {label} ──", name=name, id=id, classes=classes)
        self.can_focus = False


class ModelChoiceRow(Static):
    """Clickable model choice row."""

    def __init__(
        self,
        row_index: int,
        choice: ModelChoice,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__("", name=name, id=id, classes=classes)
        self.row_index = row_index
        self.choice = choice
        self.can_focus = False

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, ModelSelect):
                parent.on_choice_click(self.row_index)
                return
            parent = parent.parent


class ContinueRow(Static):
    """Clickable Continue action."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__("", name=name, id=id, classes=classes)
        self.can_focus = False

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, ModelSelect):
                parent.on_continue_click()
                return
            parent = parent.parent


class FilterInput(Input):
    """Filter field that forwards Esc to ModelSelect."""

    BINDINGS = [
        Binding("escape", "filter_escape", show=False, priority=True),
    ]

    def action_filter_escape(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, ModelSelect):
                parent.action_clear_filter()
                if not parent.filtering:
                    parent.focus()
                return
            parent = parent.parent


class ModelSelect(Widget):
    """Proposers (multi) / Consensus (single) model picker."""

    DEFAULT_CSS = """
    ModelSelect {
        height: 1fr;
        layout: vertical;
    }

    ModelSelect #ms-title {
        text-style: bold;
        height: 1;
    }

    ModelSelect #ms-help,
    ModelSelect #ms-footer,
    ModelSelect #ms-empty,
    ModelSelect #ms-filter-hint {
        color: #888888;
        height: auto;
    }

    ModelSelect #ms-filter-row {
        height: 1;
        layout: horizontal;
    }

    ModelSelect #ms-filter-prefix {
        color: #888888;
        width: 2;
        height: 1;
    }

    ModelSelect #ms-filter-input {
        width: 1fr;
        height: 1;
    }

    ModelSelect #ms-filter-input.-hidden,
    ModelSelect #ms-filter-hint.-hidden,
    ModelSelect #ms-list.-hidden,
    ModelSelect #ms-empty.-hidden,
    ModelSelect #ms-continue.-hidden,
    ModelSelect #ms-footer.-hidden {
        display: none;
    }

    ModelSelect #ms-list {
        height: 1fr;
        layout: vertical;
        margin-top: 1;
        margin-bottom: 1;
    }

    ModelSelect ModelHeaderRow {
        height: 1;
        width: 100%;
        color: #888888;
    }

    ModelSelect ModelChoiceRow {
        height: 1;
        width: 100%;
    }

    ModelSelect ModelChoiceRow.-focused {
        color: black;
        background: cyan;
    }

    ModelSelect ModelChoiceRow.-selected {
        color: green;
    }

    ModelSelect ModelChoiceRow.-focused.-selected {
        color: black;
        background: cyan;
    }

    ModelSelect #ms-continue {
        height: 1;
        width: 100%;
        text-style: bold;
    }

    ModelSelect #ms-continue.-focused {
        color: black;
        background: cyan;
    }

    ModelSelect #ms-continue.-disabled {
        color: #888888;
        text-style: none;
    }

    ModelSelect #ms-continue.-focused.-disabled {
        color: #888888;
        background: transparent;
        text-style: none;
    }
    """

    BINDINGS = [
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("pageup", "page_up", show=False),
        Binding("pagedown", "page_down", show=False),
        Binding("enter", "activate", show=False),
        Binding("space", "activate", show=False),
        Binding("slash", "start_filter", show=False),
        Binding("escape", "clear_filter", show=False),
        Binding("m", "toggle_mocks", show=False),
        Binding("c", "continue", show=False),
    ]

    can_focus = True
    cursor: reactive[int] = reactive(0)
    continue_focused: reactive[bool] = reactive(False)
    filtering: reactive[bool] = reactive(False)
    filter_query: reactive[str] = reactive("")

    def __init__(
        self,
        mode: ModelSelectMode,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.mode: ModelSelectMode = mode
        self._choices: list[ModelChoice] = []
        self._selection: ModelSelection | None = None
        self._include_mocks = False
        self._loading = False
        self._display_rows: list[DisplayRow] = []
        self._remount_token = 0

    @property
    def planner_app(self) -> PlannerApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        yield Static("", id="ms-title")
        yield Static("", id="ms-help")
        with Vertical(id="ms-filter-row"):
            yield Static("/ ", id="ms-filter-prefix")
            yield FilterInput(
                placeholder="filter models…",
                id="ms-filter-input",
                classes="-hidden",
            )
            yield Static("press / to filter", id="ms-filter-hint")
        yield Static("Loading models…", id="ms-empty")
        with VerticalScroll(id="ms-list", classes="-hidden"):
            pass
        yield ContinueRow(id="ms-continue", classes="-hidden")
        yield Static("", id="ms-footer", classes="-hidden")

    def sync(
        self,
        *,
        choices: list[ModelChoice],
        selection: ModelSelection | None,
        include_mocks: bool,
        loading: bool,
    ) -> None:
        choices_changed = self._choices != choices
        loading_changed = self._loading != loading
        self._choices = list(choices)
        self._selection = selection
        self._include_mocks = include_mocks
        self._loading = loading

        if loading_changed or choices_changed or selection is None or loading:
            self._rebuild()
        else:
            # Same catalog — refresh marks / chrome only (draft toggles).
            self._refresh_row_styles()
            self._update_chrome()
            self._update_continue()
            self._update_filter_ui()

    def _filtered_choices(self) -> list[ModelChoice]:
        return [
            c for c in self._choices if choice_matches_query(c, self.filter_query)
        ]

    def _can_continue(self) -> bool:
        if self._selection is None:
            return False
        return len(self._selection["proposers"]) > 0 and bool(
            self._selection.get("consensus")
        )

    def _list_height(self) -> int:
        try:
            return max(5, self.size.height - 8)
        except Exception:
            return 10

    def _rebuild(self) -> None:
        empty = self.query_one("#ms-empty", Static)
        list_widget = self.query_one("#ms-list", VerticalScroll)
        continue_row = self.query_one("#ms-continue", ContinueRow)
        footer = self.query_one("#ms-footer", Static)

        if self._loading:
            empty.update("Loading models…")
            empty.remove_class("-hidden")
            list_widget.add_class("-hidden")
            continue_row.add_class("-hidden")
            footer.add_class("-hidden")
            self._update_chrome()
            return

        if self._selection is None:
            empty.update("No models available.")
            empty.remove_class("-hidden")
            list_widget.add_class("-hidden")
            continue_row.add_class("-hidden")
            footer.add_class("-hidden")
            self._update_chrome()
            return

        empty.add_class("-hidden")
        list_widget.remove_class("-hidden")
        continue_row.remove_class("-hidden")
        footer.remove_class("-hidden")

        filtered = self._filtered_choices()
        self._display_rows = build_display_rows(filtered)

        # Clamp / reset cursor when rows change
        if not self._display_rows:
            self.cursor = 0
            self.continue_focused = False
        elif self.continue_focused:
            pass
        else:
            if (
                self.cursor >= len(self._display_rows)
                or self._display_rows[self.cursor]["kind"] != "choice"
            ):
                self.cursor = first_choice_row_index(self._display_rows)

        self._remount_token += 1
        token = self._remount_token
        self.run_worker(
            self._remount_list(token),
            exclusive=True,
            name=f"ms-remount-{self.mode}",
        )
        self._update_chrome()
        self._update_continue()
        self._update_filter_ui()

    async def _remount_list(self, token: int) -> None:
        list_widget = self.query_one("#ms-list", VerticalScroll)
        await list_widget.remove_children()
        if token != self._remount_token:
            return

        if not self._display_rows:
            await list_widget.mount(Static("(no matches)"))
            return

        widgets: list[Widget] = []
        for i, row in enumerate(self._display_rows):
            if row["kind"] == "header":
                widgets.append(ModelHeaderRow(row["label"]))
            else:
                widgets.append(ModelChoiceRow(i, row["choice"]))
        await list_widget.mount(*widgets)
        if token != self._remount_token:
            return
        self._refresh_row_styles()

    def _update_chrome(self) -> None:
        title = self.query_one("#ms-title", Static)
        help_w = self.query_one("#ms-help", Static)
        footer = self.query_one("#ms-footer", Static)

        scroll_hint = ""
        list_height = self._list_height()
        n = len(self._display_rows)
        if n > list_height and not self._loading and self._selection is not None:
            start = max(0, self.cursor - list_height // 2)
            end = min(n, start + list_height)
            scroll_hint = f" · showing {start + 1}–{end} of {n}"

        if self.mode == "proposers":
            count = (
                len(self._selection["proposers"]) if self._selection is not None else 0
            )
            title.update(f"Proposers ({count} selected){scroll_hint}")
            help_w.update("Multi-select — Space/click to toggle")
        else:
            if self._selection is not None:
                consensus = self._selection["consensus"]
                found = next(
                    (
                        c
                        for c in self._choices
                        if c["provider"] == consensus["provider"]
                        and c["modelId"] == consensus["modelId"]
                    ),
                    None,
                )
                label = (
                    format_choice_label(found)
                    if found is not None
                    else f"{consensus['provider']}:{consensus['modelId']}"
                )
            else:
                label = "—"
            title.update(f"Consensus ({label}){scroll_hint}")
            help_w.update("Single-select — Space/click to choose")

        mocks_hint = "mocks on" if self._include_mocks else "mocks off"
        footer.update(
            f"↑↓ scroll · / filter · m {mocks_hint} · Esc clear · c continue"
        )

    def _update_continue(self) -> None:
        row = self.query_one("#ms-continue", ContinueRow)
        can = self._can_continue()
        pointer = "> " if self.continue_focused else "  "
        if can:
            text = f"{pointer}[ Continue ]"
        elif self._selection is None or len(self._selection["proposers"]) == 0:
            text = f"{pointer}[ Continue ] (select ≥1 proposer)"
        else:
            text = f"{pointer}[ Continue ] (pick consensus)"
        row.update(text)
        row.set_class(self.continue_focused, "-focused")
        row.set_class(not can, "-disabled")

    def _update_filter_ui(self) -> None:
        inp = self.query_one("#ms-filter-input", FilterInput)
        hint = self.query_one("#ms-filter-hint", Static)
        if self.filtering:
            inp.remove_class("-hidden")
            hint.add_class("-hidden")
            if inp.value != self.filter_query:
                inp.value = self.filter_query
            if not inp.has_focus:
                inp.focus()
        else:
            inp.add_class("-hidden")
            hint.remove_class("-hidden")
            if self.filter_query:
                hint.update(self.filter_query)
            else:
                hint.update("press / to filter")

    def _proposer_keys(self) -> set[str]:
        if self._selection is None:
            return set()
        return {pick_key(p) for p in self._selection["proposers"]}

    def _refresh_row_styles(self) -> None:
        if self._selection is None:
            return
        try:
            list_widget = self.query_one("#ms-list", VerticalScroll)
        except Exception:
            return

        proposer_keys = self._proposer_keys()
        consensus = self._selection["consensus"]
        consensus_key = pick_key(consensus)

        for child in list_widget.children:
            if not isinstance(child, ModelChoiceRow):
                continue
            index = child.row_index
            key = pick_key(child.choice)
            focused = not self.continue_focused and self.cursor == index
            if self.mode == "proposers":
                selected = key in proposer_keys
                mark = "[x]" if selected else "[ ]"
            else:
                selected = key == consensus_key
                mark = "(•)" if selected else "( )"
            pointer = ">" if focused else " "
            child.update(
                f"{pointer} {mark} {format_choice_label(child.choice)}"
            )
            child.set_class(focused, "-focused")
            child.set_class(selected and not focused, "-selected")

        if not self.continue_focused and self._display_rows:
            try:
                focused_row = list_widget.children[self.cursor]
                focused_row.scroll_visible(animate=False)
            except Exception:
                pass

    def watch_cursor(self, _cursor: int) -> None:
        self._refresh_row_styles()
        self._update_chrome()

    def watch_continue_focused(self, _value: bool) -> None:
        self._refresh_row_styles()
        self._update_continue()

    def watch_filtering(self, _value: bool) -> None:
        self._update_filter_ui()

    def watch_filter_query(self, _value: str) -> None:
        self.continue_focused = False
        self.cursor = first_choice_row_index(
            build_display_rows(self._filtered_choices())
        )
        self._rebuild()

    def _notify_change(self, next_selection: ModelSelection) -> None:
        self._selection = next_selection
        self.planner_app.on_draft_selection_change(next_selection)
        self._refresh_row_styles()
        self._update_chrome()
        self._update_continue()

    def activate_choice(self, row_index: int) -> None:
        if self._selection is None:
            return
        if row_index < 0 or row_index >= len(self._display_rows):
            return
        row = self._display_rows[row_index]
        if row["kind"] != "choice":
            return

        choice = row["choice"]
        pick: ModelPick = {
            "provider": choice["provider"],
            "modelId": choice["modelId"],
        }
        self.continue_focused = False
        self.cursor = row_index

        if self.mode == "proposers":
            next_proposers = toggle_proposer(self._selection["proposers"], pick)
            self._notify_change(
                {
                    "proposers": next_proposers,
                    "consensus": self._selection["consensus"],
                }
            )
        else:
            self._notify_change(
                {
                    "proposers": self._selection["proposers"],
                    "consensus": pick,
                }
            )

    def on_choice_click(self, row_index: int) -> None:
        self.activate_choice(row_index)

    def on_continue_click(self) -> None:
        self.filtering = False
        self.continue_focused = True
        self._submit()

    def _submit(self) -> None:
        if not self._can_continue() or self._selection is None:
            return
        self.app.run_worker(
            self.planner_app.on_model_selection(self._selection),
            exclusive=True,
            name="model-selection",
        )

    def action_start_filter(self) -> None:
        if self.filtering:
            return
        self.filtering = True
        self.continue_focused = False
        self._update_filter_ui()

    def action_clear_filter(self) -> None:
        if self.filter_query:
            self.filter_query = ""
            return
        if self.filtering:
            self.filtering = False
            self.focus()

    def action_toggle_mocks(self) -> None:
        if self.filtering:
            return
        self.app.run_worker(
            self.planner_app.on_toggle_include_mocks(),
            exclusive=True,
            name="toggle-mocks",
        )

    def action_continue(self) -> None:
        if self.filtering:
            return
        self._submit()

    def action_move_up(self) -> None:
        if self.filtering:
            return
        if self.continue_focused:
            self.continue_focused = False
            if self._display_rows:
                self.cursor = snap_to_choice_row(
                    self._display_rows, len(self._display_rows) - 1
                )
            return
        self.cursor = next_choice_row_index(self._display_rows, self.cursor, -1)

    def action_move_down(self) -> None:
        if self.filtering:
            return
        if self.continue_focused:
            return
        nxt = next_choice_row_index(self._display_rows, self.cursor, 1)
        if nxt == self.cursor and self._can_continue():
            self.filtering = False
            self.continue_focused = True
            return
        self.cursor = nxt

    def action_page_up(self) -> None:
        if self.filtering or self.continue_focused:
            return
        height = self._list_height()
        self.cursor = snap_to_choice_row(
            self._display_rows, max(0, self.cursor - height)
        )

    def action_page_down(self) -> None:
        if self.filtering or self.continue_focused:
            return
        height = self._list_height()
        max_index = max(0, len(self._display_rows) - 1)
        self.cursor = snap_to_choice_row(
            self._display_rows, min(max_index, self.cursor + height)
        )

    def action_activate(self) -> None:
        if self.filtering:
            return
        if self.continue_focused:
            self._submit()
            return
        self.activate_choice(self.cursor)

    @on(Input.Changed, "#ms-filter-input")
    def on_filter_changed(self, event: Input.Changed) -> None:
        self.filter_query = event.value

    @on(Input.Submitted, "#ms-filter-input")
    def on_filter_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.filtering = False
        self.focus()
