from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, ContentSwitcher, OptionList, Static
from textual.widgets.option_list import Option

from planner_ai.config import AppConfig, ConfigCredentialKey
from planner_ai.ui.token_input import TokenInput

if TYPE_CHECKING:
    from planner_ai.app import PlannerApp

AuthMode = Literal["overview", "claude", "cursor", "codex"]
ACTION_IDS = ("edit-claude", "edit-cursor", "edit-codex", "clear-claude", "clear-cursor", "clear-codex", "clear-all")
ALL_CREDENTIAL_KEYS: list[ConfigCredentialKey] = ["claudeCodeOAuthToken", "cursorApiKey", "codexApiKey"]


def status_line(label: str, is_set: bool) -> str:
    return f"{label}: {'set' if is_set else 'missing'}"


class AuthScreen(Widget):
    DEFAULT_CSS = """
    AuthScreen { height: 1fr; }
    AuthScreen #auth-switcher { height: 1fr; }
    AuthScreen #overview, AuthScreen #editor { height: auto; }
    AuthScreen #auth-title { text-style: bold; height: 1; }
    AuthScreen #auth-hint { color: #888888; height: auto; }
    AuthScreen #auth-back {
        color: #888888; background: transparent; border: none;
        width: auto; min-width: 0; height: 3; padding: 0; margin-top: 1;
    }
    AuthScreen .status-set { color: green; height: 1; }
    AuthScreen .status-missing { color: yellow; height: 1; }
    AuthScreen #auth-actions { height: auto; margin: 1 0; }
    """
    mode: reactive[AuthMode] = reactive("overview")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config: AppConfig = {}

    @property
    def planner_app(self) -> PlannerApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        with ContentSwitcher(id="auth-switcher", initial="overview"):
            with Vertical(id="overview"):
                yield Static("Auth", id="auth-title")
                yield Static("Tokens are stored in your local planner-ai config.", id="auth-hint")
                yield Static("", id="status-claude", classes="status-missing")
                yield Static("", id="status-cursor", classes="status-missing")
                yield Static("", id="status-codex", classes="status-missing")
                yield OptionList(id="auth-actions")
            with Vertical(id="editor"):
                yield TokenInput(id="auth-token-input")
                yield Button("← Back to Auth overview", id="auth-back", flat=True)

    def on_mount(self) -> None:
        self.sync_config(self._config)

    def sync_config(self, config: AppConfig) -> None:
        self._config = config
        present = [bool(config.get(key)) for key in ALL_CREDENTIAL_KEYS]
        self._set_status("status-claude", "Claude OAuth", present[0])
        self._set_status("status-cursor", "Cursor API key", present[1])
        self._set_status("status-codex", "Codex API key", present[2])
        labels = [
            f"{'Edit' if present[0] else 'Set'} Claude OAuth token",
            f"{'Edit' if present[1] else 'Set'} Cursor API key",
            f"{'Edit' if present[2] else 'Set'} Codex API key",
            "Clear Claude token", "Clear Cursor key", "Clear Codex key", "Clear all credentials",
        ]
        disabled = [False, False, False, not present[0], not present[1], not present[2], not any(present)]
        actions = self.query_one("#auth-actions", OptionList)
        current = actions.highlighted_option.id if actions.highlighted_option else None
        actions.clear_options()
        for action_id, label, off in zip(ACTION_IDS, labels, disabled, strict=True):
            actions.add_option(Option(label, id=action_id, disabled=off))
        if current:
            self.highlight_action(current)

    def _set_status(self, widget_id: str, label: str, is_set: bool) -> None:
        widget = self.query_one(f"#{widget_id}", Static)
        widget.update(status_line(label, is_set))
        widget.set_class(is_set, "status-set")
        widget.set_class(not is_set, "status-missing")

    def watch_mode(self, mode: AuthMode) -> None:
        switcher = self.query_one("#auth-switcher", ContentSwitcher)
        if mode == "overview":
            switcher.current = "overview"
            self.query_one("#auth-actions", OptionList).focus()
        else:
            switcher.current = "editor"
            self._configure_editor(mode)

    def _configure_editor(self, mode: AuthMode) -> None:
        if mode == "claude":
            label, hint = "Claude Code OAuth token", "Run `claude setup-token`, then paste. Enter empty to cancel."
        elif mode == "cursor":
            label, hint = "Cursor API key", "From Cursor Dashboard → Integrations. Enter empty to cancel."
        else:
            label, hint = "Codex API key", "From platform.openai.com/api-keys. Enter empty to cancel."
        self.query_one("#auth-token-input", TokenInput).configure(label, hint, self._on_token_submit)

    def highlight_action(self, action_id: str) -> None:
        if action_id in ACTION_IDS:
            self.query_one("#auth-actions", OptionList).highlighted = ACTION_IDS.index(action_id)

    def activate_highlighted(self) -> None:
        option = self.query_one("#auth-actions", OptionList).highlighted_option
        if option and not option.disabled and option.id:
            self._run_action(option.id)

    @on(OptionList.OptionSelected, "#auth-actions")
    def on_action_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self._run_action(event.option.id)

    def _run_action(self, action_id: str) -> None:
        if action_id.startswith("edit-"):
            self.mode = action_id.removeprefix("edit-")  # type: ignore[assignment]
            return
        keys: dict[str, list[ConfigCredentialKey]] = {
            "clear-claude": ["claudeCodeOAuthToken"],
            "clear-cursor": ["cursorApiKey"],
            "clear-codex": ["codexApiKey"],
            "clear-all": list(ALL_CREDENTIAL_KEYS),
        }
        if action_id in keys:
            self.app.run_worker(self.planner_app.on_clear_credentials(keys[action_id]), exclusive=True, name="auth-clear")

    def _on_token_submit(self, value: str) -> None:
        mode = self.mode
        self.mode = "overview"
        if not value:
            return
        callbacks = {"claude": self.planner_app.on_save_claude, "cursor": self.planner_app.on_save_cursor, "codex": self.planner_app.on_save_codex}
        if mode in callbacks:
            self.app.run_worker(callbacks[mode](value), exclusive=True, name="auth-save")

    @on(Button.Pressed, "#auth-back")
    def on_back_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.mode = "overview"
