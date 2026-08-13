from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import ContentSwitcher, Static

from planner_ai.config import (
    AppConfig,
    ConfigCredentialKey,
    clear_credentials,
    get_config_path,
    load_config,
    save_config,
)
from planner_ai.pipeline.run_pipeline import run_pipeline
from planner_ai.pipeline.types import Phase, PipelineCallbacks, ProposalState, RunMode
from planner_ai.providers.auth_error import collect_failing_credential_keys
from planner_ai.providers.models import (
    ModelChoice,
    ModelSelection,
    available_choices,
    normalize_selection,
    resolve_initial_selection,
)
from planner_ai.providers.resolve import ResolvedProviders, resolve_providers
from planner_ai.providers.types import ProviderCallOptions
from planner_ai.ui.auth_screen import AuthScreen
from planner_ai.ui.history_screen import HistoryScreen
from planner_ai.ui.model_select import ModelSelect
from planner_ai.ui.plan_helpers import has_any_real_credential, plan_gate
from planner_ai.ui.plan_screen import PlanScreen
from planner_ai.ui.tabs import TABS, AppTab, AppTabs, TabSelected
from planner_ai.workspace import get_workspace_cwd


def format_sources(sources: dict[str, object]) -> str:
    proposers_raw = sources.get("proposers", [])
    if isinstance(proposers_raw, list):
        proposers = " + ".join(str(p) for p in proposers_raw)
    else:
        proposers = ""
    consensus = sources.get("consensus", "")
    return f"proposers: {proposers} · consensus: {consensus}"


def credential_label(key: ConfigCredentialKey) -> str:
    match key:
        case "claudeCodeOAuthToken":
            return "Claude OAuth token"
        case "cursorApiKey":
            return "Cursor API key"
        case "codexApiKey":
            return "Codex API key"


def startup_tab(creds: AppConfig, choices: list[ModelChoice]) -> AppTab:
    if not has_any_real_credential(creds):
        return "auth"
    if not normalize_selection(creds.get("modelSelection"), choices):
        return "proposers"
    return "plan"


class PlannerApp(App[None]):
    """Textual shell: header, tabs, config load / model reload / plan runs."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        layout: vertical;
        padding: 1;
    }

    #header {
        height: auto;
        layout: vertical;
    }

    #header-title {
        text-style: bold;
    }

    #header-cwd,
    #header-sources,
    #header-goal,
    #header-tabs-hint {
        color: #888888;
    }

    #header-goal.-hidden {
        display: none;
    }

    #loading-config {
        color: #888888;
    }

    #loading-config.-hidden {
        display: none;
    }

    #tab-body {
        height: 1fr;
    }

    .placeholder-pane {
        color: #888888;
        padding: 1 0;
    }

    #plan,
    #auth,
    #proposers,
    #consensus,
    #history {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+1", "go_tab_plan", "Plan", show=False, priority=True),
        Binding("ctrl+2", "go_tab_proposers", "Proposers", show=False, priority=True),
        Binding("ctrl+3", "go_tab_consensus", "Consensus", show=False, priority=True),
        Binding("ctrl+4", "go_tab_auth", "Auth", show=False, priority=True),
        Binding("ctrl+5", "go_tab_history", "History", show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.active_tab: AppTab = "plan"
        self.phase: Phase = "idle"
        self.loading_config = True
        self.config: AppConfig = {}
        self.choices: list[ModelChoice] = []
        self.draft_selection: ModelSelection | None = None
        self.providers: ResolvedProviders | None = None
        self.run_mode: RunMode = "plan"
        self.goal = ""
        self.proposals: list[ProposalState] = []
        self.consensus_started_at: int | None = None
        self.plan_path: str | None = None
        self.archive_path: str | None = None
        self.plan: str | None = None
        self.error: str | None = None
        self.failing_keys: list[ConfigCredentialKey] = []
        self.loading_choices = False

    def compose(self) -> ComposeResult:
        with Vertical(id="header"):
            yield Static("planner-ai", id="header-title")
            yield Static("", id="header-cwd")
            yield Static("", id="header-sources")
            yield Static("", id="header-goal", classes="-hidden")
            yield Static(
                "Tabs: click or Ctrl+1 Plan · Ctrl+2 Proposers · Ctrl+3 Consensus · "
                "Ctrl+4 Auth · Ctrl+5 History",
                id="header-tabs-hint",
            )
        yield AppTabs()
        yield Static("Loading config…", id="loading-config")
        with ContentSwitcher(id="tab-body", initial="plan"):
            for tab_id, label in TABS:
                if tab_id == "plan":
                    yield PlanScreen(id="plan")
                elif tab_id == "auth":
                    yield AuthScreen(id="auth")
                elif tab_id == "proposers":
                    yield ModelSelect("proposers", id="proposers")
                elif tab_id == "consensus":
                    yield ModelSelect("consensus", id="consensus")
                elif tab_id == "history":
                    yield HistoryScreen(id="history")
                else:
                    yield Static(label, id=tab_id, classes="placeholder-pane")

    async def on_mount(self) -> None:
        self._refresh_header()
        try:
            loaded = load_config()
            self.loading_config = False
            self._set_loading_visible(False)
            await self.reload_models(loaded)
        except Exception as err:
            self.loading_config = False
            self._set_loading_visible(False)
            self.phase = "error"
            self.error = f"Failed to load config: {err}"
            self.go_tab("plan")
            self._sync_plan_screen()

    def _set_loading_visible(self, visible: bool) -> None:
        loading = self.query_one("#loading-config", Static)
        loading.set_class(not visible, "-hidden")

    def _refresh_header(self) -> None:
        self.query_one("#header-cwd", Static).update(f"cwd: {get_workspace_cwd()}")
        sources = self.query_one("#header-sources", Static)
        if self.providers is not None:
            sources.update(format_sources(self.providers.sources))
        else:
            sources.update(f"config: {get_config_path()}")

        goal_widget = self.query_one("#header-goal", Static)
        if self.goal:
            prefix = "Question" if self.run_mode == "ask" else "Goal"
            goal_widget.update(f"{prefix}: {self.goal}")
            goal_widget.remove_class("-hidden")
        else:
            goal_widget.update("")
            goal_widget.add_class("-hidden")

    def _failing_labels(self) -> list[str]:
        return [credential_label(k) for k in self.failing_keys]

    def _sync_model_selects(self) -> None:
        include_mocks = self.config.get("includeMocks") is True
        for widget_id in ("proposers", "consensus"):
            self.query_one(f"#{widget_id}", ModelSelect).sync(
                choices=self.choices,
                selection=self.draft_selection,
                include_mocks=include_mocks,
                loading=self.loading_choices,
            )

    def _sync_plan_screen(self) -> None:
        self.query_one("#plan", PlanScreen).sync(
            phase=self.phase,
            gate=plan_gate(self.providers, self.config),
            mode=self.run_mode,
            proposals=self.proposals,
            consensus_started_at=self.consensus_started_at,
            plan_path=self.plan_path,
            archive_path=self.archive_path,
            plan=self.plan,
            error=self.error,
            failing_labels=self._failing_labels(),
        )

    def go_tab(self, tab: AppTab) -> None:
        previous = self.active_tab
        self.active_tab = tab
        self.query_one(AppTabs).active = tab
        self.query_one("#tab-body", ContentSwitcher).current = tab
        if tab == "plan":
            self._sync_plan_screen()
            self.query_one("#plan", PlanScreen).focus_for_state()
        elif tab == "auth":
            auth = self.query_one(AuthScreen)
            if auth.mode == "overview":
                auth.focus()
        elif tab in ("proposers", "consensus"):
            self.query_one(f"#{tab}", ModelSelect).focus()
        elif tab == "history":
            history = self.query_one("#history", HistoryScreen)
            if previous != "history":
                history.show_list_and_reload()
            else:
                history.focus()

    def action_go_tab_plan(self) -> None:
        self.go_tab("plan")

    def action_go_tab_proposers(self) -> None:
        self.go_tab("proposers")

    def action_go_tab_consensus(self) -> None:
        self.go_tab("consensus")

    def action_go_tab_auth(self) -> None:
        self.go_tab("auth")

    def action_go_tab_history(self) -> None:
        self.go_tab("history")

    def on_tab_selected(self, event: TabSelected) -> None:
        self.go_tab(event.tab)

    def on_draft_selection_change(self, selection: ModelSelection) -> None:
        self.draft_selection = selection
        self._sync_model_selects()

    def set_run_mode(self, mode: RunMode) -> None:
        self.run_mode = mode
        self._refresh_header()
        self._sync_plan_screen()

    def submit_goal(self, goal: str) -> None:
        self.run_worker(
            self.start(goal, self.run_mode),
            exclusive=True,
            name="pipeline",
        )

    def retry_run(self) -> None:
        if self.goal.strip():
            self.run_worker(
                self.start(self.goal, self.run_mode),
                exclusive=True,
                name="pipeline",
            )

    def plan_another(self) -> None:
        self.plan = None
        self.plan_path = None
        self.archive_path = None
        self.error = None
        self.proposals = []
        self.consensus_started_at = None
        self.phase = "idle"
        self._sync_plan_screen()
        self._refresh_header()
        self.query_one("#plan", PlanScreen).focus_for_state()

    def back_to_idle(self) -> None:
        self.plan = None
        self.plan_path = None
        self.archive_path = None
        self.error = None
        self.proposals = []
        self.consensus_started_at = None
        self.failing_keys = []
        self.phase = "idle"
        self._sync_plan_screen()
        self._refresh_header()
        self.query_one("#plan", PlanScreen).focus_for_state()

    def reset_failing_keys(self) -> None:
        self.run_worker(
            self.remove_failing_keys(),
            exclusive=True,
            name="reset-failing",
        )

    async def start(
        self,
        next_goal: str,
        mode: RunMode | None = None,
    ) -> None:
        if self.providers is None:
            return

        run_mode = mode if mode is not None else self.run_mode
        self.run_mode = run_mode
        self.goal = next_goal
        self.error = None
        self.failing_keys = []
        self.plan_path = None
        self.archive_path = None
        self.plan = None
        self.proposals = []
        self.consensus_started_at = None
        self._refresh_header()
        self._sync_plan_screen()

        latest: list[ProposalState] = []
        providers = self.providers

        def on_phase(phase: Phase) -> None:
            self.phase = phase
            self._sync_plan_screen()

        def on_proposals(proposals: list[ProposalState]) -> None:
            nonlocal latest
            latest = proposals
            self.proposals = proposals
            self._sync_plan_screen()

        def on_consensus_started(started_at: int) -> None:
            self.consensus_started_at = started_at
            self._sync_plan_screen()

        try:
            result = await run_pipeline(
                next_goal,
                providers.proposers,
                providers.consensus,
                PipelineCallbacks(
                    on_phase=on_phase,
                    on_proposals=on_proposals,
                    on_consensus_started=on_consensus_started,
                ),
                ProviderCallOptions(mode=run_mode),
            )
            self.plan_path = (
                str(result.plan_path) if result.plan_path is not None else None
            )
            self.archive_path = str(result.archive_path)
            self.plan = result.plan
            self.run_mode = result.mode
            self.proposals = result.proposals
        except Exception as err:
            message = str(err) if str(err) else repr(err)
            keys = collect_failing_credential_keys(
                proposals=latest,
                error_message=message,
                consensus_source=providers.sources["consensus"],
            )
            self.failing_keys = keys
            self.phase = "error"
            self.error = message
        finally:
            self._sync_plan_screen()
            self._refresh_header()
            if self.phase == "done":
                self.query_one("#plan", PlanScreen).focus_for_state()
            elif self.phase == "error":
                self.query_one("#plan", PlanScreen).focus()

    async def remove_failing_keys(self) -> None:
        if len(self.failing_keys) == 0:
            return
        try:
            next_config = clear_credentials(self.failing_keys)
            self.providers = None
            self.draft_selection = None
            self.choices = []
            self.failing_keys = []
            self.error = None
            self.goal = ""
            self.proposals = []
            self.consensus_started_at = None
            self.plan_path = None
            self.archive_path = None
            self.plan = None
            self.phase = "idle"
            await self.reload_models(next_config, "auth")
        except Exception as err:
            self.error = str(err) if str(err) else repr(err)
            self._sync_plan_screen()

    async def reload_models(
        self,
        creds: AppConfig,
        prefer_tab: AppTab | None = None,
    ) -> None:
        self.config = creds
        self.failing_keys = []
        self.error = None
        self.loading_choices = True
        self._sync_model_selects()

        try:
            next_choices = await available_choices(
                creds,
                {"includeMocks": creds.get("includeMocks") is True},
            )
            saved_valid = normalize_selection(
                creds.get("modelSelection"),
                next_choices,
            )
            next_selection = resolve_initial_selection(
                creds.get("modelSelection"),
                next_choices,
            )
            self.choices = next_choices
            self.draft_selection = next_selection

            if saved_valid is not None:
                self.providers = resolve_providers(
                    creds,
                    next_selection,
                    next_choices,
                )
            else:
                self.providers = None

            self.query_one(AuthScreen).sync_config(creds)
            self._refresh_header()
            self._sync_plan_screen()
            self.go_tab(
                prefer_tab
                if prefer_tab is not None
                else startup_tab(creds, next_choices)
            )
        except Exception as err:
            self.phase = "error"
            message = str(err) if str(err) else repr(err)
            self.error = f"Failed to load models: {message}"
            self.go_tab("plan")
            self._sync_plan_screen()
        finally:
            self.loading_choices = False
            self._sync_model_selects()

    async def on_model_selection(self, next_selection: ModelSelection) -> None:
        try:
            next_config = save_config({"modelSelection": next_selection})
            self.config = next_config
            self.draft_selection = next_selection
            self.providers = resolve_providers(
                next_config,
                next_selection,
                self.choices,
            )
            self.phase = "idle"
            self.error = None
            self._sync_model_selects()
            self._refresh_header()
            self._sync_plan_screen()
            self.go_tab("plan")
        except Exception as err:
            self.phase = "error"
            self.error = str(err) if str(err) else repr(err)
            self.go_tab("plan")
            self._sync_plan_screen()

    async def on_toggle_include_mocks(self) -> None:
        try:
            next_config = save_config(
                {"includeMocks": self.config.get("includeMocks") is not True}
            )
            stay: AppTab | None = None
            if self.active_tab in ("proposers", "consensus"):
                stay = self.active_tab
            await self.reload_models(next_config, stay)
        except Exception as err:
            self.phase = "error"
            self.error = str(err) if str(err) else repr(err)
            self.go_tab("plan")
            self._sync_plan_screen()

    async def on_save_claude(self, token: str) -> None:
        try:
            next_config = save_config({"claudeCodeOAuthToken": token})
            await self.reload_models(next_config, "auth")
        except Exception as err:
            self.phase = "error"
            self.error = str(err) if str(err) else repr(err)
            self.go_tab("plan")
            self._sync_plan_screen()

    async def on_save_cursor(self, token: str) -> None:
        try:
            next_config = save_config({"cursorApiKey": token})
            await self.reload_models(next_config, "auth")
        except Exception as err:
            self.phase = "error"
            self.error = str(err) if str(err) else repr(err)
            self.go_tab("plan")
            self._sync_plan_screen()

    async def on_save_codex(self, token: str) -> None:
        try:
            next_config = save_config({"codexApiKey": token})
            await self.reload_models(next_config, "auth")
        except Exception as err:
            self.phase = "error"
            self.error = str(err) if str(err) else repr(err)
            self.go_tab("plan")
            self._sync_plan_screen()

    async def on_clear_credentials(self, keys: list[ConfigCredentialKey]) -> None:
        try:
            next_config = clear_credentials(keys)
            self.providers = None
            self.draft_selection = None
            self.phase = "idle"
            await self.reload_models(next_config, "auth")
        except Exception as err:
            self.phase = "error"
            self.error = str(err) if str(err) else repr(err)
            self.go_tab("plan")
            self._sync_plan_screen()
