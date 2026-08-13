from __future__ import annotations

from typing import Literal

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

AppTab = Literal["plan", "proposers", "consensus", "auth", "history"]

TABS: list[tuple[AppTab, str]] = [
    ("plan", "Plan"),
    ("proposers", "Proposers"),
    ("consensus", "Consensus"),
    ("auth", "Auth"),
    ("history", "History"),
]


class TabSelected(Message):
    """Posted when the user clicks a tab label."""

    def __init__(self, tab: AppTab) -> None:
        self.tab = tab
        super().__init__()


class TabLabel(Static):
    """Clickable tab label."""

    def __init__(self, tab_id: AppTab, label: str) -> None:
        super().__init__(f" {label} ", id=f"tab-{tab_id}")
        self.tab_id = tab_id
        self.tab_label = label
        self.can_focus = False

    def on_click(self) -> None:
        self.post_message(TabSelected(self.tab_id))


class AppTabs(Widget):
    """Five top-level tab labels with cyan active styling."""

    DEFAULT_CSS = """
    AppTabs {
        height: auto;
        layout: vertical;
    }

    AppTabs #tab-row {
        height: 1;
        layout: horizontal;
    }

    AppTabs TabLabel {
        width: auto;
        height: 1;
        margin-right: 2;
        color: #888888;
    }

    AppTabs TabLabel.-active {
        color: black;
        background: cyan;
    }

    AppTabs #tab-underline {
        height: 1;
        color: cyan;
    }
    """

    active: reactive[AppTab] = reactive("plan")

    def compose(self):
        with Widget(id="tab-row"):
            for tab_id, label in TABS:
                yield TabLabel(tab_id, label)
        yield Label("", id="tab-underline")

    def watch_active(self, active: AppTab) -> None:
        self._refresh_styles(active)

    def on_mount(self) -> None:
        self._refresh_styles(self.active)

    def _refresh_styles(self, active: AppTab) -> None:
        for tab_id, _label in TABS:
            label = self.query_one(f"#tab-{tab_id}", TabLabel)
            label.set_class(tab_id == active, "-active")

        underline = self.query_one("#tab-underline", Label)
        parts: list[str] = []
        for i, (tab_id, label) in enumerate(TABS):
            if i > 0:
                parts.append("  ")
            width = len(label) + 2
            if tab_id == active:
                parts.append("▬" * width)
            else:
                parts.append(" " * width)
        underline.update("".join(parts))
