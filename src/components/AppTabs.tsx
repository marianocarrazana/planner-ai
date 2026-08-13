import { Clickable } from "./Clickable.js";

export type AppTab = "plan" | "proposers" | "consensus" | "auth" | "history";

interface AppTabsProps {
  active: AppTab;
  onChange: (tab: AppTab) => void;
}

const TABS: { id: AppTab; label: string }[] = [
  { id: "plan", label: "Plan" },
  { id: "proposers", label: "Proposers" },
  { id: "consensus", label: "Consensus" },
  { id: "auth", label: "Auth" },
  { id: "history", label: "History" },
];

const DIM = "#888888";

export function AppTabs({ active, onChange }: AppTabsProps) {
  return (
    <box flexDirection="column" gap={0}>
      <box flexDirection="row" gap={2}>
        {TABS.map((tab) => {
          const selected = tab.id === active;
          return (
            <Clickable key={tab.id} onClick={() => onChange(tab.id)}>
              <text
                fg={selected ? "black" : DIM}
                bg={selected ? "cyan" : undefined}
              >
                {` ${tab.label} `}
              </text>
            </Clickable>
          );
        })}
      </box>
      <text fg="cyan">
        {TABS.map((tab) =>
          tab.id === active
            ? "▬".repeat(tab.label.length + 2)
            : " ".repeat(tab.label.length + 2),
        ).join("  ")}
      </text>
    </box>
  );
}
