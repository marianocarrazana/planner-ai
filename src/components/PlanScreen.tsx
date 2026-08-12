import { useKeyboard, useRenderer } from "@opentui/react";
import type { Phase, ProposalState } from "../pipeline/types.js";
import { Clickable } from "./Clickable.js";
import { ConsensusView } from "./ConsensusView.js";
import { DoneView } from "./DoneView.js";
import { GoalInput } from "./GoalInput.js";
import { ProposalList } from "./ProposalList.js";

export type PlanGate = "ready" | "need-models" | "need-auth";

interface PlanScreenProps {
  phase: Phase;
  gate: PlanGate;
  goal: string;
  proposals: ProposalState[];
  planPath: string | null;
  error: string | null;
  failingLabels: string[];
  onSubmitGoal: (goal: string) => void;
  onGoModels: () => void;
  onGoAuth: () => void;
  onResetFailingKeys: () => void;
}

const DIM = "#888888";

export function PlanScreen({
  phase,
  gate,
  goal: _goal,
  proposals,
  planPath,
  error,
  failingLabels,
  onSubmitGoal,
  onGoModels,
  onGoAuth,
  onResetFailingKeys,
}: PlanScreenProps) {
  const renderer = useRenderer();
  const canResetAuth = failingLabels.length > 0;

  useKeyboard((key) => {
    if (phase !== "error") return;

    if (key.name === "q" || key.name === "escape") {
      renderer.destroy();
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
          tab, then pick models.
        </text>
        <Clickable onClick={onGoAuth}>
          <text fg="cyan">→ Open Auth tab (or Ctrl+3)</text>
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
          Select proposers and a consensus model before running a plan.
        </text>
        <Clickable onClick={onGoModels}>
          <text fg="cyan">→ Open Models tab (or Ctrl+2)</text>
        </Clickable>
      </box>
    );
  }

  if (phase === "idle") {
    return <GoalInput onSubmit={onSubmitGoal} />;
  }

  if (phase === "proposing") {
    return <ProposalList proposals={proposals} />;
  }

  if (phase === "consensus") {
    return (
      <box flexDirection="column" gap={1}>
        <ProposalList proposals={proposals} />
        <ConsensusView />
      </box>
    );
  }

  if (phase === "writing") {
    return (
      <box flexDirection="column" gap={1}>
        <ProposalList proposals={proposals} />
        <ConsensusView writing />
      </box>
    );
  }

  if (phase === "done" && planPath) {
    return <DoneView planPath={planPath} />;
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
            Press r to remove {failingLabels.join(" and ")} and re-enter · q to
            quit
          </text>
        ) : (
          <text fg={DIM}>Press q to quit</text>
        )}
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
