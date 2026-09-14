"use client";

import Image from "next/image";
import { Button } from "@/components/atoms";
import { MoneyCalendar } from "@/components/transactions/MoneyCalendar";
import {
  EMPTY_TRANSACTIONS,
  type TransactionsState,
} from "@/lib/transactions";
import { turnText, type Transcript } from "@/lib/transcript";
import { AppFrame } from "./AppFrame";
import styles from "./shells.module.css";

type EndedShellProps = {
  durationSeconds: number;
  transcript?: Transcript;
  transactions?: TransactionsState;
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
  transactions = EMPTY_TRANSACTIONS,
  reason = "user",
  onRestart,
  error,
}: EndedShellProps) {
  const lines = transcript.filter((turn) => turnText(turn) !== "");
  const dropped = Boolean(error) || reason === "dropped";
  const hasMoney = transactions.items.length > 0;
  const hasTurns = lines.length > 0;

  if (hasMoney) {
    return (
      <AppFrame>
        <div className={styles.callReview}>
          <div className={styles.callReviewBar}>
            <div>
              <h1 className={styles.callReviewTitle}>
                {headline(reason, error)}
              </h1>
              <p className={styles.callReviewMeta}>
                {durationSeconds > 0
                  ? `You talked for ${formatDuration(durationSeconds)}. This is yours to keep.`
                  : "This is yours to keep."}
              </p>
            </div>
            <Button variant="primary" onClick={onRestart}>
              {dropped ? "Try again" : "Start again"}
            </Button>
          </div>

          {dropped && error ? (
            <p className={styles.errorBanner} role="alert">
              {error}
            </p>
          ) : null}

          <div className={styles.planScroll}>
            <MoneyCalendar state={transactions} />
          </div>

          <div className={styles.recapCompact}>
            {hasTurns ? (
              lines.map((turn) => (
                <p key={turn.id} className={styles.recapLine}>
                  <span className={styles.recapSpeaker}>
                    {turn.role === "agent" ? "Kubera" : "You"}
                  </span>
                  <span>{turnText(turn)}</span>
                </p>
              ))
            ) : (
              <p className={styles.recapIdle}>No transcript for this call.</p>
            )}
          </div>
        </div>
      </AppFrame>
    );
  }

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
            {durationSeconds > 0
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
            {dropped ? "Try again" : "Start again"}
          </Button>
        </div>

        {hasTurns ? (
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
