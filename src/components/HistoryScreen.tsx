import { useKeyboard, useTerminalDimensions } from "@opentui/react";
import { useCallback, useEffect, useState } from "react";
import {
  listArchivedRuns,
  readArchivedRun,
  type ArchivedRun,
  type ArchivedRunSummary,
} from "../readRunArchive.js";
import { ARCHIVE_DIR } from "../writeRunArchive.js";
import { Clickable } from "./Clickable.js";
import { ResultBrowser } from "./ResultBrowser.js";

const DIM = "#888888";

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

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

type View =
  | { kind: "list" }
  | { kind: "loading"; run: ArchivedRunSummary }
  | { kind: "detail"; run: ArchivedRunSummary; archived: ArchivedRun }
  | { kind: "error"; run: ArchivedRunSummary; message: string };

export function HistoryScreen() {
  const { width: columns, height: rows } = useTerminalDimensions();
  const rowWidth = Math.max(20, columns - 4);
  const listHeight = Math.max(5, rows - 14);

  const [runs, setRuns] = useState<ArchivedRunSummary[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [scrollStart, setScrollStart] = useState(0);
  const [view, setView] = useState<View>({ kind: "list" });

  const reload = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const next = await listArchivedRuns();
      setRuns(next);
      setCursor((prev) =>
        next.length === 0 ? 0 : clamp(prev, 0, next.length - 1),
      );
    } catch (err) {
      setRuns([]);
      setListError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (view.kind !== "list" || runs.length === 0) {
      setScrollStart(0);
      return;
    }
    const { start } = visibleWindow(cursor, runs.length, listHeight);
    setScrollStart(start);
  }, [cursor, runs.length, listHeight, view.kind]);

  const openRun = useCallback(async (run: ArchivedRunSummary) => {
    setView({ kind: "loading", run });
    try {
      const archived = await readArchivedRun(run.path);
      setView({ kind: "detail", run, archived });
    } catch (err) {
      setView({
        kind: "error",
        run,
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, []);

  const backToList = useCallback(() => {
    setView({ kind: "list" });
    void reload();
  }, [reload]);

  useKeyboard((key) => {
    if (view.kind === "detail" || view.kind === "loading") return;

    if (view.kind === "error") {
      if (
        key.name === "escape" ||
        key.name === "return" ||
        key.name === "q"
      ) {
        setView({ kind: "list" });
      }
      return;
    }

    if (loadingList || runs.length === 0) {
      if (key.name === "r" && !key.ctrl && !key.meta) {
        void reload();
      }
      return;
    }

    const maxIndex = runs.length - 1;

    if (key.name === "pageup") {
      setCursor((prev) => clamp(prev - listHeight, 0, maxIndex));
      return;
    }
    if (key.name === "pagedown") {
      setCursor((prev) => clamp(prev + listHeight, 0, maxIndex));
      return;
    }
    if (key.name === "up") {
      setCursor((prev) => clamp(prev - 1, 0, maxIndex));
      return;
    }
    if (key.name === "down") {
      setCursor((prev) => clamp(prev + 1, 0, maxIndex));
      return;
    }
    if (key.name === "r" && !key.ctrl && !key.meta) {
      void reload();
      return;
    }
    if (key.name === "return" || key.name === "space") {
      const selected = runs[cursor];
      if (selected) void openRun(selected);
    }
  });

  if (view.kind === "detail") {
    return (
      <ResultBrowser
        mode={view.archived.kind}
        planPath={null}
        archivePath={view.run.path}
        plan={view.archived.plan}
        proposals={view.archived.proposals}
        onExit={backToList}
        title={`Archived · ${view.archived.kind} · ${view.run.timestampLabel}`}
      />
    );
  }

  if (view.kind === "loading") {
    return (
      <box flexDirection="column" gap={1} flexGrow={1}>
        <text>
          <strong>History</strong>
        </text>
        <text fg={DIM}>Loading {view.run.dirName}…</text>
      </box>
    );
  }

  if (view.kind === "error") {
    return (
      <box flexDirection="column" gap={1} flexGrow={1}>
        <text>
          <strong>History</strong>
        </text>
        <text fg="red">{fitRow(view.message, rowWidth)}</text>
        <Clickable onClick={() => setView({ kind: "list" })}>
          <text fg="cyan">← Back to list (Esc)</text>
        </Clickable>
      </box>
    );
  }

  const windowEnd = Math.min(runs.length, scrollStart + listHeight);
  const visibleRuns = runs.slice(scrollStart, windowEnd);
  const scrollHint =
    runs.length > listHeight
      ? ` · showing ${scrollStart + 1}–${windowEnd} of ${runs.length}`
      : runs.length > 0
        ? ` · ${runs.length} run${runs.length === 1 ? "" : "s"}`
        : "";

  return (
    <box flexDirection="column" gap={1} flexGrow={1} width={rowWidth}>
      <box flexDirection="column" gap={0}>
        <text>
          <strong>History</strong>
        </text>
        <text fg={DIM}>
          {fitRow(
            `Archived runs in ${ARCHIVE_DIR}/${scrollHint}`,
            rowWidth,
          )}
        </text>
      </box>

      {loadingList ? (
        <text fg={DIM}>Loading…</text>
      ) : listError ? (
        <text fg="red">{fitRow(listError, rowWidth)}</text>
      ) : runs.length === 0 ? (
        <text fg={DIM}>
          {fitRow(`No archived runs in ${ARCHIVE_DIR}`, rowWidth)}
        </text>
      ) : (
        <box
          flexDirection="column"
          gap={0}
          height={listHeight}
          flexGrow={1}
          onMouseScroll={(event) => {
            const scroll = event.scroll;
            if (!scroll || runs.length === 0) return;
            const amount = Math.max(1, Math.round(Math.abs(scroll.delta)));
            const maxIndex = runs.length - 1;
            if (scroll.direction === "up") {
              setCursor((prev) => clamp(prev - amount, 0, maxIndex));
            } else if (scroll.direction === "down") {
              setCursor((prev) => clamp(prev + amount, 0, maxIndex));
            }
          }}
        >
          {visibleRuns.map((run, index) => {
            const absoluteIndex = scrollStart + index;
            const focused = cursor === absoluteIndex;
            const countLabel =
              run.outputCount === 1
                ? "1 proposer"
                : `${run.outputCount} proposers`;
            const label = `${run.kind}  ·  ${run.timestampLabel}  ·  ${countLabel}`;
            return (
              <Clickable
                key={run.id}
                onClick={() => {
                  setCursor(absoluteIndex);
                  void openRun(run);
                }}
              >
                <text
                  fg={focused ? "black" : undefined}
                  bg={focused ? "cyan" : undefined}
                  selectable={false}
                >
                  {fitRow(`${focused ? "> " : "  "}${label}`, rowWidth)}
                </text>
              </Clickable>
            );
          })}
        </box>
      )}

      <text fg={DIM}>
        {fitRow(
          runs.length === 0
            ? "r refresh · Ctrl+1–5 switch tabs"
            : "↑↓/wheel/PgUp/PgDn · Enter open · r refresh · Ctrl+1–5 tabs",
          rowWidth,
        )}
      </text>
    </box>
  );
}
