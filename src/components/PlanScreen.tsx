import { useKeyboard, useRenderer } from "@opentui/react";
import type { Phase, ProposalState, RunMode } from "../pipeline/types.js";
import { Clickable } from "./Clickable.js";
import { ConsensusView } from "./ConsensusView.js";
import { GoalInput } from "./GoalInput.js";
import { ProposalList } from "./ProposalList.js";
import { ResultBrowser } from "./ResultBrowser.js";

export type PlanGate = "ready" | "need-models" | "need-auth";

interface PlanScreenProps {
  phase: Phase;
  gate: PlanGate;
  mode: RunMode;
  onModeChange: (mode: RunMode) => void;
  goal: string;
  proposals: ProposalState[];
  consensusStartedAt: number | null;
  planPath: string | null;
  archivePath: string | null;
  plan: string | null;
  error: string | null;
  failingLabels: string[];
  onSubmitGoal: (goal: string) => void;
  onGoModels: () => void;
  onGoAuth: () => void;
  onResetFailingKeys: () => void;
  onPlanAnother: () => void;
  onRetry: () => void;
  onBackToIdle: () => void;
}

const DIM = "#888888";

export function PlanScreen({
  phase,
  gate,
  mode,
  onModeChange,
  goal: _goal,
  proposals,
  consensusStartedAt,
  planPath,
  archivePath,
  plan,
  error,
  failingLabels,
  onSubmitGoal,
  onGoModels,
  onGoAuth,
  onResetFailingKeys,
  onPlanAnother,
  onRetry,
  onBackToIdle,
}: PlanScreenProps) {
  const renderer = useRenderer();
  const canResetAuth = failingLabels.length > 0;
  const anotherLabel = mode === "ask" ? "Ask another" : "Plan another";

  useKeyboard((key) => {
    if (phase !== "error") return;

    if (key.name === "q") {
      renderer.destroy();
      return;
    }

    if (key.name === "escape") {
      onBackToIdle();
      return;
    }

    if (key.name === "return") {
      onRetry();
      return;
    }

    if (canResetAuth && key.name === "r") {
      onResetFailingKeys();
    }
  });

  if (gate === "need-auth") {
    return (
      <box flexDirection="column" gap={1}>
        <text>
          <strong>Plan</strong>
        </text>
        <text fg={DIM}>
          Add at least one provider token (or skip both for mocks) on the Auth
          tab, then pick proposers and consensus.
        </text>
        <Clickable onClick={onGoAuth}>
          <text fg="cyan">→ Open Auth tab (or Ctrl+4)</text>
        </Clickable>
      </box>
    );
  }

  if (gate === "need-models") {
    return (
      <box flexDirection="column" gap={1}>
        <text>
          <strong>Plan</strong>
        </text>
        <text fg={DIM}>
          Select proposers and a consensus model before running a plan or ask.
        </text>
        <Clickable onClick={onGoModels}>
          <text fg="cyan">→ Open Proposers tab (or Ctrl+2)</text>
        </Clickable>
      </box>
    );
  }

  if (phase === "idle") {
    return (
      <GoalInput
        mode={mode}
        onModeChange={onModeChange}
        onSubmit={onSubmitGoal}
      />
    );
  }

  if (phase === "proposing") {
    return <ProposalList proposals={proposals} />;
  }

  if (phase === "consensus") {
    return (
      <box flexDirection="column" gap={1}>
        <ProposalList proposals={proposals} />
        <ConsensusView mode={mode} startedAt={consensusStartedAt} />
      </box>
    );
  }

  if (phase === "writing") {
    return (
      <box flexDirection="column" gap={1}>
        <ProposalList proposals={proposals} />
        <ConsensusView mode={mode} writing />
      </box>
    );
  }

  if (phase === "done" && plan !== null && archivePath) {
    return (
      <ResultBrowser
        mode={mode}
        planPath={planPath}
        archivePath={archivePath}
        plan={plan}
        proposals={proposals}
        onPlanAnother={onPlanAnother}
      />
    );
  }

  if (phase === "error") {
    return (
      <box flexDirection="column" gap={1}>
        <text fg="red">
          <strong>Error</strong>
        </text>
        <text fg="red">{error ?? "Something went wrong"}</text>
        {proposals.length > 0 ? <ProposalList proposals={proposals} /> : null}
        {canResetAuth ? (
          <text fg={DIM}>
            Enter retry · Esc {anotherLabel.toLowerCase()} · Press r to remove{" "}
            {failingLabels.join(" and ")} and re-enter · q to quit
          </text>
        ) : (
          <text fg={DIM}>
            Enter retry · Esc {anotherLabel.toLowerCase()} · q to quit
          </text>
        )}
        <Clickable onClick={onRetry}>
          <text fg="cyan">→ Retry (or press Enter)</text>
        </Clickable>
        <Clickable onClick={onBackToIdle}>
          <text fg="cyan">→ {anotherLabel} (or press Esc)</text>
        </Clickable>
        {canResetAuth ? (
          <Clickable onClick={onResetFailingKeys}>
            <text fg="cyan">→ Clear failing credentials (or press r)</text>
          </Clickable>
        ) : null}
      </box>
    );
  }

  return <text fg={DIM}>Ready.</text>;
}
