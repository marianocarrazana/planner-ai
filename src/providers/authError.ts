import type { ConfigCredentialKey } from "../config.js";
import type { ProposalState } from "../pipeline/types.js";

const AUTH_ERROR_PATTERNS = [
  /invalid auth/i,
  /unauthorized/i,
  /\b401\b/,
  /invalid authorization/i,
  /invalid api key/i,
  /expired token/i,
  /authentication/i,
  /fix external auth/i,
];

export function isAuthErrorMessage(message: string): boolean {
  return AUTH_ERROR_PATTERNS.some((pattern) => pattern.test(message));
}

export function credentialKeyForProvider(
  kind: string,
): ConfigCredentialKey | null {
  const base = kind.includes(":") ? kind.slice(0, kind.indexOf(":")) : kind;
  switch (base) {
    case "anthropic":
      return "claudeCodeOAuthToken";
    case "cursor":
      return "cursorApiKey";
    case "codex":
      return "codexApiKey";
    default:
      return null;
  }
}

export function collectFailingCredentialKeys(input: {
  proposals: ProposalState[];
  errorMessage: string;
  consensusSource: string;
}): ConfigCredentialKey[] {
  const keys = new Set<ConfigCredentialKey>();

  for (const proposal of input.proposals) {
    if (proposal.status !== "error" || !proposal.error) continue;
    if (!isAuthErrorMessage(proposal.error)) continue;
    const key = credentialKeyForProvider(proposal.id);
    if (key) keys.add(key);
  }

  if (isAuthErrorMessage(input.errorMessage)) {
    const key = credentialKeyForProvider(input.consensusSource);
    if (key) keys.add(key);

    // Top-level errors often come from a proposer (e.g. "All proposals failed"
    // is not auth-like, but the thrown SDK message can be). Map by message alone
    // when consensus source is mock but a real provider failed auth.
    if (keys.size === 0) {
      if (/claude|anthropic|CLAUDE_CODE_OAUTH/i.test(input.errorMessage)) {
        keys.add("claudeCodeOAuthToken");
      }
      if (/cursor/i.test(input.errorMessage)) {
        keys.add("cursorApiKey");
      }
      if (/codex|openai|CODEX_API_KEY/i.test(input.errorMessage)) {
        keys.add("codexApiKey");
      }
    }
  }

  return [...keys];
}
