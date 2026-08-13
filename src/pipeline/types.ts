export type RunMode = "plan" | "ask";

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
  /** Epoch ms when this proposer entered "streaming"; used for elapsed UI. */
  startedAt?: number;
}

export interface PipelineResult {
  /** Workspace plan.md path in plan mode; null in ask mode. */
  planPath: string | null;
  /** Archive directory under .planner-ai/. */
  archivePath: string;
  /** Consensus markdown (plan or answer). */
  plan: string;
  mode: RunMode;
  proposals: ProposalState[];
}

export interface PipelineCallbacks {
  onPhase: (phase: Phase) => void;
  onProposals: (proposals: ProposalState[]) => void;
  onConsensusStarted?: (startedAt: number) => void;
}
