"use client";

import Image from "next/image";
import { AppFrame } from "@/components/shells/AppFrame";
import styles from "./gate.module.css";

type WelcomeScreenProps = {
  onStart: () => void;
  busy?: boolean;
};

export function WelcomeScreen({ onStart, busy = false }: WelcomeScreenProps) {
  return (
    <AppFrame>
      <div className={styles.body}>
        <Image
          src="/kubera-logo.png"
          alt=""
          width={128}
          height={128}
          className={styles.logo}
          priority
        />
        <h1 className={styles.title}>Kubera</h1>
        <p className={styles.lede}>I&rsquo;ll help you with your finances.</p>

        <button
          type="button"
          className={styles.primary}
          onClick={onStart}
          disabled={busy}
        >
          {busy ? "Waking Kubera…" : "Talk to Kubera"}
        </button>
      </div>
    </AppFrame>
  );
}
