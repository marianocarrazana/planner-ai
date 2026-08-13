import {
  formatElapsedSeconds,
  useElapsedSeconds,
} from "./useElapsedSeconds.js";

interface ConsensusViewProps {
  writing?: boolean;
  startedAt?: number | null;
}

const DIM = "#888888";

export function ConsensusView({
  writing = false,
  startedAt = null,
}: ConsensusViewProps) {
  const elapsedSeconds = useElapsedSeconds(startedAt, !writing && startedAt != null);

  return (
    <box flexDirection="column" gap={1}>
      <text>
        <strong>{writing ? "Writing plan" : "Consensus"}</strong>
      </text>
      <text fg={DIM}>
        {writing
          ? "Saving plan.md…"
          : elapsedSeconds != null
            ? `Reconciling proposals into one plan… ${formatElapsedSeconds(elapsedSeconds)}`
            : "Reconciling proposals into one plan…"}
      </text>
    </box>
  );
}
