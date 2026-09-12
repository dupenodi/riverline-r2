"use client";

import Image from "next/image";
import { AmbientBackdrop, Button } from "@/components/atoms";
import styles from "./WelcomeScreen.module.css";

type WelcomeScreenProps = {
  onStart: () => void;
  busy?: boolean;
};

export function WelcomeScreen({ onStart, busy = false }: WelcomeScreenProps) {
  return (
    <main className={styles.screen}>
      <AmbientBackdrop mood="idle" />
      <div className={styles.body}>
        <div className={styles.hero}>
          <Image
            src="/kubera-logo.png"
            alt=""
            width={88}
            height={88}
            className={styles.logo}
            priority
          />
          <h1 className={styles.title}>Kubera</h1>
          <p className={styles.lede}>
            I help you talk through your money and see what the month can hold.
          </p>
        </div>

        <div className={styles.ctaBlock}>
          <Button variant="start" onClick={onStart} disabled={busy}>
            {busy ? "Starting…" : "Start a call"}
          </Button>
          <p className={styles.ctaHint}>Uses your microphone</p>
        </div>
      </div>
    </main>
  );
}
