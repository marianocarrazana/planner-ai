import type { ProposalState } from "../pipeline/types.js";
import {
  formatElapsedSeconds,
  useElapsedSeconds,
} from "./useElapsedSeconds.js";

interface ProposalListProps {
  proposals: ProposalState[];
}

const DIM = "#888888";

function statusLabel(
  status: ProposalState["status"],
  elapsedSeconds: number | null,
): string {
  switch (status) {
    case "pending":
      return "pending";
    case "streaming":
      return elapsedSeconds != null
        ? `working… ${formatElapsedSeconds(elapsedSeconds)}`
        : "working…";
    case "done":
      return "done";
    case "error":
      return "error";
  }
}

function statusColor(status: ProposalState["status"]): string {
  switch (status) {
    case "pending":
      return "#888888";
    case "streaming":
      return "yellow";
    case "done":
      return "green";
    case "error":
      return "red";
  }
}

export function ProposalList({ proposals }: ProposalListProps) {
  const hasErrors = proposals.some((p) => p.status === "error");
  const doneCount = proposals.filter((p) => p.status === "done").length;
  const streaming = proposals.filter((p) => p.status === "streaming");
  const anyStreaming = streaming.length > 0;
  const listStartedAt = anyStreaming
    ? (streaming.find((p) => p.startedAt != null)?.startedAt ?? null)
    : null;
  const elapsedSeconds = useElapsedSeconds(listStartedAt, anyStreaming);

  return (
    <box flexDirection="column" gap={1}>
      <text>
        <strong>Proposals</strong>
      </text>
      {hasErrors ? (
        <text fg={DIM}>
          consensus used {doneCount} of {proposals.length} proposers
        </text>
      ) : null}
      {proposals.map((proposal) => (
        <box key={proposal.id} flexDirection="row" gap={1}>
          <text fg={statusColor(proposal.status)}>
            {`[${statusLabel(
              proposal.status,
              proposal.status === "streaming" ? elapsedSeconds : null,
            )}]`}
          </text>
          <text>{proposal.label}</text>
          {proposal.error ? (
            <text fg="red">— {proposal.error}</text>
          ) : null}
        </box>
      ))}
    </box>
  );
}
