"use client";

import type { ReactNode } from "react";
import { useFlash } from "@/lib/use-flash";
import styles from "./cards.module.css";

type CardProps = {
  title: string;
  /** Changes to this string make the card pulse. Usually the rendered figures. */
  signature: string;
  note?: ReactNode;
  tone?: "plain" | "good" | "warn" | "bad";
  children: ReactNode;
};

export function Card({
  title,
  signature,
  note,
  tone = "plain",
  children,
}: CardProps) {
  const flashing = useFlash(signature);
  return (
    <section
      className={[
        styles.card,
        styles[`tone_${tone}`],
        flashing ? styles.flash : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <header className={styles.cardHead}>
        <h2 className={styles.cardTitle}>{title}</h2>
        {note ? <span className={styles.cardNote}>{note}</span> : null}
      </header>
      {children}
    </section>
  );
}
