#!/usr/bin/env bun
import { createCliRenderer } from "@opentui/core";
import { createRoot } from "@opentui/react";
import { App } from "./app.js";
import { clearCredentials, getConfigPath } from "./config.js";

async function main(): Promise<void> {
  if (process.argv.includes("--reset-auth")) {
    await clearCredentials(["claudeCodeOAuthToken", "cursorApiKey"]);
    console.log(`Cleared credentials in ${getConfigPath()}`);
    return;
  }

  const renderer = await createCliRenderer({
    screenMode: "alternate-screen",
    useMouse: true,
    exitOnCtrlC: true,
  });
  createRoot(renderer).render(<App />);
}

void main();
