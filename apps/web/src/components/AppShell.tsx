"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import { DailyTransport } from "@pipecat-ai/daily-transport";
import { WelcomeScreen } from "@/components/WelcomeScreen";
import { CallShell } from "@/components/shells/CallShell";
import { ConnectingShell } from "@/components/shells/ConnectingShell";
import { EndedShell } from "@/components/shells/EndedShell";
import { MicBlockedShell } from "@/components/shells/MicBlockedShell";
import {
  createSession,
  endSession,
  endSessionBeacon,
  type SessionCreated,
} from "@/lib/agent-api";
import { LevelMeter } from "@/lib/audio-level";
import {
  acceptSnapshot,
  EMPTY_SNAPSHOT,
  type FinanceSnapshot,
} from "@/lib/finance";
import {
  agentSegment,
  agentTurnEnded,
  agentTurnStarted,
  interrupted,
  userFinal,
  userInterim,
  userSpeaking,
  type Transcript,
} from "@/lib/transcript";

type Phase =
  | "idle"
  | "mic_blocked"
  | "connecting"
  | "ready"
  | "ending"
  | "ended"
  | "error";

type ConnectStep = "mic" | "session" | "room" | "assistant";

type EndReason = "user" | "agent" | "dropped";

function isScaffoldRoom(url: string): boolean {
  return (
    url.includes("example.daily.co") ||
    url.includes("scaffold") ||
    !url.includes("daily.co")
  );
}

async function requestMic(): Promise<boolean> {
  if (!navigator.mediaDevices?.getUserMedia) return false;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    for (const track of stream.getTracks()) track.stop();
    return true;
  } catch {
    return false;
  }
}

export function AppShell() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [connectStep, setConnectStep] = useState<ConnectStep>("mic");
  const [session, setSession] = useState<SessionCreated | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [endReason, setEndReason] = useState<EndReason>("user");
  const [muted, setMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [lastDuration, setLastDuration] = useState(0);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [userTalking, setUserTalking] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [scaffoldMode, setScaffoldMode] = useState(false);
  const [transcript, setTranscript] = useState<Transcript>([]);
  const [finance, setFinance] = useState<FinanceSnapshot>(EMPTY_SNAPSHOT);

  const clientRef = useRef<PipecatClient | null>(null);
  const botAudioElRef = useRef<HTMLAudioElement | null>(null);
  const sessionRef = useRef<SessionCreated | null>(null);
  const callStartedAt = useRef<number | null>(null);
  const cancelledRef = useRef(false);
  const agentSpeakingRef = useRef(false);

  const micMeter = useMemo(() => new LevelMeter(), []);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    agentSpeakingRef.current = agentSpeaking;
  }, [agentSpeaking]);

  // The clock starts when the call does (see `goLive`); this only keeps it ticking.
  useEffect(() => {
    if (phase !== "ready") return;
    const id = window.setInterval(() => {
      if (callStartedAt.current == null) return;
      setElapsed(Math.floor((Date.now() - callStartedAt.current) / 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, [phase]);

  // A closed tab is still a live Daily room and a live bot on the server, so
  // the session gets one last best-effort DELETE on the way out.
  useEffect(() => {
    const release = () => {
      const current = sessionRef.current;
      if (current) endSessionBeacon(current.session_id);
    };
    window.addEventListener("pagehide", release);
    return () => window.removeEventListener("pagehide", release);
  }, []);

  const detachBotAudio = useCallback(() => {
    const el = botAudioElRef.current;
    botAudioElRef.current = null;
    if (!el) return;
    el.pause();
    el.srcObject = null;
    el.remove();
  }, []);

  const teardownClient = useCallback(async () => {
    detachBotAudio();
    micMeter.reset();
    const client = clientRef.current;
    clientRef.current = null;
    if (!client) return;
    try {
      await client.disconnect();
    } catch {
      /* already gone */
    }
  }, [detachBotAudio, micMeter]);

  const resetToIdle = useCallback(() => {
    cancelledRef.current = false;
    setPhase("idle");
    setConnectStep("mic");
    setSession(null);
    setError(null);
    setNotice(null);
    setEndReason("user");
    setMuted(false);
    setElapsed(0);
    setAgentSpeaking(false);
    setUserTalking(false);
    setThinking(false);
    setScaffoldMode(false);
    setTranscript([]);
    setFinance(EMPTY_SNAPSHOT);
    callStartedAt.current = null;
  }, []);

  /** Everything is up: start the clock and show the call screen. */
  const goLive = useCallback(() => {
    callStartedAt.current = Date.now();
    setElapsed(0);
    setPhase("ready");
  }, []);

  const handleCancelConnect = useCallback(async () => {
    cancelledRef.current = true;
    await teardownClient();
    const current = sessionRef.current;
    if (current) {
      try {
        await endSession(current.session_id);
      } catch {
        /* ignore */
      }
    }
    resetToIdle();
  }, [resetToIdle, teardownClient]);

  /** Wind the call down. `reason` decides what the ended screen says. */
  const closeCall = useCallback(
    async (reason: EndReason) => {
      setPhase((current) =>
        current === "ending" || current === "ended" ? current : "ending",
      );
      setAgentSpeaking(false);
      setUserTalking(false);
      setThinking(false);
      setEndReason(reason);

      const duration =
        callStartedAt.current != null
          ? Math.floor((Date.now() - callStartedAt.current) / 1000)
          : 0;
      setLastDuration(duration);

      await teardownClient();

      const current = sessionRef.current;
      if (current) {
        try {
          await endSession(current.session_id);
        } catch (err) {
          setError(
            err instanceof Error ? err.message : "Failed to end the session.",
          );
        }
      }

      setSession(null);
      setPhase("ended");
    },
    [teardownClient],
  );

  const startCall = useCallback(async () => {
    cancelledRef.current = false;
    setError(null);
    setNotice(null);
    setMuted(false);
    setAgentSpeaking(false);
    setUserTalking(false);
    setThinking(false);
    setTranscript([]);
    setFinance(EMPTY_SNAPSHOT);
    setPhase("connecting");
    setConnectStep("mic");

    const micOk = await requestMic();
    if (cancelledRef.current) return;
    if (!micOk) {
      setPhase("mic_blocked");
      return;
    }

    setConnectStep("session");
    let created: SessionCreated;
    try {
      created = await createSession();
    } catch (err) {
      if (cancelledRef.current) return;
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach the agent. Is it running on :7860?",
      );
      setPhase("error");
      return;
    }

    if (cancelledRef.current) {
      try {
        await endSession(created.session_id);
      } catch {
        /* ignore */
      }
      return;
    }

    setSession(created);
    setConnectStep("room");

    const scaffold = isScaffoldRoom(created.room.url);
    setScaffoldMode(scaffold);

    if (scaffold) {
      await new Promise((r) => setTimeout(r, 600));
      if (cancelledRef.current) return;
      setConnectStep("assistant");
      await new Promise((r) => setTimeout(r, 400));
      if (cancelledRef.current) return;
      goLive();
      return;
    }

    const client = new PipecatClient({
      transport: new DailyTransport(),
      enableMic: true,
      enableCam: false,
      callbacks: {
        // Official Daily client pattern: attach remote audio yourself.
        // https://docs.pipecat.ai/api-reference/client/js/overview
        onTrackStarted: (track, participant) => {
          if (!participant || participant.local || track.kind !== "audio") {
            return;
          }
          detachBotAudio();
          const audioElement = document.createElement("audio");
          audioElement.autoplay = true;
          audioElement.srcObject = new MediaStream([track]);
          document.body.appendChild(audioElement);
          botAudioElRef.current = audioElement;
          void audioElement.play().catch(() => {
            // Autoplay blocked: the call is up but silent, which is worth
            // saying out loud rather than letting the user wonder.
            setNotice("Tap anywhere to let this page play audio.");
          });
        },
        onTrackStopped: (track, participant) => {
          if (!participant || participant.local || track.kind !== "audio") {
            return;
          }
          detachBotAudio();
        },
        onBotReady: () => {
          setConnectStep("assistant");
        },

        // Loudness, sampled by the Daily transport at 10 Hz. Kept out of React
        // state so the visuals animate without re-rendering the call screen.
        onLocalAudioLevel: (level) => micMeter.set(level),

        onBotStartedSpeaking: () => {
          setAgentSpeaking(true);
          setThinking(false);
        },
        onBotStoppedSpeaking: () => {
          setAgentSpeaking(false);
          setTranscript((prev) => agentTurnEnded(prev));
        },
        onBotLlmStarted: () => {
          setThinking(true);
          setTranscript((prev) => agentTurnStarted(prev));
        },
        onBotLlmStopped: () => setThinking(false),

        onUserStartedSpeaking: () => {
          setUserTalking(true);
          setTranscript((prev) =>
            // Talking over Kubera ends its turn where the audio actually
            // stopped, instead of letting the caption run on.
            agentSpeakingRef.current
              ? userSpeaking(interrupted(prev))
              : userSpeaking(prev),
          );
        },
        onUserStoppedSpeaking: () => {
          setUserTalking(false);
          micMeter.reset();
        },
        onUserTranscript: (data) => {
          setTranscript((prev) =>
            data.final ? userFinal(prev, data.text) : userInterim(prev, data.text),
          );
        },

        onBotOutput: (data) => {
          // The RTVI contract, applied as written (see lib/transcript.ts):
          //   "new" / never-spoken  → create the segment
          //   in-progress/completed → advance spoken only (id may differ)
          const id =
            data.segment_id === undefined || data.segment_id === null
              ? data.text
              : String(data.segment_id);
          const text = data.text ?? "";
          const status = data.spoken_status;
          const willBeSpoken = data.will_be_spoken ?? data.spoken ?? true;

          // Text that never reaches TTS is on screen the moment it arrives;
          // there will be no progress message to mark it said.
          if (!willBeSpoken || status === undefined || status === null) {
            setTranscript((prev) =>
              agentSegment(prev, { id, text, spoken: text, create: true }),
            );
            return;
          }

          if (status === "new") {
            setTranscript((prev) =>
              agentSegment(prev, { id, text, spoken: "", create: true }),
            );
            return;
          }

          const accumulated = data.spoken_progress?.accumulated_text;
          const spoken =
            status === "completed" ? text : (accumulated ?? "");

          setTranscript((prev) =>
            agentSegment(prev, { id, text, spoken, create: false }),
          );
        },

        onServerMessage: (data) => {
          const message = data as { type?: string; state?: unknown } | null;

          // The whole picture arrives as one versioned snapshot after every
          // change, and the cards are a pure function of it. Nothing here
          // recomputes money: a second implementation of the maths in the
          // browser could disagree with the tested one.
          if (message?.type === "finance_state") {
            setFinance((current) => acceptSnapshot(current, message.state));
          }
        },
        onError: (message) => {
          const data = message?.data as
            | { error?: string; fatal?: boolean }
            | undefined;
          const detail = data?.error ?? "Something went wrong on the call.";
          if (data?.fatal) {
            setError(detail);
            void closeCall("dropped");
          } else {
            setNotice(detail);
          }
        },
        onBotDisconnected: () => {
          setError("Kubera dropped off the call.");
          void closeCall("dropped");
        },
        onDisconnected: () => {
          // Only meaningful if we did not ask for it.
          if (clientRef.current) void closeCall("dropped");
        },
      },
    });

    clientRef.current = client;

    try {
      await client.connect({
        url: created.room.url,
        token: created.client.token,
      });
      if (cancelledRef.current) {
        await teardownClient();
        return;
      }
      setConnectStep("assistant");
      goLive();
    } catch (err) {
      if (cancelledRef.current) return;
      await teardownClient();
      try {
        await endSession(created.session_id);
      } catch {
        /* ignore */
      }
      setSession(null);
      setError(
        err instanceof Error ? err.message : "Could not join the voice room.",
      );
      setPhase("error");
    }
  }, [closeCall, detachBotAudio, goLive, micMeter, teardownClient]);

  const handleEnd = useCallback(() => {
    if (phase === "ending" || phase === "ended") return;
    void closeCall("user");
  }, [closeCall, phase]);

  const handleMute = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      const client = clientRef.current;
      if (client) {
        try {
          client.enableMic(!next);
        } catch {
          /* scaffold / no transport */
        }
      }
      if (next) micMeter.reset();
      return next;
    });
  }, [micMeter]);

  if (phase === "idle") {
    return <WelcomeScreen onStart={startCall} />;
  }

  if (phase === "mic_blocked") {
    return <MicBlockedShell onRetry={startCall} onBack={resetToIdle} />;
  }

  if (phase === "connecting") {
    return (
      <ConnectingShell step={connectStep} onCancel={handleCancelConnect} />
    );
  }

  if (phase === "ready" || phase === "ending") {
    return (
      <CallShell
        elapsedSeconds={elapsed}
        muted={muted}
        agentSpeaking={agentSpeaking}
        userSpeaking={userTalking}
        thinking={thinking}
        transcript={transcript}
        finance={finance}
        micMeter={micMeter}
        connectionLabel={scaffoldMode ? "Scaffold" : "Connected"}
        notice={notice}
        onMute={handleMute}
        onEnd={handleEnd}
        ending={phase === "ending"}
      />
    );
  }

  if (phase === "ended" || phase === "error") {
    return (
      <EndedShell
        durationSeconds={lastDuration}
        transcript={transcript}
        finance={finance}
        reason={phase === "error" ? "dropped" : endReason}
        onRestart={resetToIdle}
        error={error}
      />
    );
  }

  return null;
}
