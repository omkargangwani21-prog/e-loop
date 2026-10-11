import { useEffect, useRef } from "react";

/** Moves keyboard and screen-reader focus to a step heading when the step appears. */
export function useFocusOnMount<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, []);
  return ref;
}
