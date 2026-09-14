"use client";

import Image from "next/image";
import { AppFrame } from "./AppFrame";
import styles from "@/components/gate.module.css";

type Step = "mic" | "session" | "room" | "assistant";

type ConnectingShellProps = {
  step: Step;
  onCancel?: () => void;
};

const STATUS: Record<Step, string> = {
  mic: "Checking your microphone…",
  session: "Starting up…",
  room: "Connecting…",
  assistant: "Almost there…",
};

export function ConnectingShell({ step, onCancel }: ConnectingShellProps) {
  return (
    <AppFrame>
      <div className={styles.body}>
        <Image
          src="/kubera-thinking.png"
          alt=""
          width={128}
          height={128}
          className={[styles.logo, styles.logoPulse].join(" ")}
          priority
        />
        <h1 className={styles.title}>Kubera</h1>
        <p className={styles.lede}>{STATUS[step]}</p>

        {onCancel ? (
          <button type="button" className={styles.ghost} onClick={onCancel}>
            Cancel
          </button>
        ) : null}
      </div>
    </AppFrame>
  );
}
