"use client";

import { useRef } from "react";
import { useLevelVar, type LevelMeter } from "@/lib/audio-level";
import { Icon } from "./Icon";
import styles from "./atoms.module.css";

export type OrbState =
  | "idle"
  | "listening"
  | "speaking"
  | "thinking"
  | "connecting"
  | "muted";

type BreathingOrbProps = {
  state?: OrbState;
  size?: "md" | "lg";
  /** Pulse harder when the mic hears input. */
  active?: boolean;
  /** Live loudness for the current speaker. */
  meter?: LevelMeter | null;
};

export function BreathingOrb({
  state = "listening",
  size = "md",
  active = false,
  meter = null,
}: BreathingOrbProps) {
  const ref = useRef<HTMLDivElement>(null);
  const tracking = state === "speaking" || (state === "listening" && active);
  useLevelVar(ref, meter, "--level", { gain: 2.4, enabled: tracking });

  const sizeClass = size === "lg" ? styles.orbLg : "";
  const moodClass =
    state === "listening"
      ? active
        ? styles.orbInput
        : styles.orbListening
      : state === "speaking"
        ? styles.orbSpeaking
        : state === "muted" || state === "idle"
          ? styles.orbMuted
          : "";

  if (state === "connecting") {
    return (
      <div
        ref={ref}
        className={[styles.orb, sizeClass].filter(Boolean).join(" ")}
        aria-hidden
      >
        <div className={[styles.orbHalo, styles.orbHaloConnect].join(" ")} />
        <div className={[styles.orbCore, styles.orbCoreConnect].join(" ")} />
      </div>
    );
  }

  if (state === "thinking") {
    return (
      <div
        ref={ref}
        className={[styles.orb, sizeClass].filter(Boolean).join(" ")}
        aria-hidden
      >
        <div className={styles.orbThinkingRing} />
        <div className={[styles.orbCore, styles.orbCoreThinking].join(" ")}>
          <Icon name="microphone" size={size === "lg" ? 28 : 14} />
        </div>
      </div>
    );
  }

  const haloExtra =
    state === "speaking"
      ? styles.orbHaloSpeak
      : active && state === "listening"
        ? styles.orbHaloInput
        : state === "listening"
          ? ""
          : styles.orbHaloFast;

  return (
    <div
      ref={ref}
      className={[styles.orb, sizeClass, moodClass, tracking ? styles.orbLive : ""]
        .filter(Boolean)
        .join(" ")}
      aria-hidden
    >
      <div className={[styles.orbHalo, haloExtra].filter(Boolean).join(" ")} />
      <div className={styles.orbCore}>
        <Icon
          name={state === "muted" ? "microphone-slash" : "microphone"}
          size={size === "lg" ? 28 : 14}
        />
      </div>
    </div>
  );
}
