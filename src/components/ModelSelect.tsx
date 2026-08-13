import { useKeyboard, useTerminalDimensions } from "@opentui/react";
import { useEffect, useMemo, useState } from "react";
import {
  formatChoiceLabel,
  type ModelChoice,
  type ModelPick,
  type ModelSelection,
  type ProviderKind,
} from "../providers/models.js";
import { Clickable } from "./Clickable.js";

export type ModelSelectMode = "proposers" | "consensus";

interface ModelSelectProps {
  mode: ModelSelectMode;
  choices: ModelChoice[];
  value: ModelSelection;
  includeMocks: boolean;
  onChange: (next: ModelSelection) => void;
  onSubmit: (selection: ModelSelection) => void;
  onToggleIncludeMocks: () => void;
}

const DIM = "#888888";

const PROVIDER_ORDER: ProviderKind[] = ["anthropic", "cursor", "mock"];

const PROVIDER_HEADERS: Record<ProviderKind, string> = {
  anthropic: "Claude",
  cursor: "Cursor",
  mock: "Mock",
};

type DisplayRow =
  | { kind: "header"; provider: ProviderKind; label: string }
  | { kind: "choice"; choice: ModelChoice; choiceIndex: number };

function pickKey(pick: ModelPick): string {
  return `${pick.provider}:${pick.modelId}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Keep a fixed-width row so shorter redraws wipe leftover terminal glyphs. */
function fitRow(text: string, width: number): string {
  const w = Math.max(8, width);
  if (text.length <= w) return text.padEnd(w);
  return `${text.slice(0, Math.max(0, w - 1))}…`;
}

function visibleWindow(
  cursor: number,
  total: number,
  windowSize: number,
): { start: number; end: number } {
  if (total <= windowSize) return { start: 0, end: total };
  const maxStart = Math.max(0, total - windowSize);
  const start = clamp(cursor - Math.floor(windowSize / 2), 0, maxStart);
  return { start, end: start + windowSize };
}

function providerSourceLabel(provider: ProviderKind): string {
  switch (provider) {
    case "anthropic":
      return "claude";
    case "cursor":
      return "cursor";
    case "mock":
      return "mock";
  }
}

function choiceMatchesQuery(choice: ModelChoice, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    choice.label,
    choice.modelId,
    choice.provider,
    providerSourceLabel(choice.provider),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
}

function buildDisplayRows(filtered: ModelChoice[]): DisplayRow[] {
  const rows: DisplayRow[] = [];
  let choiceIndex = 0;

  for (const provider of PROVIDER_ORDER) {
    const group = filtered.filter((c) => c.provider === provider);
    if (group.length === 0) continue;
    rows.push({
      kind: "header",
      provider,
      label: PROVIDER_HEADERS[provider],
    });
    for (const choice of group) {
      rows.push({ kind: "choice", choice, choiceIndex });
      choiceIndex += 1;
    }
  }

  return rows;
}

function firstChoiceRowIndex(rows: DisplayRow[]): number {
  const idx = rows.findIndex((r) => r.kind === "choice");
  return idx >= 0 ? idx : 0;
}

function nextChoiceRowIndex(
  rows: DisplayRow[],
  from: number,
  direction: 1 | -1,
): number {
  let i = from + direction;
  while (i >= 0 && i < rows.length) {
    if (rows[i]?.kind === "choice") return i;
    i += direction;
  }
  return from;
}

function snapToChoiceRow(rows: DisplayRow[], index: number): number {
  const row = rows[index];
  if (row?.kind === "choice") return index;
  const forward = nextChoiceRowIndex(rows, index - 1, 1);
  if (rows[forward]?.kind === "choice") return forward;
  return nextChoiceRowIndex(rows, index + 1, -1);
}

export function ModelSelect({
  mode,
  choices,
  value,
  includeMocks,
  onChange,
  onSubmit,
  onToggleIncludeMocks,
}: ModelSelectProps) {
  const { width: columns, height: rows } = useTerminalDimensions();

  const [cursor, setCursor] = useState(0);
  const [scrollStart, setScrollStart] = useState(0);
  const [continueFocused, setContinueFocused] = useState(false);
  const [filterQuery, setFilterQuery] = useState("");
  /** When true, filter `<input>` is focused — `m`/`c` shortcuts are disabled. */
  const [filtering, setFiltering] = useState(false);

  const proposers = value.proposers;
  const consensus = value.consensus;

  const proposerKeys = useMemo(
    () => new Set(proposers.map(pickKey)),
    [proposers],
  );

  const filteredChoices = useMemo(
    () => choices.filter((c) => choiceMatchesQuery(c, filterQuery)),
    [choices, filterQuery],
  );

  const displayRows = useMemo(
    () => buildDisplayRows(filteredChoices),
    [filteredChoices],
  );

  const canContinue = proposers.length > 0 && Boolean(consensus);
  const maxIndex = Math.max(0, displayRows.length - 1);
  const rowWidth = Math.max(20, columns - 4);

  // Header + tab bar + title/help + filter + continue/hints + padding
  const listHeight = Math.max(5, rows - 16);

  useEffect(() => {
    setCursor(firstChoiceRowIndex(displayRows));
    setContinueFocused(false);
  }, [mode]);

  useEffect(() => {
    setCursor(firstChoiceRowIndex(displayRows));
    setContinueFocused(false);
  }, [filterQuery]);

  useEffect(() => {
    setCursor((prev) => {
      if (displayRows.length === 0) return 0;
      if (displayRows[prev]?.kind === "choice") return prev;
      return firstChoiceRowIndex(displayRows);
    });
  }, [choices]);

  useEffect(() => {
    if (continueFocused) return;
    if (displayRows.length === 0) {
      setScrollStart(0);
      return;
    }
    const { start } = visibleWindow(cursor, displayRows.length, listHeight);
    setScrollStart(start);
  }, [cursor, continueFocused, displayRows.length, listHeight]);

  const windowEnd = Math.min(displayRows.length, scrollStart + listHeight);
  const visibleRows = displayRows.slice(scrollStart, windowEnd);

  const activateChoice = (choice: ModelChoice, rowIndex: number) => {
    const pick: ModelPick = {
      provider: choice.provider,
      modelId: choice.modelId,
    };

    setContinueFocused(false);
    setCursor(rowIndex);

    if (mode === "proposers") {
      const key = pickKey(pick);
      const nextProposers = proposers.some((p) => pickKey(p) === key)
        ? proposers.filter((p) => pickKey(p) !== key)
        : [...proposers, pick];
      onChange({ proposers: nextProposers, consensus });
      return;
    }

    onChange({ proposers, consensus: pick });
  };

  const activateRow = (index: number) => {
    const row = displayRows[index];
    if (!row || row.kind !== "choice") return;
    activateChoice(row.choice, index);
  };

  const submit = () => {
    if (!canContinue) return;
    onSubmit(value);
  };

  useKeyboard((key) => {
    if (key.name === "escape") {
      if (filterQuery) {
        setFilterQuery("");
        return;
      }
      if (filtering) {
        setFiltering(false);
        return;
      }
    }

    // `/` enters filter mode (also when already filtering, keep focus)
    if (
      !filtering &&
      !key.ctrl &&
      !key.meta &&
      (key.raw === "/" || key.sequence === "/" || key.name === "/")
    ) {
      setFiltering(true);
      setContinueFocused(false);
      return;
    }

    // Shortcuts that conflict with typing — only when not filtering
    if (!filtering) {
      if (key.name === "m" && !key.ctrl && !key.meta) {
        onToggleIncludeMocks();
        return;
      }
      if (key.name === "c" && !key.ctrl && !key.meta) {
        submit();
        return;
      }
    }

    if (continueFocused) {
      if (key.name === "up") {
        setContinueFocused(false);
        setCursor(snapToChoiceRow(displayRows, maxIndex));
        return;
      }
      if (key.name === "return" || key.name === "space") {
        submit();
      }
      return;
    }

    if (key.name === "pageup") {
      setCursor((prev) =>
        snapToChoiceRow(displayRows, Math.max(0, prev - listHeight)),
      );
      return;
    }
    if (key.name === "pagedown") {
      setCursor((prev) =>
        snapToChoiceRow(displayRows, Math.min(maxIndex, prev + listHeight)),
      );
      return;
    }
    if (key.name === "up") {
      setCursor((prev) => nextChoiceRowIndex(displayRows, prev, -1));
      return;
    }
    if (key.name === "down") {
      const next = nextChoiceRowIndex(displayRows, cursor, 1);
      if (next === cursor && canContinue) {
        setFiltering(false);
        setContinueFocused(true);
        return;
      }
      setCursor(next);
      return;
    }

    if (key.name === "space" || key.name === "return") {
      if (filtering) return;
      activateRow(cursor);
    }
  });

  const consensusChoice = choices.find(
    (c) =>
      c.provider === consensus.provider && c.modelId === consensus.modelId,
  );
  const consensusLabel = consensusChoice
    ? formatChoiceLabel(consensusChoice)
    : `${consensus.provider}:${consensus.modelId}`;

  const scrollHint =
    displayRows.length > listHeight
      ? ` · showing ${scrollStart + 1}–${windowEnd} of ${displayRows.length}`
      : "";

  const title =
    mode === "proposers"
      ? `Proposers (${proposers.length} selected)${scrollHint}`
      : `Consensus (${consensusLabel})${scrollHint}`;

  const help =
    mode === "proposers"
      ? "Multi-select — Space/click to toggle"
      : "Single-select — Space/click to choose";

  const mocksHint = includeMocks ? "mocks on" : "mocks off";

  return (
    <box flexDirection="column" gap={1} flexGrow={1} width={rowWidth}>
      <box flexDirection="column">
        <text>
          <strong>{fitRow(title, rowWidth)}</strong>
        </text>
        <text fg={DIM}>{fitRow(help, rowWidth)}</text>
      </box>

      <box flexDirection="row" gap={0} width={rowWidth}>
        <text fg={DIM}>{"/ "}</text>
        {filtering ? (
          <input
            focused
            flexGrow={1}
            value={filterQuery}
            onInput={setFilterQuery}
            placeholder="filter models…"
          />
        ) : (
          <text fg={filterQuery ? undefined : DIM} truncate>
            {filterQuery || "press / to filter"}
          </text>
        )}
      </box>

      <box flexDirection="column">
        {visibleRows.length === 0 ? (
          <text fg={DIM}>{fitRow("(no matches)", rowWidth)}</text>
        ) : (
          visibleRows.map((row, offset) => {
            const index = scrollStart + offset;
            if (row.kind === "header") {
              return (
                <text key={`header-${row.provider}`} fg={DIM} truncate>
                  {fitRow(`  ── ${row.label} ──`, rowWidth)}
                </text>
              );
            }

            const { choice } = row;
            const key = pickKey(choice);
            const focused = !continueFocused && cursor === index;
            const selected =
              mode === "proposers"
                ? proposerKeys.has(key)
                : pickKey(consensus) === key;
            const mark =
              mode === "proposers"
                ? selected
                  ? "[x]"
                  : "[ ]"
                : selected
                  ? "(•)"
                  : "( )";
            const pointer = focused ? ">" : " ";
            const line = fitRow(
              `${pointer} ${mark} ${formatChoiceLabel(choice)}`,
              rowWidth,
            );
            return (
              <Clickable
                key={`${mode}-${key}`}
                onClick={() => activateChoice(choice, index)}
              >
                <text
                  fg={focused ? "black" : selected ? "green" : undefined}
                  bg={focused ? "cyan" : undefined}
                  truncate
                >
                  {line}
                </text>
              </Clickable>
            );
          })
        )}
      </box>

      <Clickable
        onClick={() => {
          setFiltering(false);
          setContinueFocused(true);
          submit();
        }}
      >
        <text
          fg={!canContinue ? DIM : continueFocused ? "black" : undefined}
          bg={continueFocused ? "cyan" : undefined}
          truncate
        >
          <strong>
            {fitRow(
              `${continueFocused ? ">" : " "} [ Continue ]${
                canContinue
                  ? ""
                  : proposers.length === 0
                    ? " (select ≥1 proposer)"
                    : " (pick consensus)"
              }`,
              rowWidth,
            )}
          </strong>
        </text>
      </Clickable>

      <text fg={DIM}>
        {fitRow(
          `↑↓ scroll · / filter · m ${mocksHint} · Esc clear · c continue`,
          rowWidth,
        )}
      </text>
    </box>
  );
}
