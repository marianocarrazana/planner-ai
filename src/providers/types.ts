export interface ModelProvider {
  id: string;
  label: string;
  propose(goal: string): Promise<string>;
}

export interface ConsensusProvider {
  reconcile(
    goal: string,
    proposals: { id: string; body: string }[],
  ): Promise<string>;
}
