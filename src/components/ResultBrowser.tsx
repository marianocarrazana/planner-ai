import { useKeyboard, useRenderer, useTerminalDimensions } from "@opentui/react";
import { useEffect, useMemo, useState } from "react";
import type { ProposalState, RunMode } from "../pipeline/types.js";
import { Clickable } from "./Clickable.js";

interface ResultBrowserProps {
  mode?: RunMode;
  /** Workspace plan.md path when written; null for ask mode. */
  planPath?: string | null;
  /** Archive directory under .planner-ai/. */
  archivePath: string;
  plan: string;
  proposals: ProposalState[];
  /** When set, shows “Plan/Ask another” and handles `n`. */
  onPlanAnother?: () => void;
  /**
   * When set, q / Enter / Esc call this instead of destroying the renderer.
   * Used by History to return to the run list.
   */
  onExit?: () => void;
  /** Header title. Defaults by mode (live) or “Archived run”. */
  title?: string;
}

const PRIMARY_TAB_ID = "primary";
const DIM = "#888888";

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function fitRow(text: string, width: number): string {
  const w = Math.max(8, width);
  if (text.length <= w) return text.padEnd(w);
  return `${text.slice(0, Math.max(0, w - 1))}…`;
}

export function ResultBrowser({
  mode = "plan",
  planPath = null,
  archivePath,
  plan,
  proposals,
  onPlanAnother,
  onExit,
  title,
}: ResultBrowserProps) {
  const renderer = useRenderer();
  const { width: columns, height: rows } = useTerminalDimensions();
  const canPlanAnother = Boolean(onPlanAnother);
  const isAsk = mode === "ask";
  const primaryLabel = isAsk ? "Answer" : "Plan";
  const anotherLabel = isAsk ? "Ask another" : "Plan another";
  const heading =
    title ??
    (onExit ? "Archived run" : isAsk ? "Answer ready" : "Plan ready");

  const tabs = useMemo(
    () => [
      { id: PRIMARY_TAB_ID, label: primaryLabel },
      ...proposals.map((proposal) => ({
        id: proposal.id,
        label: proposal.label,
      })),
    ],
    [proposals, primaryLabel],
  );

  const hasErrors = proposals.some((p) => p.status === "error");
  const doneCount = proposals.filter((p) => p.status === "done").length;

  const [activeTab, setActiveTab] = useState(PRIMARY_TAB_ID);
  const [scrollTop, setScrollTop] = useState(0);

  const rowWidth = Math.max(20, columns - 4);
  // Header chrome + result tabs + status + hints + padding (+ N-of-M / plan-another)
  const chromeRows = (hasErrors ? 17 : 16) + (canPlanAnother ? 1 : 0);
  const bodyHeight = Math.max(5, rows - chromeRows);

  const activeProposal =
    activeTab === PRIMARY_TAB_ID
      ? null
      : (proposals.find((p) => p.id === activeTab) ?? null);

  const bodyText = useMemo(() => {
    if (activeTab === PRIMARY_TAB_ID) return plan;
    if (!activeProposal) return "";
    if (activeProposal.error) return activeProposal.error;
    return activeProposal.body ?? "";
  }, [activeTab, activeProposal, plan]);

  const lines = useMemo(() => bodyText.split("\n"), [bodyText]);
  const maxScroll = Math.max(0, lines.length - bodyHeight);

  useEffect(() => {
    setScrollTop(0);
  }, [activeTab]);

  useEffect(() => {
    setScrollTop((prev) => clamp(prev, 0, maxScroll));
  }, [maxScroll]);

  const visibleLines = lines.slice(scrollTop, scrollTop + bodyHeight);
  const activeIndex = Math.max(
    0,
    tabs.findIndex((tab) => tab.id === activeTab),
  );

  const selectTab = (id: string) => {
    setActiveTab(id);
  };

  const moveTab = (delta: number) => {
    if (tabs.length === 0) return;
    const next = (activeIndex + delta + tabs.length) % tabs.length;
    const tab = tabs[next];
    if (tab) setActiveTab(tab.id);
  };

  const scrollBy = (delta: number) => {
    setScrollTop((prev) => clamp(prev + delta, 0, maxScroll));
  };

  const exit = () => {
    if (onExit) {
      onExit();
      return;
    }
    renderer.destroy();
  };

  useKeyboard((key) => {
    if (key.name === "q" || key.name === "return" || key.name === "escape") {
      exit();
      return;
    }

    if (key.name === "n" && onPlanAnother) {
      onPlanAnother();
      return;
    }

    if (key.name === "left" || key.sequence === "[") {
      moveTab(-1);
      return;
    }
    if (key.name === "right" || key.sequence === "]") {
      moveTab(1);
      return;
    }

    if (key.name === "up") {
      scrollBy(-1);
      return;
    }
    if (key.name === "down") {
      scrollBy(1);
      return;
    }
    if (key.name === "pageup") {
      scrollBy(-bodyHeight);
      return;
    }
    if (key.name === "pagedown") {
      scrollBy(bodyHeight);
    }
  });

  const scrollHint =
    lines.length > bodyHeight
      ? ` · lines ${scrollTop + 1}–${Math.min(lines.length, scrollTop + bodyHeight)} of ${lines.length}`
      : "";

  const pathLabel = onExit
    ? archivePath
    : planPath
      ? `Wrote ${planPath} · archived ${archivePath}`
      : `Archived ${archivePath}`;
  const statusLine =
    activeTab === PRIMARY_TAB_ID
      ? `${pathLabel}${scrollHint}`
      : activeProposal?.error
        ? `Error · ${activeProposal.label}${scrollHint}`
        : `${activeProposal?.label ?? "Proposal"}${scrollHint}`;

  const hints = canPlanAnother
    ? `←→/[ ] tabs · ↑↓/wheel/PgUp/PgDn scroll · n ${anotherLabel.toLowerCase()} · Enter or q exit`
    : "←→/[ ] tabs · ↑↓/wheel/PgUp/PgDn scroll · Esc/Enter/q back";

  return (
    <box flexDirection="column" gap={1} flexGrow={1} width={rowWidth}>
      <box flexDirection="column" gap={0}>
        <text fg="green">
          <strong>{heading}</strong>
        </text>
        {hasErrors ? (
          <text fg={DIM}>
            consensus used {doneCount} of {proposals.length} proposers
          </text>
        ) : null}
        <box flexDirection="row" gap={2}>
          {tabs.map((tab) => {
            const selected = tab.id === activeTab;
            return (
              <Clickable key={tab.id} onClick={() => selectTab(tab.id)}>
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
          {tabs
            .map((tab) =>
              tab.id === activeTab
                ? "▬".repeat(tab.label.length + 2)
                : " ".repeat(tab.label.length + 2),
            )
            .join("  ")}
        </text>
      </box>

      <text fg={activeProposal?.error ? "red" : DIM}>
        {fitRow(statusLine, rowWidth)}
      </text>

      <box
        flexDirection="column"
        flexGrow={1}
        height={bodyHeight}
        onMouseScroll={(event) => {
          const scroll = event.scroll;
          if (!scroll) return;
          const amount = Math.max(1, Math.round(Math.abs(scroll.delta)));
          if (scroll.direction === "up") {
            scrollBy(-amount);
          } else if (scroll.direction === "down") {
            scrollBy(amount);
          }
        }}
      >
        {visibleLines.length === 0 ? (
          <text selectable={false} fg={DIM}>
            {fitRow("(empty)", rowWidth)}
          </text>
        ) : (
          visibleLines.map((line, index) => (
            <text
              key={`${scrollTop + index}-${line.slice(0, 24)}`}
              selectable={false}
              truncate
            >
              {fitRow(line.length === 0 ? " " : line, rowWidth)}
            </text>
          ))
        )}
      </box>

      {onPlanAnother ? (
        <Clickable onClick={onPlanAnother}>
          <text fg="cyan">→ {anotherLabel} (or press n)</text>
        </Clickable>
      ) : null}
      <text fg={DIM}>{fitRow(hints, rowWidth)}</text>
    </box>
  );
}
