import { useEffect, useRef, useState } from 'react'

export interface ApiState<T> {
  data: T | null
  error: string | null
  /** True while a request for the current key is in flight (previous data stays visible meanwhile). */
  loading: boolean
}

/**
 * Loads data whenever `key` changes, aborting the previous request.
 * `enabled=false` holds the request back (used to fit the forecast once before the endpoints that reuse it).
 */
export function useApi<T>(load: (signal: AbortSignal) => Promise<T>, key: string, enabled = true): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: true })
  const loader = useRef(load)
  loader.current = load

  useEffect(() => {
    if (!enabled) {
      setState((s) => (s.loading ? s : { ...s, loading: true }))
      return
    }
    const ctrl = new AbortController()
    setState((s) => ({ ...s, loading: true, error: null }))
    loader
      .current(ctrl.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        setState((s) => ({ ...s, loading: false, error: e instanceof Error ? e.message : 'Request failed' }))
      })
    return () => ctrl.abort()
  }, [key, enabled])

  return state
}
