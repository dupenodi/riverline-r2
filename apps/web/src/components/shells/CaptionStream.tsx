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
  compact?: boolean;
  idle?: string;
  agentSpeaking?: boolean;
  userSpeaking?: boolean;
};

/** Live captions; spoken vs pending from `turnCaption`. */
export function CaptionStream({
  transcript,
  compact = false,
  idle,
  agentSpeaking = false,
  userSpeaking = false,
}: CaptionStreamProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const lines = transcript.filter((turn) => !isEmpty(turn));

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
            idle ? <p className={styles.captionIdle}>{idle}</p> : null
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
