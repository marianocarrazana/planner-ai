from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Static


class TokenInput(Vertical):
    """Masked token field. Enter submits trimmed value; empty cancels."""

    DEFAULT_CSS = """
    TokenInput {
        height: auto;
        layout: vertical;
    }

    TokenInput #token-label {
        height: 1;
    }

    TokenInput #token-hint {
        height: auto;
        color: #888888;
    }

    TokenInput #token-hint.-hidden {
        display: none;
    }

    TokenInput #token-field {
        width: 1fr;
    }
    """

    def __init__(
        self,
        label: str = "",
        on_submit: Callable[[str], None] | None = None,
        *,
        hint: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._label = label
        self._hint = hint or ""
        self._on_submit = on_submit

    def compose(self) -> ComposeResult:
        yield Static(self._label, id="token-label")
        hint = Static(self._hint, id="token-hint")
        if not self._hint:
            hint.add_class("-hidden")
        yield hint
        yield Input(
            password=True,
            placeholder="Enter to skip…",
            id="token-field",
        )

    def configure(
        self,
        label: str,
        hint: str,
        on_submit: Callable[[str], None],
    ) -> None:
        self._on_submit = on_submit
        self.query_one("#token-label", Static).update(label)
        hint_widget = self.query_one("#token-hint", Static)
        hint_widget.update(hint)
        hint_widget.remove_class("-hidden")
        self.clear()
        self.query_one("#token-field", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        if self._on_submit is not None:
            self._on_submit(event.value.strip())

    def clear(self) -> None:
        self.query_one("#token-field", Input).value = ""
