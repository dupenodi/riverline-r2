"use client";

import { useCallback, useState } from "react";
import {
  createSession,
  endSession,
  getAgentUrl,
  type CallUiStatus,
  type SessionCreated,
} from "@/lib/agent-api";
import styles from "./VoiceCall.module.css";

/**
 * Session UI scaffold: POST /sessions → (Pipecat connect TODO) → DELETE /sessions/{id}.
 */
export function VoiceCall() {
  const [status, setStatus] = useState<CallUiStatus>("idle");
  const [session, setSession] = useState<SessionCreated | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleStart = useCallback(async () => {
    setStatus("starting");
    setMessage(null);
    setSession(null);

    try {
      const created = await createSession();
      setSession(created);
      setStatus("connecting");

      // TODO: PipecatClient + DailyTransport
      // await client.connect({ url: created.room.url, token: created.client.token })

      setStatus("ready");
      setMessage(
        `Session ${created.session_id.slice(0, 8)}… ready (scaffold — no WebRTC yet).`,
      );
    } catch (err) {
      setStatus("error");
      setMessage(
        err instanceof Error
          ? err.message
          : "Could not reach agent. Is it running on :7860?",
      );
    }
  }, []);

  const handleEnd = useCallback(async () => {
    if (!session) {
      setStatus("idle");
      return;
    }

    setStatus("ending");
    try {
      // TODO: await client.disconnect()
      await endSession(session.session_id);
      setSession(null);
      setStatus("idle");
      setMessage("Call ended.");
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Failed to end session");
    }
  }, [session]);

  const showEnd = status === "ready" || status === "connecting" || status === "ending";

  return (
    <section className={styles.panel}>
      <div className={styles.actions}>
        {showEnd ? (
          <button
            type="button"
            className={styles.buttonDanger}
            onClick={handleEnd}
            disabled={status === "ending" || status === "connecting"}
          >
            {status === "ending" ? "Ending…" : "End call"}
          </button>
        ) : (
          <button
            type="button"
            className={styles.button}
            onClick={handleStart}
            disabled={status === "starting"}
          >
            {status === "starting" ? "Starting…" : "Start call"}
          </button>
        )}
      </div>
      {message ? (
        <p className={status === "error" ? styles.error : styles.hint}>
          {message}
        </p>
      ) : (
        <p className={styles.hint}>
          <code>POST/DELETE {getAgentUrl()}/sessions</code> — Daily + Pipecat
          next.
        </p>
      )}
    </section>
  );
}
