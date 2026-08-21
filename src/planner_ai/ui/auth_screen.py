from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Button,
    ContentSwitcher,
    Link,
    LoadingIndicator,
    OptionList,
    Static,
)
from textual.widgets.option_list import Option

from planner_ai.config import AppConfig, ConfigCredentialKey
from planner_ai.providers.codex_auth import (
    CodexAuthStatus,
    CodexLoginDetails,
    CodexLoginMethod,
)
from planner_ai.ui.token_input import TokenInput

if TYPE_CHECKING:
    from planner_ai.app import PlannerApp

AuthMode = Literal["overview", "claude", "cursor", "codex", "codex-login"]
ACTION_IDS = (
    "login-codex-browser",
    "login-codex-device",
    "edit-claude",
    "edit-cursor",
    "edit-codex",
    "clear-claude",
    "clear-cursor",
    "disconnect-codex",
    "clear-all",
)
ALL_CREDENTIAL_KEYS: list[ConfigCredentialKey] = [
    "claudeCodeOAuthToken",
    "cursorApiKey",
    "codexApiKey",
]


def status_line(label: str, is_set: bool) -> str:
    return f"{label}: {'set' if is_set else 'missing'}"


class AuthScreen(Widget):
    DEFAULT_CSS = """
    AuthScreen { height: 1fr; }
    AuthScreen #auth-switcher { height: 1fr; }
    AuthScreen #overview,
    AuthScreen #editor,
    AuthScreen #codex-login { height: auto; }
    AuthScreen #auth-title,
    AuthScreen #codex-login-title { text-style: bold; height: 1; }
    AuthScreen #auth-hint,
    AuthScreen #codex-shared-hint { color: #888888; height: auto; }
    AuthScreen #codex-shared-hint { margin-top: 1; }
    AuthScreen #auth-back,
    AuthScreen #codex-login-cancel {
        color: #888888; background: transparent; border: none;
        width: auto; min-width: 0; height: 3; padding: 0; margin-top: 1;
    }
    AuthScreen .status-set { color: green; height: 1; }
    AuthScreen .status-missing { color: yellow; height: 1; }
    AuthScreen #auth-actions { height: auto; margin: 1 0; }
    AuthScreen #codex-login-message,
    AuthScreen #codex-login-code { height: auto; }
    AuthScreen #codex-login-spinner { height: 1; }
    AuthScreen #codex-login-url { color: cyan; height: auto; margin: 1 0; }
    AuthScreen #codex-login-error { color: red; height: auto; }
    AuthScreen #codex-login-error.-hidden,
    AuthScreen #codex-login-code.-hidden,
    AuthScreen #codex-login-url.-hidden,
    AuthScreen #codex-login-spinner.-hidden { display: none; }
    """
    mode: reactive[AuthMode] = reactive("overview")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config: AppConfig = {}
        self._codex_status = CodexAuthStatus(authenticated=False)

    @property
    def planner_app(self) -> PlannerApp:
        return self.app  # type: ignore[return-value]

    def compose(self) -> ComposeResult:
        with ContentSwitcher(id="auth-switcher", initial="overview"):
            with Vertical(id="overview"):
                yield Static("Auth", id="auth-title")
                yield Static(
                    "ChatGPT uses your subscription; API keys use API billing.",
                    id="auth-hint",
                )
                yield Static("", id="status-claude", classes="status-missing")
                yield Static("", id="status-cursor", classes="status-missing")
                yield Static("", id="status-codex", classes="status-missing")
                yield OptionList(id="auth-actions")
            with Vertical(id="editor"):
                yield TokenInput(id="auth-token-input")
                yield Button(
                    "← Back to Auth overview",
                    id="auth-back",
                    flat=True,
                )
            with Vertical(id="codex-login"):
                yield Static("Connect ChatGPT", id="codex-login-title")
                yield LoadingIndicator(id="codex-login-spinner")
                yield Static("Starting Codex login…", id="codex-login-message")
                yield Link(
                    "",
                    url="",
                    id="codex-login-url",
                    classes="-hidden",
                )
                yield Static("", id="codex-login-code", classes="-hidden")
                yield Static("", id="codex-login-error", classes="-hidden")
                yield Static(
                    "This session is shared with Codex CLI and the IDE extension.",
                    id="codex-shared-hint",
                )
                yield Button(
                    "Cancel login",
                    id="codex-login-cancel",
                    flat=True,
                )

    def on_mount(self) -> None:
        self.sync_config(self._config)

    def sync_config(
        self,
        config: AppConfig,
        codex_status: CodexAuthStatus | None = None,
    ) -> None:
        self._config = config
        if codex_status is not None:
            self._codex_status = codex_status
        present = [bool(config.get(key)) for key in ALL_CREDENTIAL_KEYS]
        self._set_status("status-claude", "Claude OAuth", present[0])
        self._set_status("status-cursor", "Cursor API key", present[1])
        codex_connected = present[2] or self._codex_status.authenticated
        self._set_status(
            "status-codex",
            self._codex_status_label(present[2]),
            codex_connected,
        )
        labels = [
            "Connect ChatGPT in browser",
            "Connect ChatGPT with device code (beta)",
            f"{'Edit' if present[0] else 'Set'} Claude OAuth token",
            f"{'Edit' if present[1] else 'Set'} Cursor API key",
            f"{'Edit' if present[2] else 'Set'} Codex API key (usage billing)",
            "Clear Claude token",
            "Clear Cursor key",
            "Disconnect Codex shared session",
            "Clear all credentials and shared Codex session",
        ]
        disabled = [
            False,
            False,
            False,
            False,
            False,
            not present[0],
            not present[1],
            not codex_connected,
            not any(present) and not self._codex_status.authenticated,
        ]
        actions = self.query_one("#auth-actions", OptionList)
        current = actions.highlighted_option.id if actions.highlighted_option else None
        actions.clear_options()
        for action_id, label, off in zip(
            ACTION_IDS,
            labels,
            disabled,
            strict=True,
        ):
            actions.add_option(Option(label, id=action_id, disabled=off))
        if current:
            self.highlight_action(current)

    def _codex_status_label(self, has_config_key: bool) -> str:
        if has_config_key:
            return "Codex API key"
        if self._codex_status.method == "chatgpt":
            plan = self._codex_status.plan
            suffix = f" ({plan.replace('_', ' ').title()})" if plan else ""
            return f"Codex ChatGPT{suffix}"
        if self._codex_status.method == "apiKey":
            return "Codex API key (shared)"
        if self._codex_status.error:
            return "Codex status unavailable"
        return "Codex ChatGPT"

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
        elif mode == "codex-login":
            switcher.current = "codex-login"
        else:
            switcher.current = "editor"
            self._configure_editor(mode)

    def _configure_editor(self, mode: AuthMode) -> None:
        if mode == "claude":
            label = "Claude Code OAuth token"
            hint = "Run `claude setup-token`, then paste. Enter empty to cancel."
        elif mode == "cursor":
            label = "Cursor API key"
            hint = "From Cursor Dashboard → Integrations. Enter empty to cancel."
        else:
            label = "Codex API key"
            hint = (
                "From platform.openai.com/api-keys (usage billing). "
                "Enter empty to cancel."
            )
        self.query_one("#auth-token-input", TokenInput).configure(
            label,
            hint,
            self._on_token_submit,
        )

    def highlight_action(self, action_id: str) -> None:
        if action_id in ACTION_IDS:
            self.query_one("#auth-actions", OptionList).highlighted = (
                ACTION_IDS.index(action_id)
            )

    def activate_highlighted(self) -> None:
        option = self.query_one("#auth-actions", OptionList).highlighted_option
        if option and not option.disabled and option.id:
            self._run_action(option.id)

    @on(OptionList.OptionSelected, "#auth-actions")
    def on_action_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self._run_action(event.option.id)

    def _run_action(self, action_id: str) -> None:
        if action_id == "login-codex-browser":
            self._start_codex_login("browser")
            return
        if action_id == "login-codex-device":
            self._start_codex_login("device")
            return
        if action_id.startswith("edit-"):
            self.mode = action_id.removeprefix("edit-")  # type: ignore[assignment]
            return
        keys: dict[str, list[ConfigCredentialKey]] = {
            "clear-claude": ["claudeCodeOAuthToken"],
            "clear-cursor": ["cursorApiKey"],
            "disconnect-codex": ["codexApiKey"],
            "clear-all": list(ALL_CREDENTIAL_KEYS),
        }
        if action_id in keys:
            self.app.run_worker(
                self.planner_app.on_clear_credentials(keys[action_id]),
                exclusive=True,
                name="auth-clear",
            )

    def _start_codex_login(self, method: CodexLoginMethod) -> None:
        self.mode = "codex-login"
        self.query_one("#codex-login-message", Static).update(
            "Starting browser login…"
            if method == "browser"
            else "Requesting a device code…"
        )
        self.query_one("#codex-login-spinner").remove_class("-hidden")
        self.query_one("#codex-login-url").add_class("-hidden")
        self.query_one("#codex-login-code").add_class("-hidden")
        self.query_one("#codex-login-error").add_class("-hidden")
        self.query_one("#codex-login-cancel", Button).label = "Cancel login"
        self.planner_app.start_codex_login(method)

    def show_codex_login_details(self, details: CodexLoginDetails) -> None:
        link = self.query_one("#codex-login-url", Link)
        link.text = details.url
        link.url = details.url
        link.remove_class("-hidden")
        if details.method == "browser":
            message = (
                "Complete sign-in in your browser. If it did not open, use this link:"
            )
        else:
            message = "Open this link and enter the one-time code:"
            code = self.query_one("#codex-login-code", Static)
            code.update(f"Code: {details.user_code}")
            code.remove_class("-hidden")
        self.query_one("#codex-login-message", Static).update(message)

    def show_codex_login_error(self, message: str) -> None:
        self.query_one("#codex-login-spinner").add_class("-hidden")
        error = self.query_one("#codex-login-error", Static)
        error.update(message)
        error.remove_class("-hidden")
        self.query_one("#codex-login-cancel", Button).label = (
            "← Back to Auth overview"
        )

    def _on_token_submit(self, value: str) -> None:
        mode = self.mode
        self.mode = "overview"
        if not value:
            return
        callbacks = {
            "claude": self.planner_app.on_save_claude,
            "cursor": self.planner_app.on_save_cursor,
            "codex": self.planner_app.on_save_codex,
        }
        if mode in callbacks:
            self.app.run_worker(
                callbacks[mode](value),
                exclusive=True,
                name="auth-save",
            )

    @on(Button.Pressed, "#auth-back")
    def on_back_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.mode = "overview"

    @on(Button.Pressed, "#codex-login-cancel")
    def on_codex_login_cancel(self, event: Button.Pressed) -> None:
        event.stop()
        self.planner_app.cancel_codex_login()
        self.mode = "overview"
