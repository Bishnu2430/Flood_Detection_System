import { useEffect, useRef, useState } from "react";

export type PollState<T> = {
  data: T | null;
  error: unknown;
  isLoading: boolean;
  lastUpdatedAt: number | null;
};

export function usePolling<T>(opts: {
  key: string;
  intervalMs: number;
  load: () => Promise<T>;
}): PollState<T> {
  const { intervalMs, load } = opts;

  const [state, setState] = useState<PollState<T>>({
    data: null,
    error: null,
    isLoading: true,
    lastUpdatedAt: null,
  });

  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      setState((s) => ({
        ...s,
        isLoading: s.lastUpdatedAt === null,
        error: null,
      }));
      try {
        const data = await loadRef.current();
        if (cancelled) return;
        setState({
          data,
          error: null,
          isLoading: false,
          lastUpdatedAt: Date.now(),
        });
      } catch (error) {
        if (cancelled) return;
        setState((s) => ({ ...s, error, isLoading: false }));
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [intervalMs]);

  return state;
}
