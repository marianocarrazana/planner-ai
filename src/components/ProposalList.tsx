import type { ProposalState } from "../pipeline/types.js";

interface ProposalListProps {
  proposals: ProposalState[];
}

function statusLabel(status: ProposalState["status"]): string {
  switch (status) {
    case "pending":
      return "pending";
    case "streaming":
      return "working…";
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
  return (
    <box flexDirection="column" gap={1}>
      <text>
        <strong>Proposals</strong>
      </text>
      {proposals.map((proposal) => (
        <box key={proposal.id} flexDirection="row" gap={1}>
          <text fg={statusColor(proposal.status)}>
            [{statusLabel(proposal.status)}]
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
