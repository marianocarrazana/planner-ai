export type Phase =
  | "idle"
  | "proposing"
  | "consensus"
  | "writing"
  | "done"
  | "error";

export type ProposalStatus = "pending" | "streaming" | "done" | "error";

export interface ProposalState {
  id: string;
  label: string;
  status: ProposalStatus;
  body?: string;
  error?: string;
}

export interface PipelineResult {
  planPath: string;
  plan: string;
  proposals: ProposalState[];
}

export interface PipelineCallbacks {
  onPhase: (phase: Phase) => void;
  onProposals: (proposals: ProposalState[]) => void;
}
