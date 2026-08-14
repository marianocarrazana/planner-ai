from __future__ import annotations

from typing import Literal

from textual.widgets import Tab, Tabs

AppTab = Literal["plan", "proposers", "consensus", "auth", "history"]

TABS: list[tuple[AppTab, str]] = [
    ("plan", "Plan"),
    ("proposers", "Proposers"),
    ("consensus", "Consensus"),
    ("auth", "Auth"),
    ("history", "History"),
]


def app_tab_widget_id(tab: AppTab) -> str:
    return f"tab-{tab}"


def parse_app_tab_id(widget_id: str | None) -> AppTab | None:
    if widget_id is None or not widget_id.startswith("tab-"):
        return None
    tab = widget_id.removeprefix("tab-")
    for tab_id, _ in TABS:
        if tab_id == tab:
            return tab_id
    return None


class AppTabs(Tabs):
    """Top-level app tabs using Textual's native Tabs chrome."""

    DEFAULT_CSS = """
    AppTabs {
        margin-top: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(
            *[Tab(label, id=app_tab_widget_id(tab_id)) for tab_id, label in TABS],
            active=app_tab_widget_id("plan"),
            id="app-tabs",
        )
