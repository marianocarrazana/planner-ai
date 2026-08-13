import { useEffect, useState } from "react";

/**
 * Whole seconds since `startedAt` while `active`. Shares one 1s interval
 * per call site (mount the hook once per list/view, not per row).
 */
export function useElapsedSeconds(
  startedAt: number | null | undefined,
  active: boolean,
): number | null {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!active || startedAt == null) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active, startedAt]);

  if (!active || startedAt == null) return null;
  return Math.max(0, Math.floor((now - startedAt) / 1000));
}

export function formatElapsedSeconds(seconds: number): string {
  return `${seconds}s`;
}
