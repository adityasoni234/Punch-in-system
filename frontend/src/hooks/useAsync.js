import { useCallback, useEffect, useRef, useState } from 'react';

/** Loading / data / error state for a fetch, with a manual `reload`. */
export function useAsync(fn, deps = [], { immediate = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: immediate });
  const mounted = useRef(true);
  const callback = useCallback(fn, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(
    async ({ quiet = false } = {}) => {
      if (!quiet) setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const data = await callback();
        if (mounted.current) setState({ data, error: null, loading: false });
        return data;
      } catch (error) {
        if (error.name === 'AbortError') return null;
        if (mounted.current) setState((prev) => ({ ...prev, error, loading: false }));
        return null;
      }
    },
    [callback],
  );

  useEffect(() => {
    if (immediate) run();
  }, [run, immediate]);

  return { ...state, reload: run, setData: (data) => setState((s) => ({ ...s, data })) };
}
