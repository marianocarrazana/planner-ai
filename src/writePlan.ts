import { writeFile } from "node:fs/promises";
import path from "node:path";
import { getWorkspaceCwd } from "./workspace.js";

const PLAN_FILENAME = "plan.md";

export async function writePlan(
  plan: string,
  cwd: string = getWorkspaceCwd(),
): Promise<string> {
  const planPath = path.join(cwd, PLAN_FILENAME);
  await writeFile(planPath, plan, "utf8");
  return planPath;
}
