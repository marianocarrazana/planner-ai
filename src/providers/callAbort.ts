import type { ProviderCallOptions } from "./types.js";

export class ProviderAbortError extends Error {
  readonly name = "AbortError";

  constructor(message = "Aborted") {
    super(message);
  }
}

export type CallAbortHandle = {
  controller: AbortController;
  signal: AbortSignal;
  cleanup: () => void;
  throwIfAborted: () => void;
};

/**
 * Combines an optional parent AbortSignal with an optional wall-clock timeout
 * into a single AbortController for one provider call.
 */
export function createCallAbort(
  options?: ProviderCallOptions,
): CallAbortHandle {
  const controller = new AbortController();
  const onParentAbort = () => {
    if (!controller.signal.aborted) {
      controller.abort(options?.signal?.reason);
    }
  };

  if (options?.signal) {
    if (options.signal.aborted) {
      controller.abort(options.signal.reason);
    } else {
      options.signal.addEventListener("abort", onParentAbort, { once: true });
    }
  }

  let timer: ReturnType<typeof setTimeout> | undefined;
  if (
    typeof options?.timeoutMs === "number" &&
    options.timeoutMs > 0 &&
    !controller.signal.aborted
  ) {
    timer = setTimeout(() => {
      if (!controller.signal.aborted) {
        controller.abort(
          new ProviderAbortError(`Timed out after ${options.timeoutMs}ms`),
        );
      }
    }, options.timeoutMs);
  }

  const cleanup = () => {
    if (timer !== undefined) {
      clearTimeout(timer);
      timer = undefined;
    }
    options?.signal?.removeEventListener("abort", onParentAbort);
  };

  const throwIfAborted = () => {
    if (!controller.signal.aborted) return;
    const reason = controller.signal.reason;
    if (reason instanceof Error) throw reason;
    throw new ProviderAbortError(
      typeof reason === "string" && reason.length > 0 ? reason : "Aborted",
    );
  };

  return {
    controller,
    signal: controller.signal,
    cleanup,
    throwIfAborted,
  };
}

export function isAbortError(err: unknown): boolean {
  if (err instanceof ProviderAbortError) return true;
  if (err instanceof Error && err.name === "AbortError") return true;
  if (
    typeof DOMException !== "undefined" &&
    err instanceof DOMException &&
    err.name === "AbortError"
  ) {
    return true;
  }
  return false;
}

/** Rejects when `signal` aborts; resolves after `ms` otherwise. */
export function abortableSleep(
  ms: number,
  signal?: AbortSignal,
): Promise<void> {
  if (signal?.aborted) {
    const reason = signal.reason;
    return Promise.reject(
      reason instanceof Error
        ? reason
        : new ProviderAbortError(
            typeof reason === "string" && reason.length > 0
              ? reason
              : "Aborted",
          ),
    );
  }

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);

    const onAbort = () => {
      clearTimeout(timer);
      const reason = signal?.reason;
      reject(
        reason instanceof Error
          ? reason
          : new ProviderAbortError(
              typeof reason === "string" && reason.length > 0
                ? reason
                : "Aborted",
            ),
      );
    };

    signal?.addEventListener("abort", onAbort, { once: true });
  });
}
