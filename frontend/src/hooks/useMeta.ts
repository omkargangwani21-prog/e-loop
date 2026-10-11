import { api } from "../api/client";
import type { Meta } from "../api/types";
import { useAsync } from "./useAsync";

let cached: Meta | null = null;

/** Reference data (categories, areas, limits) rarely changes, so it is fetched once per page load. */
export function useMeta() {
  const state = useAsync<Meta>(async (signal) => {
    if (cached) return cached;
    cached = await api.meta(signal);
    return cached;
  }, []);
  return state;
}
