import { mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import type { ModelSelection, ProviderKind } from "./providers/models.js";

export interface AppConfig {
  claudeCodeOAuthToken?: string;
  cursorApiKey?: string;
  modelSelection?: ModelSelection;
  /** When true, show mock models even if real credentials are set. */
  includeMocks?: boolean;
}

export type ConfigCredentialKey = "claudeCodeOAuthToken" | "cursorApiKey";

const APP_NAME = "planner-ai";
const CONFIG_FILENAME = "config.json";

export function getConfigDir(): string {
  switch (process.platform) {
    case "darwin":
      return path.join(
        os.homedir(),
        "Library",
        "Application Support",
        APP_NAME,
      );
    case "win32":
      return path.join(
        process.env.APPDATA ?? path.join(os.homedir(), "AppData", "Roaming"),
        APP_NAME,
      );
    default: {
      const xdg = process.env.XDG_CONFIG_HOME?.trim();
      const base = xdg || path.join(os.homedir(), ".config");
      return path.join(base, APP_NAME);
    }
  }
}

export function getConfigPath(): string {
  return path.join(getConfigDir(), CONFIG_FILENAME);
}

/** Strip all whitespace so pasted line breaks cannot poison Authorization headers. */
export function sanitizeToken(value: string): string {
  return value.replace(/\s+/g, "");
}

function fieldNeedsRewrite(raw: unknown): boolean {
  return typeof raw === "string" && sanitizeToken(raw) !== raw;
}

function isProviderKind(value: unknown): value is ProviderKind {
  return value === "anthropic" || value === "cursor" || value === "mock";
}

function normalizeModelSelection(raw: unknown): ModelSelection | undefined {
  if (!raw || typeof raw !== "object") return undefined;

  const obj = raw as Record<string, unknown>;
  if (!Array.isArray(obj.proposers)) return undefined;

  const proposers: ModelSelection["proposers"] = [];
  for (const item of obj.proposers) {
    if (!item || typeof item !== "object") continue;
    const pick = item as Record<string, unknown>;
    if (!isProviderKind(pick.provider)) continue;
    if (typeof pick.modelId !== "string" || !pick.modelId.trim()) continue;
    proposers.push({
      provider: pick.provider,
      modelId: pick.modelId.trim(),
    });
  }

  if (
    !obj.consensus ||
    typeof obj.consensus !== "object" ||
    proposers.length === 0
  ) {
    return undefined;
  }

  const consensus = obj.consensus as Record<string, unknown>;
  if (!isProviderKind(consensus.provider)) return undefined;
  if (typeof consensus.modelId !== "string" || !consensus.modelId.trim()) {
    return undefined;
  }

  return {
    proposers,
    consensus: {
      provider: consensus.provider,
      modelId: consensus.modelId.trim(),
    },
  };
}

function normalizeConfig(raw: unknown): AppConfig {
  if (!raw || typeof raw !== "object") {
    return {};
  }

  const obj = raw as Record<string, unknown>;
  const config: AppConfig = {};

  if (typeof obj.claudeCodeOAuthToken === "string") {
    const value = sanitizeToken(obj.claudeCodeOAuthToken);
    if (value) config.claudeCodeOAuthToken = value;
  }

  if (typeof obj.cursorApiKey === "string") {
    const value = sanitizeToken(obj.cursorApiKey);
    if (value) config.cursorApiKey = value;
  }

  const modelSelection = normalizeModelSelection(obj.modelSelection);
  if (modelSelection) {
    config.modelSelection = modelSelection;
  }

  if (obj.includeMocks === true) {
    config.includeMocks = true;
  }

  return config;
}

async function writeConfigFile(config: AppConfig): Promise<void> {
  const dir = getConfigDir();
  await mkdir(dir, { recursive: true });
  await writeFile(getConfigPath(), `${JSON.stringify(config, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
}

export async function loadConfig(): Promise<AppConfig> {
  try {
    const body = await readFile(getConfigPath(), "utf8");
    const parsed = JSON.parse(body) as unknown;
    const normalized = normalizeConfig(parsed);

    if (
      parsed &&
      typeof parsed === "object" &&
      (fieldNeedsRewrite(
        (parsed as Record<string, unknown>).claudeCodeOAuthToken,
      ) ||
        fieldNeedsRewrite((parsed as Record<string, unknown>).cursorApiKey))
    ) {
      await writeConfigFile(normalized);
    }

    return normalized;
  } catch (err) {
    if (
      err &&
      typeof err === "object" &&
      "code" in err &&
      (err as { code?: string }).code === "ENOENT"
    ) {
      return {};
    }
    throw err;
  }
}

export async function saveConfig(partial: AppConfig): Promise<AppConfig> {
  const current = await loadConfig();
  const next: AppConfig = { ...current };

  if (partial.claudeCodeOAuthToken !== undefined) {
    const value = sanitizeToken(partial.claudeCodeOAuthToken);
    if (value) {
      next.claudeCodeOAuthToken = value;
    } else {
      delete next.claudeCodeOAuthToken;
    }
  }

  if (partial.cursorApiKey !== undefined) {
    const value = sanitizeToken(partial.cursorApiKey);
    if (value) {
      next.cursorApiKey = value;
    } else {
      delete next.cursorApiKey;
    }
  }

  if (partial.modelSelection !== undefined) {
    next.modelSelection = partial.modelSelection;
  }

  if (partial.includeMocks !== undefined) {
    if (partial.includeMocks) {
      next.includeMocks = true;
    } else {
      delete next.includeMocks;
    }
  }

  await writeConfigFile(next);
  return next;
}

export async function clearCredentials(
  keys: ConfigCredentialKey[],
): Promise<AppConfig> {
  const partial: AppConfig = {};
  for (const key of keys) {
    partial[key] = "";
  }
  return saveConfig(partial);
}
