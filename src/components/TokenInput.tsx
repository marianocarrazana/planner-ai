import { useKeyboard, usePaste } from "@opentui/react";
import { useState } from "react";

interface TokenInputProps {
  label: string;
  hint?: string;
  onSubmit: (value: string) => void;
}

const DIM = "#888888";

function pasteText(event: { text?: string; bytes?: Uint8Array }): string {
  if (typeof event.text === "string") return event.text;
  if (event.bytes) return new TextDecoder().decode(event.bytes);
  return "";
}

/** Masked token field — OpenTUI input has no password type in current release. */
export function TokenInput({ label, hint, onSubmit }: TokenInputProps) {
  const [value, setValue] = useState("");

  usePaste((event) => {
    const text = pasteText(event).replace(/\r?\n/g, "");
    if (text) setValue((prev) => prev + text);
  });

  useKeyboard((key) => {
    if (key.ctrl || key.meta) return;

    if (key.name === "return") {
      onSubmit(value.trim());
      return;
    }

    if (key.name === "backspace") {
      setValue((prev) => prev.slice(0, -1));
      return;
    }

    if (key.name === "space") {
      setValue((prev) => `${prev} `);
      return;
    }

    if (key.sequence && key.name.length === 1 && !key.ctrl && !key.meta) {
      setValue((prev) => prev + key.sequence);
    }
  });

  const masked = value.length > 0 ? "*".repeat(value.length) : "";

  return (
    <box flexDirection="column" gap={1}>
      <text>{label}</text>
      {hint ? <text fg={DIM}>{hint}</text> : null}
      <box flexDirection="row">
        <text fg={DIM}>{"> "}</text>
        <text>
          {masked}
          <span fg="cyan">█</span>
        </text>
        {value.length === 0 ? (
          <text fg={DIM}>Enter to skip…</text>
        ) : null}
      </box>
    </box>
  );
}
