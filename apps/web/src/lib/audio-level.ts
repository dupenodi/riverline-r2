"use client";

import { useEffect, type RefObject } from "react";

/**
 * Live mic / bot loudness, kept out of React state.
 *
 * The Daily transport runs local and remote audio-level observers at 10 Hz
 * (see @pipecat-ai/daily-transport, which calls startLocalAudioLevelObserver on
 * connect), surfaced as the onLocalAudioLevel / onRemoteAudioLevel callbacks.
 * Re-rendering the call screen ten times a second to animate an orb is waste,
 * so levels are written here and read back inside an animation frame.
 */
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

/**
 * Drive a CSS custom property on `ref` from `meter`, smoothed so the visual
 * eases between the 100 ms samples instead of stepping.
 */
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
      // Rise fast so speech registers immediately, fall slowly so the shape
      // does not flicker between syllables.
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
