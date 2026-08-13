import { access, copyFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { getWorkspaceCwd } from "./workspace.js";

const PLAN_FILENAME = "plan.md";
const PLAN_BAK_FILENAME = "plan.md.bak";

export async function writePlan(
  plan: string,
  cwd: string = getWorkspaceCwd(),
): Promise<string> {
  const planPath = path.join(cwd, PLAN_FILENAME);
  const bakPath = path.join(cwd, PLAN_BAK_FILENAME);
  try {
    await access(planPath);
    await copyFile(planPath, bakPath);
  } catch {
    // no existing plan.md
  }
  await writeFile(planPath, plan, "utf8");
  return planPath;
}
