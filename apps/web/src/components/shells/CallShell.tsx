"use client";

import { useEffect } from "react";
import Image from "next/image";
import { CallTimer } from "@/components/atoms";
import { MoneyBoard } from "@/components/transactions/MoneyBoard";
import type { LevelMeter } from "@/lib/audio-level";
import {
  callMood,
  moodLabel,
  moodMascot,
  moodPulses,
} from "@/lib/call-mood";
import { hasBoard, type TransactionsState } from "@/lib/transactions";
import { isEmpty, type Transcript } from "@/lib/transcript";
import { AppFrame } from "./AppFrame";
import { CaptionStream } from "./CaptionStream";
import styles from "./shells.module.css";

type CallShellProps = {
  elapsedSeconds: number;
  muted: boolean;
  agentSpeaking: boolean;
  userSpeaking: boolean;
  thinking: boolean;
  transcript: Transcript;
  transactions: TransactionsState;
  micMeter?: LevelMeter | null;
  connectionLabel?: string;
  notice?: string | null;
  onMute: () => void;
  onEnd: () => void;
  ending?: boolean;
};

export function CallShell({
  elapsedSeconds,
  muted,
  agentSpeaking,
  userSpeaking,
  thinking,
  transcript,
  transactions,
  micMeter: _micMeter = null,
  connectionLabel = "Connected",
  notice = null,
  onMute,
  onEnd,
  ending = false,
}: CallShellProps) {
  const hasMoney = hasBoard(transactions);
  const hasLines = transcript.some((turn) => !isEmpty(turn));
  const youSpeaking = userSpeaking && !muted && !ending;
  const mood = callMood({
    ending,
    muted,
    agentSpeaking,
    thinking,
    userSpeaking: youSpeaking,
    hasLines,
  });
  const label = moodLabel(mood);

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
    <AppFrame>
      {hasMoney ? (
        <div className={styles.planScroll}>
          <MoneyBoard state={transactions} />
        </div>
      ) : (
        <div className={styles.talkStage}>
          <div className={styles.talkHead}>
            <Image
              src={moodMascot(mood)}
              alt=""
              width={88}
              height={88}
              className={[
                styles.talkMascot,
                moodPulses(mood) ? styles.talkMascotPulse : "",
              ]
                .filter(Boolean)
                .join(" ")}
              priority
            />
            <p className={styles.talkMood} data-mood={mood} role="status">
              {label}
            </p>
          </div>

          <CaptionStream
            transcript={transcript}
            agentSpeaking={agentSpeaking}
            userSpeaking={youSpeaking}
          />
        </div>
      )}

      {hasMoney ? (
        <CaptionStream
          transcript={transcript}
          compact
          idle={label}
          agentSpeaking={agentSpeaking}
          userSpeaking={youSpeaking}
        />
      ) : null}

      {notice ? (
        <p className={styles.notice} role="status">
          {notice}
        </p>
      ) : null}

      <div className={styles.dock}>
        <div className={styles.dockMeta}>
          <span
            className={styles.wire}
            data-live={!muted && !ending}
            data-muted={muted}
          >
            <i aria-hidden />
            {muted ? "Muted" : connectionLabel}
          </span>
          <CallTimer seconds={elapsedSeconds} />
        </div>
        <div className={styles.dockActions}>
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
      </div>
    </AppFrame>
  );
}
