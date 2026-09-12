"use client";

import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import type { Transcript, Turn } from "@/lib/transcript";
import styles from "./atoms.module.css";

type TranscriptPanelProps = {
  transcript: Transcript;
  agentName?: string;
};

/** Distance from the bottom within which we keep following new text. */
const STICK_THRESHOLD_PX = 48;

export function TranscriptPanel({
  transcript,
  agentName = "Kubera",
}: TranscriptPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    // Reading back? Stop yanking the view down. Scroll back to the bottom to
    // resume following.
    stick.current = distance <= STICK_THRESHOLD_PX;
  }, []);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el || !stick.current) return;
    el.scrollTop = el.scrollHeight;
  }, [transcript]);

  useEffect(() => {
    stick.current = true;
  }, []);

  if (transcript.length === 0) return null;

  return (
    <div className={styles.transcript}>
      <div className={styles.transcriptFade} aria-hidden />
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className={styles.transcriptScroll}
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        aria-label="Live transcript"
        tabIndex={0}
      >
        {transcript.map((turn) => (
          <TurnLine key={turn.id} turn={turn} agentName={agentName} />
        ))}
      </div>
    </div>
  );
}

function TurnLine({ turn, agentName }: { turn: Turn; agentName: string }) {
  const isAgent = turn.role === "agent";
  return (
    <p
      className={[
        styles.turn,
        isAgent ? styles.turnAgent : styles.turnUser,
        turn.closed ? "" : styles.turnLive,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span className={styles.turnSpeaker}>{isAgent ? agentName : "You"}</span>
      <span className={styles.turnBody}>
        {turn.segments.map((segment, index) => {
          // The spoken cursor comes from the RTVI spoken_progress field: text
          // ahead of it is dimmed, so the caption never claims Kubera has said
          // something it is still working through.
          const spoken =
            index < turn.spokenParts
              ? segment.text.length
              : index === turn.spokenParts
                ? turn.spokenChars
                : 0;
          const said = segment.text.slice(0, spoken);
          const pending = segment.text.slice(spoken);
          return (
            <span key={segment.id}>
              {said}
              {pending ? (
                <span className={styles.turnPending}>{pending}</span>
              ) : null}{" "}
            </span>
          );
        })}
        {turn.draft ? (
          <span className={styles.turnDraft}>{turn.draft}</span>
        ) : null}
        {turn.interrupted ? (
          <span className={styles.turnCut} aria-label="interrupted">
            {" "}
            —
          </span>
        ) : null}
      </span>
    </p>
  );
}
