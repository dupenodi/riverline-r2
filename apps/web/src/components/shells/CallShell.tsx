"use client";

import { useEffect } from "react";
import {
  AmbientBackdrop,
  BreathingOrb,
  CallTimer,
  Dock,
  InputWave,
  StatusDot,
  TranscriptPanel,
  type OrbState,
  type VoiceMood,
} from "@/components/atoms";
import type { LevelMeter } from "@/lib/audio-level";
import type { Transcript } from "@/lib/transcript";
import { AppFrame } from "./AppFrame";
import styles from "./shells.module.css";

type CallShellProps = {
  elapsedSeconds: number;
  muted: boolean;
  agentSpeaking: boolean;
  userSpeaking: boolean;
  thinking: boolean;
  transcript: Transcript;
  micMeter?: LevelMeter | null;
  botMeter?: LevelMeter | null;
  connectionLabel?: string;
  notice?: string | null;
  onMute: () => void;
  onEnd: () => void;
  ending?: boolean;
};

type VoiceState = {
  muted: boolean;
  agentSpeaking: boolean;
  userSpeaking: boolean;
  thinking: boolean;
  ending: boolean;
};

function moodFor({ ending, muted, agentSpeaking }: VoiceState): VoiceMood {
  if (ending) return "ending";
  if (muted) return "muted";
  if (agentSpeaking) return "speaking";
  return "listening";
}

function statusLabel(state: VoiceState): string {
  if (state.ending) return "Ending";
  if (state.muted) return "Muted";
  if (state.agentSpeaking) return "Speaking";
  if (state.thinking) return "Thinking";
  if (state.userSpeaking) return "Hearing you";
  return "Listening";
}

function orbStateFor({
  ending,
  muted,
  agentSpeaking,
  thinking,
}: VoiceState): OrbState {
  if (ending) return "thinking";
  if (muted) return "muted";
  if (agentSpeaking) return "speaking";
  if (thinking) return "thinking";
  return "listening";
}

export function CallShell({
  elapsedSeconds,
  muted,
  agentSpeaking,
  userSpeaking,
  thinking,
  transcript,
  micMeter = null,
  botMeter = null,
  connectionLabel = "Connected",
  notice = null,
  onMute,
  onEnd,
  ending = false,
}: CallShellProps) {
  const hearing = userSpeaking && !muted && !ending;
  const state: VoiceState = {
    muted,
    agentSpeaking,
    userSpeaking: hearing,
    thinking: thinking && !agentSpeaking,
    ending,
  };
  const label = statusLabel(state);

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
      transparent
      meta={
        <>
          <StatusDot
            tone={muted ? "muted" : agentSpeaking ? "warn" : "success"}
            label={connectionLabel}
          />
          <CallTimer seconds={elapsedSeconds} />
        </>
      }
    >
      <div className={styles.callMain}>
        <AmbientBackdrop mood={moodFor(state)} active={hearing} />
        <div className={styles.callCenter}>
          <BreathingOrb
            state={orbStateFor(state)}
            size="lg"
            active={hearing}
            meter={agentSpeaking ? botMeter : micMeter}
          />
          <InputWave active={hearing} meter={micMeter} />
          <p className={styles.voiceStatus} aria-live="polite">
            {label}
          </p>
          {notice ? (
            <p className={styles.noticeBanner} role="status">
              {notice}
            </p>
          ) : null}
          <TranscriptPanel transcript={transcript} />
        </div>
        <Dock muted={muted} onMute={onMute} onEnd={onEnd} ending={ending} />
        <p className={styles.shortcutHint}>
          <kbd>M</kbd> mute · <kbd>E</kbd> end
        </p>
      </div>
    </AppFrame>
  );
}
