"use client";

import { useEffect, useRef, useState } from "react";

/**
 * True for a moment after `signature` changes.
 *
 * This is what makes the cards feel generative rather than like a dashboard
 * that happens to be refreshing: the user says a number and sees exactly which
 * card it landed in. The first value never flashes — cards appearing for the
 * first time already announce themselves by appearing.
 */
export function useFlash(signature: string, ms = 1100): boolean {
  const [flashing, setFlashing] = useState(false);
  const previous = useRef<string | null>(null);

  useEffect(() => {
    if (previous.current === null) {
      previous.current = signature;
      return;
    }
    if (previous.current === signature) return;
    previous.current = signature;
    setFlashing(true);
    const id = window.setTimeout(() => setFlashing(false), ms);
    return () => window.clearTimeout(id);
  }, [ms, signature]);

  return flashing;
}
