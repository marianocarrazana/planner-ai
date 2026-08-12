import { useState } from "react";

interface GoalInputProps {
  onSubmit: (goal: string) => void;
}

const DIM = "#888888";

export function GoalInput({ onSubmit }: GoalInputProps) {
  const [value, setValue] = useState("");

  return (
    <box flexDirection="column" gap={1}>
      <text>What goal should we plan for?</text>
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
          placeholder="Describe the goal…"
        />
      </box>
    </box>
  );
}
