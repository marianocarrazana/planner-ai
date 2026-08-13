import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import type { ProposalState } from "./pipeline/types.js";
import {
  ARCHIVE_DIR,
  OUTPUT_SUFFIX,
  PLAN_FILENAME,
} from "./writeRunArchive.js";
import { getWorkspaceCwd } from "./workspace.js";

const RUN_DIR_RE =
  /^plan-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})(?:-(\d+))?$/;

export interface ArchivedRunSummary {
  id: string;
  dirName: string;
  path: string;
  timestampLabel: string;
  outputCount: number;
}

export interface ArchivedRun {
  path: string;
  plan: string;
  proposals: ProposalState[];
}

function formatTimestampLabel(dirName: string): string {
  const match = RUN_DIR_RE.exec(dirName);
  if (!match?.[1]) return dirName;
  const [datePart, timePart = ""] = match[1].split("T");
  const label = `${datePart} ${timePart.replace(/-/g, ":")}`;
  return match[2] ? `${label} (${match[2]})` : label;
}

function isErrorBody(body: string): boolean {
  return body.startsWith("# Error\n");
}

function proposalFromOutput(
  filename: string,
  body: string,
): ProposalState {
  const stem = filename.endsWith(OUTPUT_SUFFIX)
    ? filename.slice(0, -OUTPUT_SUFFIX.length)
    : filename.replace(/\.md$/, "");
  const id = stem || "model";
  if (isErrorBody(body)) {
    const message = body.replace(/^# Error\n\n?/, "").trim() || body.trim();
    return { id, label: id, status: "error", error: message };
  }
  return { id, label: id, status: "done", body };
}

export async function listArchivedRuns(
  cwd: string = getWorkspaceCwd(),
): Promise<ArchivedRunSummary[]> {
  const archiveRoot = path.join(cwd, ARCHIVE_DIR);
  let entries;
  try {
    entries = await readdir(archiveRoot, { withFileTypes: true });
  } catch (err) {
    const code =
      err && typeof err === "object" && "code" in err
        ? (err as { code?: string }).code
        : undefined;
    if (code === "ENOENT") return [];
    throw err;
  }

  const runs: ArchivedRunSummary[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || !RUN_DIR_RE.test(entry.name)) continue;
    const runPath = path.join(archiveRoot, entry.name);
    let outputCount = 0;
    try {
      const files = await readdir(runPath);
      outputCount = files.filter((f) => f.endsWith(OUTPUT_SUFFIX)).length;
    } catch {
      // Still list the run; detail view can surface read errors.
    }
    runs.push({
      id: entry.name,
      dirName: entry.name,
      path: runPath,
      timestampLabel: formatTimestampLabel(entry.name),
      outputCount,
    });
  }

  runs.sort((a, b) => (a.dirName < b.dirName ? 1 : a.dirName > b.dirName ? -1 : 0));
  return runs;
}

export async function readArchivedRun(runDir: string): Promise<ArchivedRun> {
  const planPath = path.join(runDir, PLAN_FILENAME);
  let plan = "";
  try {
    plan = await readFile(planPath, "utf8");
  } catch (err) {
    const code =
      err && typeof err === "object" && "code" in err
        ? (err as { code?: string }).code
        : undefined;
    if (code !== "ENOENT") throw err;
  }

  let files: string[] = [];
  try {
    files = await readdir(runDir);
  } catch (err) {
    const code =
      err && typeof err === "object" && "code" in err
        ? (err as { code?: string }).code
        : undefined;
    if (code === "ENOENT") {
      throw new Error(`Archived run not found: ${runDir}`);
    }
    throw err;
  }

  const outputFiles = files
    .filter((f) => f.endsWith(OUTPUT_SUFFIX))
    .sort((a, b) => a.localeCompare(b));

  const proposals: ProposalState[] = [];
  for (const filename of outputFiles) {
    try {
      const body = await readFile(path.join(runDir, filename), "utf8");
      proposals.push(proposalFromOutput(filename, body));
    } catch {
      const stem = filename.slice(0, -OUTPUT_SUFFIX.length) || "model";
      proposals.push({
        id: stem,
        label: stem,
        status: "error",
        error: `Failed to read ${filename}`,
      });
    }
  }

  return { path: runDir, plan, proposals };
}
