import {
  formatElapsedSeconds,
  useElapsedSeconds,
} from "./useElapsedSeconds.js";
import type { RunMode } from "../pipeline/types.js";

interface ConsensusViewProps {
  mode?: RunMode;
  writing?: boolean;
  startedAt?: number | null;
}

const DIM = "#888888";

export function ConsensusView({
  mode = "plan",
  writing = false,
  startedAt = null,
}: ConsensusViewProps) {
  const elapsedSeconds = useElapsedSeconds(startedAt, !writing && startedAt != null);
  const isAsk = mode === "ask";

  return (
    <box flexDirection="column" gap={1}>
      <text>
        <strong>
          {writing
            ? isAsk
              ? "Saving answer"
              : "Writing plan"
            : "Consensus"}
        </strong>
      </text>
      <text fg={DIM}>
        {writing
          ? isAsk
            ? "Archiving answer…"
            : "Saving plan.md…"
          : elapsedSeconds != null
            ? isAsk
              ? `Reconciling answers into one response… ${formatElapsedSeconds(elapsedSeconds)}`
              : `Reconciling proposals into one plan… ${formatElapsedSeconds(elapsedSeconds)}`
            : isAsk
              ? "Reconciling answers into one response…"
              : "Reconciling proposals into one plan…"}
      </text>
    </box>
  );
}
