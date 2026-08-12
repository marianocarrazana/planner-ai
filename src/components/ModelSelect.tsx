import { useKeyboard, useTerminalDimensions } from "@opentui/react";
import { useEffect, useMemo, useState } from "react";
import {
  formatChoiceLabel,
  type ModelChoice,
  type ModelPick,
  type ModelSelection,
} from "../providers/models.js";
import { Clickable } from "./Clickable.js";

type Section = "proposers" | "consensus" | "continue";

interface ModelSelectProps {
  choices: ModelChoice[];
  initial: ModelSelection;
  onSubmit: (selection: ModelSelection) => void;
}

const DIM = "#888888";

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

export function ModelSelect({ choices, initial, onSubmit }: ModelSelectProps) {
  const { width: columns, height: rows } = useTerminalDimensions();

  const [section, setSection] = useState<Section>("proposers");
  const [cursor, setCursor] = useState(0);
  const [scrollStart, setScrollStart] = useState(0);
  const [proposers, setProposers] = useState<ModelPick[]>(() => [
    ...initial.proposers,
  ]);
  const [consensus, setConsensus] = useState<ModelPick>(() => ({
    ...initial.consensus,
  }));

  const proposerKeys = useMemo(
    () => new Set(proposers.map(pickKey)),
    [proposers],
  );

  const canContinue = proposers.length > 0 && Boolean(consensus);
  const maxIndex = Math.max(0, choices.length - 1);
  const rowWidth = Math.max(20, columns - 4);

  // Header + tab bar + title/help + section chrome + continue/hints + padding
  const listHeight = Math.max(5, rows - 18);

  useEffect(() => {
    if (section === "continue") return;
    const { start } = visibleWindow(cursor, choices.length, listHeight);
    setScrollStart(start);
  }, [cursor, section, choices.length, listHeight]);

  const windowEnd = Math.min(choices.length, scrollStart + listHeight);
  const visibleChoices = choices.slice(scrollStart, windowEnd);

  const activateRow = (target: "proposers" | "consensus", index: number) => {
    const choice = choices[index];
    if (!choice) return;
    const pick: ModelPick = {
      provider: choice.provider,
      modelId: choice.modelId,
    };

    if (target === "proposers") {
      setSection("proposers");
      setCursor(index);
      setProposers((prev) => {
        const key = pickKey(pick);
        if (prev.some((p) => pickKey(p) === key)) {
          return prev.filter((p) => pickKey(p) !== key);
        }
        return [...prev, pick];
      });
      return;
    }

    setSection("consensus");
    setCursor(index);
    setConsensus(pick);
  };

  const submit = () => {
    if (!canContinue) return;
    onSubmit({ proposers, consensus });
  };

  const cycleSection = (dir: 1 | -1) => {
    const order: Section[] = ["proposers", "consensus", "continue"];
    const idx = order.indexOf(section);
    const next = order[(idx + dir + order.length) % order.length]!;
    setSection(next);
    if (next !== "continue") {
      setCursor((prev) => clamp(prev, 0, maxIndex));
    }
  };

  useKeyboard((key) => {
    if (key.name === "tab") {
      cycleSection(key.shift ? -1 : 1);
      return;
    }

    if (section === "continue") {
      if (key.name === "return" || key.name === "c" || key.name === "space") {
        submit();
      }
      return;
    }

    if (key.name === "pageup") {
      setCursor((prev) => Math.max(0, prev - listHeight));
      return;
    }
    if (key.name === "pagedown") {
      setCursor((prev) => Math.min(maxIndex, prev + listHeight));
      return;
    }
    if (key.name === "up") {
      setCursor((prev) => Math.max(0, prev - 1));
      return;
    }
    if (key.name === "down") {
      setCursor((prev) => Math.min(maxIndex, prev + 1));
      return;
    }

    if (key.name === "space" || key.name === "return") {
      activateRow(section, cursor);
      return;
    }

    if (key.name === "c") {
      submit();
    }
  });

  const consensusLabel =
    choices.find(
      (c) =>
        c.provider === consensus.provider && c.modelId === consensus.modelId,
    )?.label ?? `${consensus.provider}:${consensus.modelId}`;

  const scrollHint =
    choices.length > listHeight
      ? ` · showing ${scrollStart + 1}–${windowEnd} of ${choices.length}`
      : "";

  return (
    <box flexDirection="column" gap={1} flexGrow={1} width={rowWidth}>
      <box flexDirection="column">
        <text>
          <strong>{fitRow("Select models", rowWidth)}</strong>
        </text>
        <text fg={DIM}>
          {fitRow(
            section === "proposers"
              ? "Proposers (multi) — Space/click to toggle"
              : section === "consensus"
                ? "Consensus (single) — Space/click to choose"
                : "Ready to continue",
            rowWidth,
          )}
        </text>
      </box>

      <box flexDirection="column">
        <text fg={section === "proposers" ? "cyan" : DIM}>
          <strong>
            {fitRow(
              `Proposers  (${proposers.length} selected)${section === "proposers" ? scrollHint : ""}`,
              rowWidth,
            )}
          </strong>
        </text>
        {section !== "proposers" ? (
          <Clickable
            onClick={() => {
              setSection("proposers");
              setCursor(0);
            }}
          >
            <text fg={DIM}>
              {fitRow(
                proposers.length === 0
                  ? "  (none — click/Tab to edit)"
                  : `  ${proposers.length} model(s) selected · click/Tab to edit`,
                rowWidth,
              )}
            </text>
          </Clickable>
        ) : (
          visibleChoices.map((choice, offset) => {
            const index = scrollStart + offset;
            const key = pickKey(choice);
            const selected = proposerKeys.has(key);
            const focused = cursor === index;
            const mark = selected ? "[x]" : "[ ]";
            const pointer = focused ? ">" : " ";
            const line = fitRow(
              `${pointer} ${mark} ${formatChoiceLabel(choice)}`,
              rowWidth,
            );
            return (
              <Clickable
                key={`p-${key}`}
                onClick={() => activateRow("proposers", index)}
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

      <box flexDirection="column">
        <text fg={section === "consensus" ? "cyan" : DIM}>
          <strong>
            {fitRow(
              `Consensus  (${consensusLabel})${section === "consensus" ? scrollHint : ""}`,
              rowWidth,
            )}
          </strong>
        </text>
        {section !== "consensus" ? (
          <Clickable
            onClick={() => {
              setSection("consensus");
              setCursor(0);
            }}
          >
            <text fg={DIM}>
              {fitRow(`  ${consensusLabel} · click/Tab to edit`, rowWidth)}
            </text>
          </Clickable>
        ) : (
          visibleChoices.map((choice, offset) => {
            const index = scrollStart + offset;
            const key = pickKey(choice);
            const selected = pickKey(consensus) === key;
            const focused = cursor === index;
            const mark = selected ? "(•)" : "( )";
            const pointer = focused ? ">" : " ";
            const line = fitRow(
              `${pointer} ${mark} ${formatChoiceLabel(choice)}`,
              rowWidth,
            );
            return (
              <Clickable
                key={`c-${key}`}
                onClick={() => activateRow("consensus", index)}
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
          setSection("continue");
          submit();
        }}
      >
        <text
          fg={
            !canContinue
              ? DIM
              : section === "continue"
                ? "black"
                : undefined
          }
          bg={section === "continue" ? "cyan" : undefined}
          truncate
        >
          <strong>
            {fitRow(
              `${section === "continue" ? ">" : " "} [ Continue ]${
                canContinue ? "" : " (select ≥1 proposer)"
              }`,
              rowWidth,
            )}
          </strong>
        </text>
      </Clickable>

      <text fg={DIM}>
        {fitRow(
          "↑↓/PgUp/PgDn scroll · Space toggle · Tab section · c continue",
          rowWidth,
        )}
      </text>
    </box>
  );
}
