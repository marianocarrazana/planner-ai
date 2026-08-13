import {
  createAnthropicConsensus,
  createAnthropicProposer,
} from "./anthropic.js";
import {
  createCodexConsensus,
  createCodexProposer,
} from "./codex.js";
import {
  createCursorConsensus,
  createCursorProposer,
} from "./cursor.js";
import { mockConsensus, mockProposers } from "./mock.js";
import {
  findChoiceLabel,
  type ModelChoice,
  type ModelSelection,
  type ProviderKind,
} from "./models.js";
import type { ConsensusProvider, ModelProvider } from "./types.js";

export type { ProviderKind };

export interface ProviderCredentials {
  claudeCodeOAuthToken?: string;
  cursorApiKey?: string;
  codexApiKey?: string;
}

export interface ResolvedProviders {
  proposers: ModelProvider[];
  consensus: ConsensusProvider;
  sources: {
    proposers: string[];
    consensus: string;
  };
}

function nonEmpty(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function requireCreds(
  provider: ProviderKind,
  creds: ProviderCredentials,
): void {
  if (provider === "anthropic" && !nonEmpty(creds.claudeCodeOAuthToken)) {
    throw new Error("Selected Anthropic model but Claude OAuth token is missing");
  }
  if (provider === "cursor" && !nonEmpty(creds.cursorApiKey)) {
    throw new Error("Selected Cursor model but Cursor API key is missing");
  }
  if (provider === "codex" && !nonEmpty(creds.codexApiKey)) {
    throw new Error("Selected Codex model but Codex API key is missing");
  }
}

function createProposer(
  pick: ModelSelection["proposers"][number],
  creds: ProviderCredentials,
  choices: ModelChoice[],
): ModelProvider {
  requireCreds(pick.provider, creds);
  const label = findChoiceLabel(choices, pick);
  const id = `${pick.provider}:${pick.modelId}`;

  if (pick.provider === "anthropic") {
    return createAnthropicProposer(
      nonEmpty(creds.claudeCodeOAuthToken)!,
      pick.modelId,
      label,
    );
  }

  if (pick.provider === "cursor") {
    return createCursorProposer(
      nonEmpty(creds.cursorApiKey)!,
      pick.modelId,
      label,
    );
  }

  if (pick.provider === "codex") {
    return createCodexProposer(
      nonEmpty(creds.codexApiKey)!,
      pick.modelId,
      label,
    );
  }

  const mock = mockProposers.find((p) => p.id === pick.modelId);
  if (!mock) {
    throw new Error(`Unknown mock proposer: ${pick.modelId}`);
  }
  return {
    id,
    label,
    propose: mock.propose.bind(mock),
  };
}

function createConsensus(
  pick: ModelSelection["consensus"],
  creds: ProviderCredentials,
): ConsensusProvider {
  requireCreds(pick.provider, creds);

  if (pick.provider === "anthropic") {
    return createAnthropicConsensus(
      nonEmpty(creds.claudeCodeOAuthToken)!,
      pick.modelId,
    );
  }

  if (pick.provider === "cursor") {
    return createCursorConsensus(
      nonEmpty(creds.cursorApiKey)!,
      pick.modelId,
    );
  }

  if (pick.provider === "codex") {
    return createCodexConsensus(
      nonEmpty(creds.codexApiKey)!,
      pick.modelId,
    );
  }

  return mockConsensus;
}

export function resolveProviders(
  creds: ProviderCredentials = {},
  selection: ModelSelection,
  choices: ModelChoice[] = [],
): ResolvedProviders {
  if (selection.proposers.length === 0) {
    throw new Error("Select at least one proposer model");
  }

  const proposers = selection.proposers.map((pick) =>
    createProposer(pick, creds, choices),
  );
  const consensus = createConsensus(selection.consensus, creds);

  return {
    proposers,
    consensus,
    sources: {
      proposers: selection.proposers.map(
        (p) => `${p.provider}:${p.modelId}`,
      ),
      consensus: `${selection.consensus.provider}:${selection.consensus.modelId}`,
    },
  };
}
