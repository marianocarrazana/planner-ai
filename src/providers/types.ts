import type { RunMode } from "../pipeline/types.js";

export type ProviderCallOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
  /** Defaults to "plan" when omitted. */
  mode?: RunMode;
};

export interface ModelProvider {
  id: string;
  label: string;
  propose(goal: string, options?: ProviderCallOptions): Promise<string>;
}

export interface ConsensusProvider {
  reconcile(
    goal: string,
    proposals: { id: string; body: string }[],
    options?: ProviderCallOptions,
  ): Promise<string>;
}
