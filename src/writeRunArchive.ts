import { access, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import type { ProposalState, RunMode } from "./pipeline/types.js";
import { getWorkspaceCwd } from "./workspace.js";

export const ARCHIVE_DIR = ".planner-ai";
export const PLAN_FILENAME = "plan.md";
export const ANSWER_FILENAME = "answer.md";
export const OUTPUT_SUFFIX = "-output.md";

export function formatRunTimestamp(date: Date = new Date()): string {
  const y = date.getFullYear();
  const mo = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const h = String(date.getHours()).padStart(2, "0");
  const mi = String(date.getMinutes()).padStart(2, "0");
  const s = String(date.getSeconds()).padStart(2, "0");
  return `${y}-${mo}-${d}T${h}-${mi}-${s}`;
}

export function sanitizeModelId(id: string): string {
  return id.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "model";
}

export function primaryDocFilename(kind: RunMode): string {
  return kind === "ask" ? ANSWER_FILENAME : PLAN_FILENAME;
}

async function pathExists(target: string): Promise<boolean> {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

async function allocateRunDir(
  archiveRoot: string,
  kind: RunMode,
  timestamp: string,
): Promise<string> {
  let candidate = path.join(archiveRoot, `${kind}-${timestamp}`);
  if (!(await pathExists(candidate))) {
    return candidate;
  }
  for (let n = 2; ; n++) {
    candidate = path.join(archiveRoot, `${kind}-${timestamp}-${n}`);
    if (!(await pathExists(candidate))) {
      return candidate;
    }
  }
}

function proposalBody(proposal: ProposalState): string {
  if (proposal.status === "done" && proposal.body) {
    return proposal.body;
  }
  const message = proposal.error?.trim() || "Proposal failed with no error message";
  return `# Error\n\n${message}\n`;
}

export interface WriteRunArchiveInput {
  kind: RunMode;
  plan: string;
  proposals: ProposalState[];
  cwd?: string;
  date?: Date;
}

export async function writeRunArchive({
  kind,
  plan,
  proposals,
  cwd = getWorkspaceCwd(),
  date = new Date(),
}: WriteRunArchiveInput): Promise<string> {
  const archiveRoot = path.join(cwd, ARCHIVE_DIR);
  await mkdir(archiveRoot, { recursive: true });

  const runDir = await allocateRunDir(
    archiveRoot,
    kind,
    formatRunTimestamp(date),
  );
  await mkdir(runDir, { recursive: true });

  for (const proposal of proposals) {
    const filename = `${sanitizeModelId(proposal.id)}-output.md`;
    await writeFile(path.join(runDir, filename), proposalBody(proposal), "utf8");
  }

  await writeFile(path.join(runDir, primaryDocFilename(kind)), plan, "utf8");
  return runDir;
}
