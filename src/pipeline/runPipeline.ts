import type {
  ConsensusProvider,
  ModelProvider,
  ProviderCallOptions,
} from "../providers/types.js";
import { writePlan } from "../writePlan.js";
import { writeRunArchive } from "../writeRunArchive.js";
import type {
  PipelineCallbacks,
  PipelineResult,
  ProposalState,
} from "./types.js";

export async function runPipeline(
  goal: string,
  proposers: ModelProvider[],
  consensus: ConsensusProvider,
  callbacks: PipelineCallbacks,
  options?: ProviderCallOptions,
): Promise<PipelineResult> {
  const trimmed = goal.trim();
  if (!trimmed) {
    callbacks.onPhase("error");
    throw new Error("Goal is required");
  }

  let proposals: ProposalState[] = proposers.map((p) => ({
    id: p.id,
    label: p.label,
    status: "pending",
  }));

  const emit = () => callbacks.onProposals(proposals.map((p) => ({ ...p })));

  callbacks.onPhase("proposing");
  emit();

  const streamingStartedAt = Date.now();
  proposals = proposals.map((p) => ({
    ...p,
    status: "streaming",
    startedAt: streamingStartedAt,
  }));
  emit();

  const settled = await Promise.allSettled(
    proposers.map(async (provider) => {
      const body = await provider.propose(trimmed, options);
      return { id: provider.id, body };
    }),
  );

  proposals = proposals.map((proposal, index) => {
    const result = settled[index]!;
    if (result.status === "fulfilled") {
      return {
        ...proposal,
        status: "done",
        body: result.value.body,
        startedAt: undefined,
      };
    }
    return {
      ...proposal,
      status: "error",
      error: result.reason instanceof Error ? result.reason.message : String(result.reason),
      startedAt: undefined,
    };
  });
  emit();

  const successful = proposals
    .filter((p) => p.status === "done" && p.body)
    .map((p) => ({ id: p.id, body: p.body! }));

  if (successful.length === 0) {
    callbacks.onPhase("error");
    throw new Error("All proposals failed");
  }

  callbacks.onPhase("consensus");
  callbacks.onConsensusStarted?.(Date.now());
  const plan = await consensus.reconcile(trimmed, successful, options);

  callbacks.onPhase("writing");
  const planPath = await writePlan(plan);
  await writeRunArchive({ plan, proposals });

  callbacks.onPhase("done");
  return { planPath, plan, proposals };
}
