import path from "node:path";

/** Absolute directory the CLI was launched in — same rule as Claude Code. */
export function getWorkspaceCwd(): string {
  return path.resolve(process.cwd());
}
