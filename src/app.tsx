import { useKeyboard, useTerminalDimensions } from "@opentui/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppTabs, type AppTab } from "./components/AppTabs.js";
import { AuthScreen } from "./components/AuthScreen.js";
import { ModelSelect } from "./components/ModelSelect.js";
import { PlanScreen, type PlanGate } from "./components/PlanScreen.js";
import {
  clearCredentials,
  getConfigPath,
  loadConfig,
  saveConfig,
  type AppConfig,
  type ConfigCredentialKey,
} from "./config.js";
import { runPipeline } from "./pipeline/runPipeline.js";
import type { Phase, ProposalState } from "./pipeline/types.js";
import { collectFailingCredentialKeys } from "./providers/authError.js";
import {
  availableChoices,
  normalizeSelection,
  resolveInitialSelection,
  type ModelChoice,
  type ModelSelection,
} from "./providers/models.js";
import {
  resolveProviders,
  type ResolvedProviders,
} from "./providers/resolve.js";
import { getWorkspaceCwd } from "./workspace.js";

export type { AppTab };

const DIM = "#888888";

function formatSources(sources: {
  proposers: string[];
  consensus: string;
}): string {
  const proposers = sources.proposers.join(" + ");
  return `proposers: ${proposers} · consensus: ${sources.consensus}`;
}

function startupTab(creds: AppConfig, choices: ModelChoice[]): AppTab {
  if (!creds.claudeCodeOAuthToken || !creds.cursorApiKey) {
    return "auth";
  }
  if (!normalizeSelection(creds.modelSelection, choices)) {
    return "models";
  }
  return "plan";
}

export function App() {
  const { width, height } = useTerminalDimensions();

  const [activeTab, setActiveTab] = useState<AppTab>("plan");
  const [phase, setPhase] = useState<Phase>("idle");
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [config, setConfig] = useState<AppConfig>({});
  const [choices, setChoices] = useState<ModelChoice[]>([]);
  const [selection, setSelection] = useState<ModelSelection | null>(null);
  const [providers, setProviders] = useState<ResolvedProviders | null>(null);
  const [goal, setGoal] = useState("");
  const [proposals, setProposals] = useState<ProposalState[]>([]);
  const [planPath, setPlanPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failingKeys, setFailingKeys] = useState<ConfigCredentialKey[]>([]);
  const [loadingChoices, setLoadingChoices] = useState(false);

  const goTab = useCallback((tab: AppTab) => {
    setActiveTab(tab);
  }, []);

  const reloadModels = useCallback(
    async (creds: AppConfig, preferTab?: AppTab) => {
      setConfig(creds);
      setFailingKeys([]);
      setError(null);
      setLoadingChoices(true);

      try {
        const nextChoices = await availableChoices(creds);
        const savedValid = normalizeSelection(
          creds.modelSelection,
          nextChoices,
        );
        const nextSelection = resolveInitialSelection(
          creds.modelSelection,
          nextChoices,
        );
        setChoices(nextChoices);
        setSelection(nextSelection);

        if (savedValid) {
          setProviders(resolveProviders(creds, nextSelection, nextChoices));
        } else {
          setProviders(null);
        }

        goTab(preferTab ?? startupTab(creds, nextChoices));
      } catch (err) {
        setPhase("error");
        setError(
          err instanceof Error
            ? `Failed to load models: ${err.message}`
            : `Failed to load models: ${String(err)}`,
        );
        goTab("plan");
      } finally {
        setLoadingChoices(false);
      }
    },
    [goTab],
  );

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const loaded = await loadConfig();
        if (cancelled) return;
        setLoadingConfig(false);
        await reloadModels(loaded);
      } catch (err) {
        if (cancelled) return;
        setLoadingConfig(false);
        setPhase("error");
        setError(
          err instanceof Error
            ? `Failed to load config: ${err.message}`
            : `Failed to load config: ${String(err)}`,
        );
        goTab("plan");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [reloadModels, goTab]);

  const onSaveClaude = useCallback(
    async (token: string) => {
      try {
        const next = await saveConfig({ claudeCodeOAuthToken: token });
        await reloadModels(next, "auth");
      } catch (err) {
        setPhase("error");
        setError(err instanceof Error ? err.message : String(err));
        goTab("plan");
      }
    },
    [reloadModels, goTab],
  );

  const onSaveCursor = useCallback(
    async (token: string) => {
      try {
        const next = await saveConfig({ cursorApiKey: token });
        await reloadModels(next, "auth");
      } catch (err) {
        setPhase("error");
        setError(err instanceof Error ? err.message : String(err));
        goTab("plan");
      }
    },
    [reloadModels, goTab],
  );

  const onClearCredentials = useCallback(
    async (keys: ConfigCredentialKey[]) => {
      try {
        const next = await clearCredentials(keys);
        setProviders(null);
        setSelection(null);
        setPhase("idle");
        await reloadModels(next, "auth");
      } catch (err) {
        setPhase("error");
        setError(err instanceof Error ? err.message : String(err));
        goTab("plan");
      }
    },
    [reloadModels, goTab],
  );

  const onModelSelection = useCallback(
    async (nextSelection: ModelSelection) => {
      try {
        const next = await saveConfig({ modelSelection: nextSelection });
        setConfig(next);
        setSelection(nextSelection);
        const resolved = resolveProviders(next, nextSelection, choices);
        setProviders(resolved);
        setPhase("idle");
        setError(null);
        goTab("plan");
      } catch (err) {
        setPhase("error");
        setError(err instanceof Error ? err.message : String(err));
        goTab("plan");
      }
    },
    [choices, goTab],
  );

  const start = useCallback(
    async (nextGoal: string) => {
      if (!providers) return;

      setGoal(nextGoal);
      setError(null);
      setFailingKeys([]);
      setPlanPath(null);
      setProposals([]);

      let latestProposals: ProposalState[] = [];

      try {
        const result = await runPipeline(
          nextGoal,
          providers.proposers,
          providers.consensus,
          {
            onPhase: setPhase,
            onProposals: (next) => {
              latestProposals = next;
              setProposals(next);
            },
          },
        );
        setPlanPath(result.planPath);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const keys = collectFailingCredentialKeys({
          proposals: latestProposals,
          errorMessage: message,
          consensusSource: providers.sources.consensus,
        });
        setFailingKeys(keys);
        setPhase("error");
        setError(message);
      }
    },
    [providers],
  );

  const removeFailingKeys = useCallback(async () => {
    if (failingKeys.length === 0) return;

    try {
      const next = await clearCredentials(failingKeys);
      setProviders(null);
      setSelection(null);
      setChoices([]);
      setFailingKeys([]);
      setError(null);
      setGoal("");
      setProposals([]);
      setPlanPath(null);
      setPhase("idle");
      await reloadModels(next, "auth");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [failingKeys, reloadModels]);

  useKeyboard((key) => {
    // Ctrl+digit avoids stealing keys from GoalInput / TokenInput.
    if (!key.ctrl || key.meta) return;
    if (key.name === "1") {
      goTab("plan");
      return;
    }
    if (key.name === "2") {
      goTab("models");
      return;
    }
    if (key.name === "3") {
      goTab("auth");
    }
  });

  const failingLabels = useMemo(() => {
    return failingKeys.map((key) =>
      key === "claudeCodeOAuthToken" ? "Claude OAuth token" : "Cursor API key",
    );
  }, [failingKeys]);

  const planGate: PlanGate = providers
    ? "ready"
    : !config.claudeCodeOAuthToken && !config.cursorApiKey
      ? "need-auth"
      : "need-models";

  return (
    <box
      flexDirection="column"
      paddingLeft={1}
      paddingRight={1}
      paddingTop={1}
      paddingBottom={1}
      width={width}
      height={height}
      gap={1}
    >
      <box flexDirection="column">
        <text>
          <strong>planner-ai</strong>
        </text>
        <text fg={DIM}>cwd: {getWorkspaceCwd()}</text>
        {providers ? (
          <text fg={DIM}>{formatSources(providers.sources)}</text>
        ) : (
          <text fg={DIM}>config: {getConfigPath()}</text>
        )}
        {goal ? <text fg={DIM}>Goal: {goal}</text> : null}
        <text fg={DIM}>Tabs: click or Ctrl+1 Plan · Ctrl+2 Models · Ctrl+3 Auth</text>
      </box>

      <AppTabs active={activeTab} onChange={goTab} />

      <box flexDirection="column" flexGrow={1} gap={1}>
        {loadingConfig ? <text fg={DIM}>Loading config…</text> : null}

        {!loadingConfig && activeTab === "plan" ? (
          <PlanScreen
            phase={phase}
            gate={planGate}
            goal={goal}
            proposals={proposals}
            planPath={planPath}
            error={error}
            failingLabels={failingLabels}
            onSubmitGoal={(nextGoal) => {
              void start(nextGoal);
            }}
            onGoModels={() => goTab("models")}
            onGoAuth={() => goTab("auth")}
            onResetFailingKeys={() => {
              void removeFailingKeys();
            }}
          />
        ) : null}

        {!loadingConfig && activeTab === "models" ? (
          loadingChoices ? (
            <text fg={DIM}>Loading models…</text>
          ) : selection ? (
            <ModelSelect
              choices={choices}
              initial={selection}
              onSubmit={(next) => {
                void onModelSelection(next);
              }}
            />
          ) : (
            <text fg={DIM}>No models available.</text>
          )
        ) : null}

        {!loadingConfig && activeTab === "auth" ? (
          <AuthScreen
            config={config}
            onSaveClaude={(token) => {
              void onSaveClaude(token);
            }}
            onSaveCursor={(token) => {
              void onSaveCursor(token);
            }}
            onClear={(keys) => {
              void onClearCredentials(keys);
            }}
          />
        ) : null}
      </box>
    </box>
  );
}
