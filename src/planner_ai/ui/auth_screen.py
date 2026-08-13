from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Click
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Static

from planner_ai.config import AppConfig, ConfigCredentialKey
from planner_ai.ui.token_input import TokenInput

if TYPE_CHECKING:
    from planner_ai.app import PlannerApp

AuthMode = Literal["overview", "claude", "cursor", "codex"]

ALL_CREDENTIAL_KEYS: list[ConfigCredentialKey] = [
    "claudeCodeOAuthToken",
    "cursorApiKey",
    "codexApiKey",
]


def status_line(label: str, is_set: bool) -> str:
    return f"{label}: {'set' if is_set else 'missing'}"


class AuthActionRow(Static):
    """Clickable overview action row."""

    def __init__(
        self,
        index: int,
        label: str,
        *,
        disabled: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(f"  {label}", id=id)
        self.row_index = index
        self.action_label = label
        self.action_disabled = disabled

    def on_click(self) -> None:
        parent = self.parent
        while parent is not None:
            if isinstance(parent, AuthScreen):
                parent.on_action_click(self.row_index)
                return
            parent = parent.parent


class AuthScreen(Widget):
    """Auth overview + nested masked token editors."""

    DEFAULT_CSS = """
    AuthScreen {
        height: 1fr;
        layout: vertical;
    }

    AuthScreen #auth-switcher {
        height: 1fr;
    }

    AuthScreen #overview,
    AuthScreen #editor {
        height: auto;
        layout: vertical;
    }

    AuthScreen #auth-title {
        text-style: bold;
        height: 1;
    }

    AuthScreen #auth-hint,
    AuthScreen #auth-footer,
    AuthScreen #auth-back {
        color: #888888;
        height: auto;
    }

    AuthScreen #auth-back {
        margin-top: 1;
    }

    AuthScreen .status-set {
        color: green;
        height: 1;
    }

    AuthScreen .status-missing {
        color: yellow;
        height: 1;
    }

    AuthScreen #auth-actions {
        height: auto;
        layout: vertical;
        margin-top: 1;
        margin-bottom: 1;
    }

    AuthScreen AuthActionRow {
        height: 1;
        width: 100%;
    }

    AuthScreen AuthActionRow.-focused {
        color: black;
        background: cyan;
    }

    AuthScreen AuthActionRow.-disabled {
        color: #888888;
    }

    AuthScreen AuthActionRow.-focused.-disabled {
        color: #888888;
        background: transparent;
    }
    """

    BINDINGS = [
        Binding("up", "move_up", show=False),
        Binding("down", "move_down", show=False),
        Binding("enter", "activate", show=False),
        Binding("space", "activate", show=False),
    ]

    can_focus = True
    cursor: reactive[int] = reactive(0)
    mode: reactive[AuthMode] = reactive("overview")

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._config: AppConfig = {}

    @property
    def planner_app(self) -> PlannerApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        with ContentSwitcher(id="auth-switcher", initial="overview"):
            with Vertical(id="overview"):
                yield Static("Auth", id="auth-title")
                yield Static(
                    "Tokens are stored in your local planner-ai config.",
                    id="auth-hint",
                )
                yield Static("", id="status-claude", classes="status-missing")
                yield Static("", id="status-cursor", classes="status-missing")
                yield Static("", id="status-codex", classes="status-missing")
                with Vertical(id="auth-actions"):
                    for i in range(7):
                        yield AuthActionRow(i, "", id=f"auth-action-{i}")
                yield Static(
                    "↑↓ move · Enter/Space activate · Ctrl+1–5 switch tabs",
                    id="auth-footer",
                )
            with Vertical(id="editor"):
                yield TokenInput(id="auth-token-input")
                yield Static("← Back to Auth overview", id="auth-back")

    def on_mount(self) -> None:
        self.sync_config(self._config)

    def sync_config(self, config: AppConfig) -> None:
        self._config = config
        has_claude = bool(config.get("claudeCodeOAuthToken"))
        has_cursor = bool(config.get("cursorApiKey"))
        has_codex = bool(config.get("codexApiKey"))

        self._set_status("status-claude", "Claude OAuth", has_claude)
        self._set_status("status-cursor", "Cursor API key", has_cursor)
        self._set_status("status-codex", "Codex API key", has_codex)

        labels = [
            (
                "Edit Claude OAuth token"
                if has_claude
                else "Set Claude OAuth token",
                False,
            ),
            (
                "Edit Cursor API key" if has_cursor else "Set Cursor API key",
                False,
            ),
            (
                "Edit Codex API key" if has_codex else "Set Codex API key",
                False,
            ),
            ("Clear Claude token", not has_claude),
            ("Clear Cursor key", not has_cursor),
            ("Clear Codex key", not has_codex),
            (
                "Clear all credentials",
                not (has_claude or has_cursor or has_codex),
            ),
        ]
        for i, (label, disabled) in enumerate(labels):
            row = self.query_one(f"#auth-action-{i}", AuthActionRow)
            row.action_label = label
            row.action_disabled = disabled
            row.set_class(disabled, "-disabled")
        self._refresh_action_styles()

    def _set_status(self, widget_id: str, label: str, is_set: bool) -> None:
        widget = self.query_one(f"#{widget_id}", Static)
        widget.update(status_line(label, is_set))
        widget.set_class(is_set, "status-set")
        widget.set_class(not is_set, "status-missing")

    def watch_cursor(self, _cursor: int) -> None:
        self._refresh_action_styles()

    def watch_mode(self, mode: AuthMode) -> None:
        switcher = self.query_one("#auth-switcher", ContentSwitcher)
        if mode == "overview":
            switcher.current = "overview"
            self._refresh_action_styles()
            self.focus()
        else:
            switcher.current = "editor"
            self._configure_editor(mode)

    def _configure_editor(self, mode: AuthMode) -> None:
        if mode == "claude":
            label = "Claude Code OAuth token"
            hint = "Run `claude setup-token`, then paste. Enter empty to cancel."
        elif mode == "cursor":
            label = "Cursor API key"
            hint = (
                "From Cursor Dashboard → Integrations. Enter empty to cancel."
            )
        else:
            label = "Codex API key"
            hint = "From platform.openai.com/api-keys. Enter empty to cancel."

        self.query_one("#auth-token-input", TokenInput).configure(
            label,
            hint,
            self._on_token_submit,
        )

    def _refresh_action_styles(self) -> None:
        if self.mode != "overview":
            return
        try:
            actions = self.query_one("#auth-actions")
        except Exception:
            return
        for i in range(7):
            row = actions.query_one(f"#auth-action-{i}", AuthActionRow)
            focused = self.cursor == i
            prefix = "> " if focused else "  "
            row.update(f"{prefix}{row.action_label}")
            row.set_class(focused, "-focused")
            row.set_class(row.action_disabled, "-disabled")

    def action_move_up(self) -> None:
        if self.mode != "overview":
            return
        self.cursor = max(0, self.cursor - 1)

    def action_move_down(self) -> None:
        if self.mode != "overview":
            return
        self.cursor = min(6, self.cursor + 1)

    def action_activate(self) -> None:
        if self.mode != "overview":
            return
        self._run_action(self.cursor)

    def on_action_click(self, index: int) -> None:
        self.cursor = index
        row = self.query_one(f"#auth-action-{index}", AuthActionRow)
        if not row.action_disabled:
            self._run_action(index)

    def _run_action(self, index: int) -> None:
        row = self.query_one(f"#auth-action-{index}", AuthActionRow)
        if row.action_disabled:
            return
        match index:
            case 0:
                self.mode = "claude"
            case 1:
                self.mode = "cursor"
            case 2:
                self.mode = "codex"
            case 3:
                self._clear(["claudeCodeOAuthToken"])
            case 4:
                self._clear(["cursorApiKey"])
            case 5:
                self._clear(["codexApiKey"])
            case 6:
                self._clear(list(ALL_CREDENTIAL_KEYS))

    def _clear(self, keys: list[ConfigCredentialKey]) -> None:
        self.app.run_worker(
            self.planner_app.on_clear_credentials(keys),
            exclusive=True,
            name="auth-clear",
        )

    def _on_token_submit(self, value: str) -> None:
        mode = self.mode
        self.mode = "overview"
        if not value:
            return
        app = self.planner_app
        if mode == "claude":
            coro = app.on_save_claude(value)
        elif mode == "cursor":
            coro = app.on_save_cursor(value)
        elif mode == "codex":
            coro = app.on_save_codex(value)
        else:
            return
        self.app.run_worker(coro, exclusive=True, name="auth-save")

    @on(Click, "#auth-back")
    def on_back_click(self, event: Click) -> None:
        event.stop()
        self.mode = "overview"
