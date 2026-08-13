import { Cursor } from "@cursor/sdk";

export type ProviderKind = "anthropic" | "cursor" | "mock";

export interface ModelChoice {
  provider: ProviderKind;
  modelId: string;
  label: string;
}

export interface ModelPick {
  provider: ProviderKind;
  modelId: string;
}

export interface ModelSelection {
  proposers: ModelPick[];
  consensus: ModelPick;
}

export interface ProviderCredentialsForModels {
  claudeCodeOAuthToken?: string;
  cursorApiKey?: string;
}

const CURSOR_FALLBACK_MODELS: ModelChoice[] = [
  {
    provider: "cursor",
    modelId: "composer-2.5",
    label: "Composer 2.5",
  },
  {
    provider: "cursor",
    modelId: "auto",
    label: "Cursor Auto",
  },
];

const MOCK_MODELS: ModelChoice[] = [
  { provider: "mock", modelId: "alpha", label: "Model Alpha (mock)" },
  { provider: "mock", modelId: "beta", label: "Model Beta (mock)" },
  { provider: "mock", modelId: "gamma", label: "Model Gamma (mock)" },
];

function nonEmpty(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function choiceKey(choice: ModelPick): string {
  return `${choice.provider}:${choice.modelId}`;
}

function sourceLabel(provider: ProviderKind): string {
  switch (provider) {
    case "anthropic":
      return "claude";
    case "cursor":
      return "cursor";
    case "mock":
      return "mock";
  }
}

export function formatChoiceLabel(choice: ModelChoice): string {
  return `${choice.label} · ${sourceLabel(choice.provider)} · ${choice.modelId}`;
}

export function findChoiceLabel(
  choices: ModelChoice[],
  pick: ModelPick,
): string {
  const found = choices.find(
    (c) => c.provider === pick.provider && c.modelId === pick.modelId,
  );
  return found?.label ?? `${pick.provider}:${pick.modelId}`;
}

interface AnthropicModelsPage {
  data?: unknown[];
  has_more?: boolean;
  last_id?: string | null;
}

function anthropicModelChoice(raw: unknown): ModelChoice | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const id = typeof obj.id === "string" ? obj.id.trim() : "";
  if (!id) return null;
  const displayName =
    typeof obj.display_name === "string" && obj.display_name.trim()
      ? obj.display_name.trim()
      : id;
  return { provider: "anthropic", modelId: id, label: displayName };
}

/** List Claude models via Anthropic Models API using a Claude Code OAuth token. */
export async function loadAnthropicChoices(
  oauthToken: string,
): Promise<ModelChoice[]> {
  try {
    const listed: ModelChoice[] = [];
    const seen = new Set<string>();
    let afterId: string | undefined;

    for (;;) {
      const url = new URL("https://api.anthropic.com/v1/models");
      url.searchParams.set("limit", "1000");
      if (afterId) url.searchParams.set("after_id", afterId);

      const res = await fetch(url, {
        method: "GET",
        headers: {
          "anthropic-version": "2023-06-01",
          "anthropic-beta": "oauth-2025-04-20",
          Authorization: `Bearer ${oauthToken}`,
        },
      });

      if (!res.ok) {
        return [];
      }

      const page = (await res.json()) as AnthropicModelsPage;
      const rows = Array.isArray(page.data) ? page.data : [];

      for (const row of rows) {
        const choice = anthropicModelChoice(row);
        if (!choice || seen.has(choice.modelId)) continue;
        seen.add(choice.modelId);
        listed.push(choice);
      }

      if (!page.has_more) break;
      const next =
        typeof page.last_id === "string" && page.last_id.trim()
          ? page.last_id.trim()
          : undefined;
      if (!next || next === afterId) break;
      afterId = next;
    }

    return listed;
  } catch {
    return [];
  }
}

export async function loadCursorChoices(
  apiKey: string,
): Promise<ModelChoice[]> {
  try {
    const models = await Cursor.models.list({ apiKey });
    const listed: ModelChoice[] = [];
    const seen = new Set<string>();

    for (const model of models) {
      const id = typeof model?.id === "string" ? model.id.trim() : "";
      if (!id || seen.has(id)) continue;
      seen.add(id);
      const displayName =
        typeof model?.displayName === "string" && model.displayName.trim()
          ? model.displayName.trim()
          : id;
      listed.push({
        provider: "cursor",
        modelId: id,
        label: displayName,
      });
    }

    if (listed.length === 0) {
      return CURSOR_FALLBACK_MODELS;
    }

    for (const fallback of CURSOR_FALLBACK_MODELS) {
      if (!seen.has(fallback.modelId)) {
        listed.push(fallback);
      }
    }

    return listed;
  } catch {
    return CURSOR_FALLBACK_MODELS;
  }
}

export async function availableChoices(
  creds: ProviderCredentialsForModels,
  opts?: { includeMocks?: boolean },
): Promise<ModelChoice[]> {
  const claudeToken = nonEmpty(creds.claudeCodeOAuthToken);
  const cursorKey = nonEmpty(creds.cursorApiKey);
  const choices: ModelChoice[] = [];

  if (claudeToken) {
    choices.push(...(await loadAnthropicChoices(claudeToken)));
  }

  if (cursorKey) {
    choices.push(...(await loadCursorChoices(cursorKey)));
  }

  const showMocks =
    opts?.includeMocks === true || (!claudeToken && !cursorKey);
  if (showMocks) {
    choices.push(...MOCK_MODELS);
  }

  return choices;
}

export function defaultSelection(
  choices: ModelChoice[],
): ModelSelection | null {
  const anthropic = choices.filter((c) => c.provider === "anthropic");
  const cursor = choices.filter((c) => c.provider === "cursor");
  const mock = choices.filter((c) => c.provider === "mock");

  const proposers: ModelPick[] = [];

  if (anthropic[0]) {
    proposers.push({
      provider: anthropic[0].provider,
      modelId: anthropic[0].modelId,
    });
  }
  if (cursor[0]) {
    proposers.push({
      provider: cursor[0].provider,
      modelId: cursor[0].modelId,
    });
  }
  if (proposers.length === 0 && mock[0]) {
    proposers.push(
      ...mock.slice(0, 2).map((c) => ({
        provider: c.provider,
        modelId: c.modelId,
      })),
    );
  }

  if (proposers.length === 0) return null;

  let consensus: ModelPick;
  if (anthropic[0]) {
    consensus = {
      provider: anthropic[0].provider,
      modelId: anthropic[0].modelId,
    };
  } else if (cursor[0]) {
    consensus = {
      provider: cursor[0].provider,
      modelId: cursor[0].modelId,
    };
  } else {
    consensus = {
      provider: mock[0]!.provider,
      modelId: mock[0]!.modelId,
    };
  }

  return { proposers, consensus };
}

export function normalizeSelection(
  raw: unknown,
  choices: ModelChoice[],
): ModelSelection | null {
  if (!raw || typeof raw !== "object") return null;

  const obj = raw as Record<string, unknown>;
  const allowed = new Set(choices.map(choiceKey));

  const proposersRaw = obj.proposers;
  if (!Array.isArray(proposersRaw)) return null;

  const proposers: ModelPick[] = [];
  for (const item of proposersRaw) {
    const pick = normalizePick(item);
    if (!pick) continue;
    if (!allowed.has(choiceKey(pick))) continue;
    if (proposers.some((p) => choiceKey(p) === choiceKey(pick))) continue;
    proposers.push(pick);
  }

  const consensus = normalizePick(obj.consensus);
  if (!consensus || !allowed.has(choiceKey(consensus))) return null;
  if (proposers.length === 0) return null;

  return { proposers, consensus };
}

function normalizePick(raw: unknown): ModelPick | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const provider = obj.provider;
  const modelId = obj.modelId;

  if (
    provider !== "anthropic" &&
    provider !== "cursor" &&
    provider !== "mock"
  ) {
    return null;
  }
  if (typeof modelId !== "string" || !modelId.trim()) return null;

  return { provider, modelId: modelId.trim() };
}

export function resolveInitialSelection(
  saved: unknown,
  choices: ModelChoice[],
): ModelSelection {
  return (
    normalizeSelection(saved, choices) ??
    defaultSelection(choices) ?? {
      proposers: [{ provider: "mock", modelId: "alpha" }],
      consensus: { provider: "mock", modelId: "alpha" },
    }
  );
}
