import { useKeyboard } from "@opentui/react";
import { useState } from "react";
import type { AppConfig, ConfigCredentialKey } from "../config.js";
import { Clickable } from "./Clickable.js";
import { TokenInput } from "./TokenInput.js";

type AuthMode = "overview" | "claude" | "cursor";

interface AuthScreenProps {
  config: AppConfig;
  onSaveClaude: (token: string) => void;
  onSaveCursor: (token: string) => void;
  onClear: (keys: ConfigCredentialKey[]) => void;
}

const DIM = "#888888";

function statusLine(label: string, set: boolean): string {
  return `${label}: ${set ? "set" : "missing"}`;
}

export function AuthScreen({
  config,
  onSaveClaude,
  onSaveCursor,
  onClear,
}: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>("overview");
  const [cursor, setCursor] = useState(0);

  const hasClaude = Boolean(config.claudeCodeOAuthToken);
  const hasCursor = Boolean(config.cursorApiKey);

  const overviewActions = [
    {
      id: "edit-claude",
      label: hasClaude ? "Edit Claude OAuth token" : "Set Claude OAuth token",
      run: () => setMode("claude"),
    },
    {
      id: "edit-cursor",
      label: hasCursor ? "Edit Cursor API key" : "Set Cursor API key",
      run: () => setMode("cursor"),
    },
    {
      id: "clear-claude",
      label: "Clear Claude token",
      disabled: !hasClaude,
      run: () => onClear(["claudeCodeOAuthToken"]),
    },
    {
      id: "clear-cursor",
      label: "Clear Cursor key",
      disabled: !hasCursor,
      run: () => onClear(["cursorApiKey"]),
    },
    {
      id: "clear-both",
      label: "Clear both credentials",
      disabled: !hasClaude && !hasCursor,
      run: () => onClear(["claudeCodeOAuthToken", "cursorApiKey"]),
    },
  ] as const;

  const maxCursor = overviewActions.length - 1;

  useKeyboard((key) => {
    if (mode !== "overview") return;

    if (key.name === "up") {
      setCursor((prev) => Math.max(0, prev - 1));
      return;
    }
    if (key.name === "down") {
      setCursor((prev) => Math.min(maxCursor, prev + 1));
      return;
    }
    if (key.name === "return" || key.name === "space") {
      const action = overviewActions[cursor];
      if (action && !("disabled" in action && action.disabled)) {
        action.run();
      }
    }
  });

  if (mode === "claude") {
    return (
      <box flexDirection="column" gap={1}>
        <TokenInput
          label="Claude Code OAuth token"
          hint="Run `claude setup-token`, then paste. Enter empty to cancel."
          onSubmit={(value) => {
            if (value) onSaveClaude(value);
            setMode("overview");
          }}
        />
        <Clickable onClick={() => setMode("overview")}>
          <text fg={DIM}>← Back to Auth overview</text>
        </Clickable>
      </box>
    );
  }

  if (mode === "cursor") {
    return (
      <box flexDirection="column" gap={1}>
        <TokenInput
          label="Cursor API key"
          hint="From Cursor Dashboard → Integrations. Enter empty to cancel."
          onSubmit={(value) => {
            if (value) onSaveCursor(value);
            setMode("overview");
          }}
        />
        <Clickable onClick={() => setMode("overview")}>
          <text fg={DIM}>← Back to Auth overview</text>
        </Clickable>
      </box>
    );
  }

  return (
    <box flexDirection="column" gap={1}>
      <text>
        <strong>Auth</strong>
      </text>
      <text fg={DIM}>Tokens are stored in your local planner-ai config.</text>
      <text fg={hasClaude ? "green" : "yellow"}>
        {statusLine("Claude OAuth", hasClaude)}
      </text>
      <text fg={hasCursor ? "green" : "yellow"}>
        {statusLine("Cursor API key", hasCursor)}
      </text>

      <box flexDirection="column" gap={0}>
        {overviewActions.map((action, index) => {
          const disabled = "disabled" in action && action.disabled;
          const focused = cursor === index;
          return (
            <Clickable
              key={action.id}
              onClick={() => {
                setCursor(index);
                if (!disabled) action.run();
              }}
            >
              <text
                fg={
                  disabled
                    ? DIM
                    : focused
                      ? "black"
                      : undefined
                }
                bg={focused && !disabled ? "cyan" : undefined}
              >
                {focused ? "> " : "  "}
                {action.label}
              </text>
            </Clickable>
          );
        })}
      </box>

      <text fg={DIM}>↑↓ move · Enter/Space activate · Ctrl+1/2/3 switch tabs</text>
    </box>
  );
}
