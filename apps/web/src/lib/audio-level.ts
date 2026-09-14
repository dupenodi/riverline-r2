"use client";

import { useEffect, type RefObject } from "react";

/** Mic/bot loudness outside React state (Daily samples ~10 Hz). */
export class LevelMeter {
  private value = 0;

  set(level: number) {
    this.value = Number.isFinite(level) ? Math.max(0, Math.min(1, level)) : 0;
  }

  get(): number {
    return this.value;
  }

  reset() {
    this.value = 0;
  }
}

/** Write smoothed `meter` into a CSS var on `ref`. */
export function useLevelVar(
  ref: RefObject<HTMLElement | null>,
  meter: LevelMeter | null,
  varName = "--level",
  { gain = 1, enabled = true }: { gain?: number; enabled?: boolean } = {},
) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (!meter || !enabled) {
      el.style.setProperty(varName, "0");
      return;
    }

    const reduced = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    )?.matches;

    let raf = 0;
    let shown = 0;
    const tick = () => {
      const target = Math.min(1, meter.get() * gain);
      // Fast attack, slow release — avoids syllable flicker.
      const ease = target > shown ? 0.45 : 0.12;
      shown += (target - shown) * ease;
      el.style.setProperty(varName, shown.toFixed(3));
      raf = requestAnimationFrame(tick);
    };

    if (reduced) {
      el.style.setProperty(varName, "0");
      return;
    }

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [ref, meter, varName, gain, enabled]);
}
