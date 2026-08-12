import { useKeyboard, useRenderer } from "@opentui/react";

interface DoneViewProps {
  planPath: string;
}

const DIM = "#888888";

export function DoneView({ planPath }: DoneViewProps) {
  const renderer = useRenderer();

  useKeyboard((key) => {
    if (key.name === "q" || key.name === "return" || key.name === "escape") {
      renderer.destroy();
    }
  });

  return (
    <box flexDirection="column" gap={1}>
      <text fg="green">
        <strong>Plan ready</strong>
      </text>
      <text>
        Wrote <span fg="cyan">{planPath}</span>
      </text>
      <text fg={DIM}>Press Enter or q to exit</text>
    </box>
  );
}
