"use client";

import { useEffect, useRef } from "react";
import {
  isEmpty,
  turnCaption,
  type Transcript,
} from "@/lib/transcript";
import styles from "./shells.module.css";

type CaptionStreamProps = {
  transcript: Transcript;
  /** Shorter strip under the plan once the calendar owns the room. */
  compact?: boolean;
  /** Shown when there is nothing to caption yet. */
  idle?: string;
  agentSpeaking?: boolean;
  userSpeaking?: boolean;
};

/**
 * Live captions for the call: both speakers, newest at the bottom, older
 * lines scroll up under a fade. No scrollbar — the eye follows the voice.
 *
 * Text split (spoken vs still in flight) comes from `turnCaption`; this
 * component only lays that out.
 */
export function CaptionStream({
  transcript,
  compact = false,
  idle = "Listening",
  agentSpeaking = false,
  userSpeaking = false,
}: CaptionStreamProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const lines = transcript.filter((turn) => !isEmpty(turn));

  // Stick to the live edge whenever a word lands or an interim revises.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [transcript, idle]);

  return (
    <div
      className={compact ? styles.captionsCompact : styles.captions}
      aria-live="polite"
      aria-relevant="additions text"
    >
      <div className={styles.captionsScroll} ref={scrollerRef}>
        <div className={styles.captionsStack}>
          {lines.length === 0 ? (
            <p className={styles.captionIdle}>{idle}</p>
          ) : (
            lines.map((turn, index) => {
              const { spoken, pending } = turnCaption(turn);
              if (!spoken && !pending) return null;
              const last = index === lines.length - 1;
              const live =
                last &&
                ((turn.role === "agent" && agentSpeaking) ||
                  (turn.role === "user" && userSpeaking));
              return (
                <div
                  key={turn.id}
                  className={styles.captionLine}
                  data-role={turn.role}
                  data-live={live || undefined}
                >
                  <span className={styles.captionWho}>
                    {turn.role === "agent" ? "Kubera" : "You"}
                  </span>
                  <p className={styles.captionText}>
                    {spoken}
                    {pending ? (
                      <span className={styles.captionGhost}>
                        {spoken ? " " : ""}
                        {pending}
                      </span>
                    ) : null}
                  </p>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
