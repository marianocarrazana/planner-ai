interface ConsensusViewProps {
  writing?: boolean;
}

const DIM = "#888888";

export function ConsensusView({ writing = false }: ConsensusViewProps) {
  return (
    <box flexDirection="column" gap={1}>
      <text>
        <strong>{writing ? "Writing plan" : "Consensus"}</strong>
      </text>
      <text fg={DIM}>
        {writing
          ? "Saving plan.md…"
          : "Reconciling proposals into one plan…"}
      </text>
    </box>
  );
}
