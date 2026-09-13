"use client";

import { useState } from "react";
import Image from "next/image";
import { Button } from "@/components/atoms";
import { FinancePanel } from "@/components/cards";
import { EMPTY_SNAPSHOT, type FinanceSnapshot } from "@/lib/finance";
import { turnText, type Transcript } from "@/lib/transcript";
import { AppFrame } from "./AppFrame";
import styles from "./shells.module.css";

type EndedShellProps = {
  durationSeconds: number;
  transcript?: Transcript;
  finance?: FinanceSnapshot;
  reason?: "user" | "agent" | "dropped";
  onRestart: () => void;
  error?: string | null;
};

function formatDuration(total: number): string {
  const safe = Math.max(0, Math.floor(total));
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  if (m === 0) return `${s}s`;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

function headline(reason: EndedShellProps["reason"], error?: string | null) {
  if (error || reason === "dropped") return "The call dropped";
  if (reason === "agent") return "Kubera signed off";
  return "Call ended";
}

export function EndedShell({
  durationSeconds,
  transcript = [],
  finance = EMPTY_SNAPSHOT,
  reason = "user",
  onRestart,
  error,
}: EndedShellProps) {
  const [showTranscript, setShowTranscript] = useState(false);
  const lines = transcript.filter((turn) => turnText(turn) !== "");
  const dropped = Boolean(error) || reason === "dropped";
  // The call is over but the plan is the point of it — it stays on screen to
  // be read properly, rather than vanishing with the audio.
  const hasPlan = finance.facts.length > 0;

  return (
    <AppFrame>
      <div className={styles.body}>
        <Image
          src="/kubera-logo.png"
          alt=""
          width={64}
          height={64}
          style={{ borderRadius: 14, objectFit: "cover" }}
        />
        <div>
          <h1 className={styles.title}>{headline(reason, error)}</h1>
          <p className={styles.subtitle}>
            {hasPlan
              ? `You talked for ${formatDuration(durationSeconds)}. Your month is below — take your time with it.`
              : durationSeconds > 0
                ? `You talked for ${formatDuration(durationSeconds)}. Start again whenever you want.`
                : "Start again whenever you want."}
          </p>
          {dropped && error ? (
            <p className={styles.errorBanner} role="alert">
              {error}
            </p>
          ) : null}
        </div>

        <div className={styles.actions}>
          <Button variant="primary" onClick={onRestart}>
            {dropped ? "Try again" : "Back to start"}
          </Button>
          {lines.length > 0 ? (
            <Button
              variant="secondary"
              onClick={() => setShowTranscript((v) => !v)}
              aria-expanded={showTranscript}
            >
              {showTranscript ? "Hide transcript" : "Read transcript"}
            </Button>
          ) : null}
        </div>

        {hasPlan ? (
          <div className={styles.planReview}>
            <FinancePanel snapshot={finance} />
          </div>
        ) : null}

        {showTranscript && lines.length > 0 ? (
          <div className={styles.recap}>
            {lines.map((turn) => (
              <p key={turn.id} className={styles.recapLine}>
                <span className={styles.recapSpeaker}>
                  {turn.role === "agent" ? "Kubera" : "You"}
                </span>
                <span>{turnText(turn)}</span>
              </p>
            ))}
          </div>
        ) : null}
      </div>
    </AppFrame>
  );
}
