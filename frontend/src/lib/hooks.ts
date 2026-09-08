import { useCallback, useEffect, useState } from "react";

export interface AsyncState<T> {
  loading: boolean;
  data: T | null;
  error: string | null;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<AsyncState<T>>({ loading: true, data: null, error: null });

  const run = useCallback(() => {
    setState({ loading: true, data: null, error: null });
    Promise.resolve()
      .then(fn)
      .then((data) => setState({ loading: false, data, error: null }))
      .catch((e) => setState({ loading: false, data: null, error: String(e?.message ?? e) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(run, [run]);
  return [state, run] as const;
}
