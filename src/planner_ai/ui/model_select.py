from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Button,
    Input,
    LoadingIndicator,
    OptionList,
    SelectionList,
    Static,
)
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

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


def option_id_for_key(key: str) -> str:
    return key.replace(":", "--", 1)


def key_from_option_id(option_id: str) -> str:
    return option_id.replace("--", ":", 1)


def provider_source_label(provider: ProviderKind) -> str:
    return "claude" if provider == "anthropic" else provider


def choice_matches_query(choice: ModelChoice, query: str) -> bool:
    query = query.strip().lower()
    if not query:
        return True
    haystack = " ".join(
        (
            choice["label"],
            choice["modelId"],
            choice["provider"],
            provider_source_label(choice["provider"]),
        )
    ).lower()
    return query in haystack


def build_display_rows(filtered: list[ModelChoice]) -> list[DisplayRow]:
    rows: list[DisplayRow] = []
    choice_index = 0
    for provider in PROVIDER_ORDER:
        choices = [choice for choice in filtered if choice["provider"] == provider]
        if not choices:
            continue
        rows.append(
            {
                "kind": "header",
                "provider": provider,
                "label": PROVIDER_HEADERS[provider],
            }
        )
        for choice in choices:
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
    for index, row in enumerate(rows):
        if row["kind"] == "choice":
            return index
    return 0


def next_choice_row_index(
    rows: list[DisplayRow],
    from_index: int,
    direction: Literal[1, -1],
) -> int:
    index = from_index + direction
    while 0 <= index < len(rows):
        if rows[index]["kind"] == "choice":
            return index
        index += direction
    return from_index


def snap_to_choice_row(rows: list[DisplayRow], index: int) -> int:
    if not rows:
        return 0
    index = max(0, min(index, len(rows) - 1))
    if rows[index]["kind"] == "choice":
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
    if any(pick_key(item) == key for item in proposers):
        return [item for item in proposers if pick_key(item) != key]
    return [*proposers, pick]


class FilterInput(Input):
    BINDINGS = [Binding("escape", "filter_escape", show=False, priority=True)]

    def action_filter_escape(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, ModelSelect):
                parent.action_clear_filter()
                if not parent.filtering:
                    parent.focus_list()
                return
            parent = parent.parent


class ModelSelect(Widget):
    DEFAULT_CSS = """
    ModelSelect { height: 1fr; layout: vertical; }
    ModelSelect #ms-title { text-style: bold; height: 1; }
    ModelSelect #ms-help,
    ModelSelect #ms-empty,
    ModelSelect #ms-filter-hint { color: #888888; height: auto; }
    ModelSelect #ms-filter-row { height: 1; layout: horizontal; }
    ModelSelect #ms-filter-prefix { color: #888888; width: 2; height: 1; }
    ModelSelect #ms-filter-input { width: 1fr; height: 1; }
    ModelSelect #ms-filter-input.-hidden,
    ModelSelect #ms-filter-hint.-hidden,
    ModelSelect #ms-list.-hidden,
    ModelSelect #ms-empty.-hidden,
    ModelSelect #ms-loading.-hidden,
    ModelSelect #ms-continue.-hidden { display: none; }
    ModelSelect #ms-list { height: 1fr; margin: 1 0; }
    ModelSelect #ms-loading { height: 3; color: #888888; }
    ModelSelect #ms-continue { width: 100%; }
    """

    BINDINGS = [
        Binding("slash", "start_filter", "Filter", key_display="/"),
        Binding("escape", "clear_filter", "Clear filter"),
        Binding("m", "toggle_mocks", "Toggle mocks"),
        Binding("c", "continue", "Continue"),
    ]

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
        self.mode = mode
        self._choices: list[ModelChoice] = []
        self._selection: ModelSelection | None = None
        self._include_mocks = False
        self._loading = False
        self._display_rows: list[DisplayRow] = []
        self._syncing_list = False

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
        yield LoadingIndicator(id="ms-loading")
        yield Static("No models available.", id="ms-empty", classes="-hidden")
        if self.mode == "proposers":
            yield SelectionList(id="ms-list", classes="-hidden")
        else:
            yield OptionList(id="ms-list", classes="-hidden")
        yield Button(
            "Continue",
            id="ms-continue",
            variant="primary",
            classes="-hidden",
        )

    def sync(
        self,
        *,
        choices: list[ModelChoice],
        selection: ModelSelection | None,
        include_mocks: bool,
        loading: bool,
    ) -> None:
        self._choices = list(choices)
        self._selection = selection
        self._include_mocks = include_mocks
        self._loading = loading
        self._rebuild()

    def _filtered_choices(self) -> list[ModelChoice]:
        return [
            choice
            for choice in self._choices
            if choice_matches_query(choice, self.filter_query)
        ]

    def _can_continue(self) -> bool:
        return (
            self._selection is not None
            and bool(self._selection["proposers"])
            and bool(self._selection.get("consensus"))
        )

    def _rebuild(self) -> None:
        self._display_rows = build_display_rows(self._filtered_choices())
        loading = self.query_one("#ms-loading", LoadingIndicator)
        empty = self.query_one("#ms-empty", Static)
        list_widget = self.query_one("#ms-list", OptionList)
        button = self.query_one("#ms-continue", Button)
        loading.set_class(not self._loading, "-hidden")
        no_models = not self._loading and (
            self._selection is None or not self._display_rows
        )
        empty.set_class(not no_models, "-hidden")
        empty.update(
            "(no matches)"
            if self._selection is not None and self._choices
            else "No models available."
        )
        show_list = not self._loading and self._selection is not None and bool(
            self._display_rows
        )
        list_widget.set_class(not show_list, "-hidden")
        button.set_class(self._loading or self._selection is None, "-hidden")
        self._sync_list_options()
        self._update_chrome()
        self._update_continue()
        self._update_filter_ui()

    def _sync_list_options(self) -> None:
        widget = self.query_one("#ms-list", OptionList)
        self._syncing_list = True
        try:
            widget.clear_options()
            proposer_keys = self._proposer_keys()
            consensus_key = (
                pick_key(self._selection["consensus"])
                if self._selection is not None
                else ""
            )
            for row in self._display_rows:
                if row["kind"] == "header":
                    if isinstance(widget, SelectionList):
                        widget.add_option(
                            Selection(
                                f"── {row['label']} ──",
                                f"header:{row['provider']}",
                                disabled=True,
                            )
                        )
                    else:
                        widget.add_option(
                            Option(f"── {row['label']} ──", disabled=True)
                        )
                    continue
                choice = row["choice"]
                key = pick_key(choice)
                option_id = option_id_for_key(key)
                if isinstance(widget, SelectionList):
                    widget.add_option(
                        Selection(
                            format_choice_label(choice),
                            key,
                            key in proposer_keys,
                            id=option_id,
                        )
                    )
                else:
                    widget.add_option(
                        Option(format_choice_label(choice), id=option_id)
                    )
                    if key == consensus_key:
                        widget.highlighted = widget.option_count - 1
        finally:
            self._syncing_list = False

    def _proposer_keys(self) -> set[str]:
        if self._selection is None:
            return set()
        return {pick_key(pick) for pick in self._selection["proposers"]}

    def _update_chrome(self) -> None:
        title = self.query_one("#ms-title", Static)
        help_widget = self.query_one("#ms-help", Static)
        mocks = "mocks on" if self._include_mocks else "mocks off"
        if self.mode == "proposers":
            count = len(self._selection["proposers"]) if self._selection else 0
            title.update(f"Proposers ({count} selected)")
            help_widget.update(f"Multi-select — Space/click to toggle · {mocks}")
        else:
            label = "—"
            if self._selection is not None:
                key = pick_key(self._selection["consensus"])
                choice = next(
                    (item for item in self._choices if pick_key(item) == key),
                    None,
                )
                label = format_choice_label(choice) if choice else key
            title.update(f"Consensus ({label})")
            help_widget.update(f"Single-select — Enter/click to choose · {mocks}")

    def _update_continue(self) -> None:
        button = self.query_one("#ms-continue", Button)
        button.disabled = not self._can_continue()
        if self._selection is None or not self._selection["proposers"]:
            button.label = "Continue (select ≥1 proposer)"
        elif not self._selection.get("consensus"):
            button.label = "Continue (pick consensus)"
        else:
            button.label = "Continue"

    def _update_filter_ui(self) -> None:
        input_widget = self.query_one("#ms-filter-input", FilterInput)
        hint = self.query_one("#ms-filter-hint", Static)
        input_widget.set_class(not self.filtering, "-hidden")
        hint.set_class(self.filtering, "-hidden")
        if self.filtering:
            if input_widget.value != self.filter_query:
                input_widget.value = self.filter_query
            input_widget.focus()
        else:
            hint.update(self.filter_query or "press / to filter")

    def focus_list(self) -> None:
        if (
            not self._loading
            and self._selection is not None
            and self._display_rows
        ):
            self.query_one("#ms-list", OptionList).focus()
        else:
            self.focus()

    def watch_filtering(self, _value: bool) -> None:
        self._update_filter_ui()

    def watch_filter_query(self, _value: str) -> None:
        self._rebuild()

    def _notify_change(self, selection: ModelSelection) -> None:
        self._selection = selection
        self.planner_app.on_draft_selection_change(selection)

    def activate_choice(self, row_index: int) -> None:
        if self._selection is None or not 0 <= row_index < len(self._display_rows):
            return
        row = self._display_rows[row_index]
        if row["kind"] != "choice":
            return
        choice = row["choice"]
        pick: ModelPick = {
            "provider": choice["provider"],
            "modelId": choice["modelId"],
        }
        if self.mode == "proposers":
            self._notify_change(
                {
                    "proposers": toggle_proposer(
                        self._selection["proposers"], pick
                    ),
                    "consensus": self._selection["consensus"],
                }
            )
        else:
            self._notify_change(
                {"proposers": self._selection["proposers"], "consensus": pick}
            )

    @on(SelectionList.SelectedChanged, "#ms-list")
    def on_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        if self._syncing_list or self.mode != "proposers" or self._selection is None:
            return
        choices = {pick_key(choice): choice for choice in self._choices}
        proposers: list[ModelPick] = []
        for key in event.selection_list.selected:
            choice = choices.get(key)
            if choice is not None:
                proposers.append(
                    {
                        "provider": choice["provider"],
                        "modelId": choice["modelId"],
                    }
                )
        if {pick_key(pick) for pick in proposers} == self._proposer_keys():
            return
        self._notify_change(
            {"proposers": proposers, "consensus": self._selection["consensus"]}
        )

    @on(OptionList.OptionSelected, "#ms-list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if isinstance(event.option_list, SelectionList):
            return
        if self.mode != "consensus" or event.option.id is None:
            return
        key = key_from_option_id(event.option.id)
        row_index = next(
            (
                index
                for index, row in enumerate(self._display_rows)
                if row["kind"] == "choice" and pick_key(row["choice"]) == key
            ),
            -1,
        )
        self.activate_choice(row_index)

    @on(Button.Pressed, "#ms-continue")
    def on_continue_pressed(self, event: Button.Pressed) -> None:
        event.stop()
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
        if not self.filtering:
            self.filtering = True

    def action_clear_filter(self) -> None:
        if self.filter_query:
            self.filter_query = ""
        elif self.filtering:
            self.filtering = False
            self.focus_list()

    def action_toggle_mocks(self) -> None:
        if not self.filtering:
            self.app.run_worker(
                self.planner_app.on_toggle_include_mocks(),
                exclusive=True,
                name="toggle-mocks",
            )

    def action_continue(self) -> None:
        if not self.filtering:
            self._submit()

    @on(Input.Changed, "#ms-filter-input")
    def on_filter_changed(self, event: Input.Changed) -> None:
        self.filter_query = event.value

    @on(Input.Submitted, "#ms-filter-input")
    def on_filter_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.filtering = False
        self.focus_list()
