"use client";

import { useState, type ReactNode } from "react";
import Image from "next/image";
import { Button } from "@/components/atoms";
import { PlanView } from "@/components/plan/PlanView";
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
  /** The finance panel. The call is over but the plan is the point of it, so
      it stays exactly where the user has been reading it all along. */
  sidebar?: ReactNode;
  sidebarVersion?: number;
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
  sidebar = null,
  sidebarVersion = 0,
}: EndedShellProps) {
  const [showTranscript, setShowTranscript] = useState(false);
  const lines = transcript.filter((turn) => turnText(turn) !== "");
  const dropped = Boolean(error) || reason === "dropped";
  const hasPlan = finance.plan != null;
  const hasFacts = finance.facts.length > 0;

  // The plan is the point of the call, so hanging up must not throw it away.
  // It stays exactly where it was being read, full width, and the sign-off
  // becomes a line above it rather than a screen of its own.
  if (hasPlan) {
    return (
      <AppFrame sidebar={null}>
        <div className={styles.endedPlan}>
          <div className={styles.endedBar}>
            <div>
              <h1 className={styles.endedTitle}>{headline(reason, error)}</h1>
              <p className={styles.endedMeta}>
                {durationSeconds > 0
                  ? `You talked for ${formatDuration(durationSeconds)}. This is yours to keep.`
                  : "This is yours to keep."}
              </p>
            </div>
            <div className={styles.actions}>
              {lines.length > 0 ? (
                <Button
                  variant="secondary"
                  onClick={() => setShowTranscript((v) => !v)}
                  aria-expanded={showTranscript}
                >
                  {showTranscript ? "Hide transcript" : "Read transcript"}
                </Button>
              ) : null}
              <Button variant="primary" onClick={onRestart}>
                {dropped ? "Try again" : "Start again"}
              </Button>
            </div>
          </div>

          {dropped && error ? (
            <p className={styles.errorBanner} role="alert">
              {error}
            </p>
          ) : null}

          <PlanView snapshot={finance} />

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

  return (
    <AppFrame sidebar={sidebar} sidebarVersion={sidebarVersion}>
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
            {hasFacts
              ? `You talked for ${formatDuration(durationSeconds)}. What you told me is still on the right.`
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
            {dropped ? "Try again" : "Start again"}
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
