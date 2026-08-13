import { useState } from "react";
import type { RunMode } from "../pipeline/types.js";
import { Clickable } from "./Clickable.js";

interface GoalInputProps {
  mode: RunMode;
  onModeChange: (mode: RunMode) => void;
  onSubmit: (goal: string) => void;
}

const DIM = "#888888";

export function GoalInput({ mode, onModeChange, onSubmit }: GoalInputProps) {
  const [value, setValue] = useState("");

  return (
    <box flexDirection="column" gap={1}>
      <box flexDirection="row" gap={2}>
        {(["plan", "ask"] as const).map((id) => {
          const selected = mode === id;
          const label = id === "plan" ? "Plan" : "Ask";
          return (
            <Clickable key={id} onClick={() => onModeChange(id)}>
              <text
                fg={selected ? "black" : DIM}
                bg={selected ? "cyan" : undefined}
              >
                {` ${label} `}
              </text>
            </Clickable>
          );
        })}
      </box>
      <text>
        {mode === "ask"
          ? "What do you want to ask?"
          : "What goal should we plan for?"}
      </text>
      <box flexDirection="row" gap={0}>
        <text fg={DIM}>{"> "}</text>
        <input
          focused
          flexGrow={1}
          value={value}
          onInput={setValue}
          onSubmit={() => {
            const trimmed = value.trim();
            if (trimmed) onSubmit(trimmed);
          }}
          placeholder={
            mode === "ask" ? "Ask a question…" : "Describe the goal…"
          }
        />
      </box>
    </box>
  );
}
