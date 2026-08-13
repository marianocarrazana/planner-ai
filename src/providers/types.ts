export type ProviderCallOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
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
