"use client";

import { useRef } from "react";
import { useLevelVar, type LevelMeter } from "@/lib/audio-level";
import styles from "./atoms.module.css";

type InputWaveProps = {
  active?: boolean;
  /** Live mic loudness. Without it the bars fall back to a fixed idle pulse. */
  meter?: LevelMeter | null;
};

const BARS = 7;
// Bars nearer the middle react harder, so loud speech reads as a shape rather
// than a block.
const WEIGHTS = [0.45, 0.7, 0.9, 1, 0.9, 0.7, 0.45];

export function InputWave({ active = false, meter = null }: InputWaveProps) {
  const ref = useRef<HTMLDivElement>(null);
  useLevelVar(ref, meter, "--level", { gain: 3.2, enabled: active });

  return (
    <div
      ref={ref}
      className={[
        styles.inputWave,
        active ? styles.inputWaveActive : "",
        meter ? "" : styles.inputWaveIdle,
      ]
        .filter(Boolean)
        .join(" ")}
      aria-hidden
    >
      {Array.from({ length: BARS }, (_, i) => (
        <span
          key={i}
          className={styles.inputWaveBar}
          style={
            {
              animationDelay: `${i * 0.08}s`,
              "--weight": WEIGHTS[i],
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}
