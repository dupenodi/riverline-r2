"use client";

import { useEffect, type ReactNode } from "react";
import { CallTimer } from "@/components/atoms";
import { PlanView } from "@/components/plan/PlanView";
import type { LevelMeter } from "@/lib/audio-level";
import type { FinanceSnapshot } from "@/lib/finance";
import { isEmpty, type Transcript } from "@/lib/transcript";
import { AppFrame } from "./AppFrame";
import { CaptionStream } from "./CaptionStream";
import styles from "./shells.module.css";

/**
 * The call.
 *
 * While there is no plan, the centre is live captions — Kubera and the user,
 * stacked like subtitles, newest at the bottom. Once a plan exists it takes
 * the room and the captions shrink to a strip under it.
 *
 * Mute and end stay in the dock. Status that used to live in a hearing strip
 * (Listening / Thinking / speaking) sits in the caption idle line instead.
 */

type CallShellProps = {
  elapsedSeconds: number;
  muted: boolean;
  agentSpeaking: boolean;
  userSpeaking: boolean;
  thinking: boolean;
  transcript: Transcript;
  finance: FinanceSnapshot;
  /** The ledger rail, owned by AppShell so it outlives the call. */
  sidebar?: ReactNode;
  /** Kept for the call API; loudness bars left with the old hearing strip. */
  micMeter?: LevelMeter | null;
  connectionLabel?: string;
  notice?: string | null;
  onMute: () => void;
  onEnd: () => void;
  ending?: boolean;
};

function status(
  muted: boolean,
  agentSpeaking: boolean,
  thinking: boolean,
  ending: boolean,
  hasLines: boolean,
): string {
  if (ending) return "Ending";
  if (muted) return "Muted";
  if (agentSpeaking) return "Kubera is speaking";
  if (thinking) return "Thinking";
  if (!hasLines) return "One moment — getting the line ready.";
  return "Listening";
}

export function CallShell({
  elapsedSeconds,
  muted,
  agentSpeaking,
  userSpeaking,
  thinking,
  transcript,
  finance,
  sidebar = null,
  micMeter: _micMeter = null,
  connectionLabel = "Connected",
  notice = null,
  onMute,
  onEnd,
  ending = false,
}: CallShellProps) {
  const planned = finance.plan != null;
  const hasLines = transcript.some((turn) => !isEmpty(turn));
  const idle = status(muted, agentSpeaking, thinking, ending, hasLines);

  useEffect(() => {
    if (ending) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.isContentEditable) return;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;

      if (event.key === "m" || event.key === "M") {
        event.preventDefault();
        onMute();
      } else if (event.key === "e" || event.key === "E") {
        event.preventDefault();
        onEnd();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ending, onEnd, onMute]);

  return (
    <AppFrame
      // Once the plan is up it wants the full width; the rail has said
      // everything it has to say and the calendar repeats it in context.
      sidebar={planned ? null : sidebar}
      meta={
        <>
          <span
            className={styles.wire}
            data-live={!muted && !ending}
            data-muted={muted}
          >
            <i aria-hidden />
            {muted ? "Muted" : connectionLabel}
          </span>
          <CallTimer seconds={elapsedSeconds} />
        </>
      }
    >
      {planned ? (
        <div className={styles.planScroll}>
          <PlanView snapshot={finance} />
        </div>
      ) : null}

      <CaptionStream
        transcript={transcript}
        compact={planned}
        idle={idle}
        agentSpeaking={agentSpeaking}
        userSpeaking={userSpeaking && !muted && !ending}
      />

      {notice ? (
        <p className={styles.notice} role="status">
          {notice}
        </p>
      ) : null}

      <div className={styles.dock}>
        <button
          type="button"
          className={styles.ctl}
          onClick={onMute}
          aria-pressed={muted}
          disabled={ending}
        >
          {muted ? "Unmute" : "Mute"}
          <kbd>M</kbd>
        </button>
        <button
          type="button"
          className={styles.ctlEnd}
          onClick={onEnd}
          disabled={ending}
        >
          {ending ? "Ending…" : "End call"}
          <kbd>E</kbd>
        </button>
      </div>
    </AppFrame>
  );
}
