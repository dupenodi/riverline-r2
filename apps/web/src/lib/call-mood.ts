export type CallMood =
  | "ending"
  | "muted"
  | "speaking"
  | "working"
  | "user"
  | "waiting"
  | "listening";

type CallMoodInput = {
  ending?: boolean;
  muted?: boolean;
  agentSpeaking?: boolean;
  thinking?: boolean;
  userSpeaking?: boolean;
  hasLines?: boolean;
};

/** Priority: ending → muted → Kubera speaking → working → you → waiting/listening. */
export function callMood({
  ending = false,
  muted = false,
  agentSpeaking = false,
  thinking = false,
  userSpeaking = false,
  hasLines = false,
}: CallMoodInput): CallMood {
  if (ending) return "ending";
  if (muted && !agentSpeaking) return "muted";
  if (agentSpeaking) return "speaking";
  if (thinking) return "working";
  if (userSpeaking) return "user";
  if (!hasLines) return "waiting";
  return "listening";
}

const COPY: Record<CallMood, string> = {
  ending: "Ending…",
  muted: "You're muted",
  speaking: "Kubera is talking…",
  working: "One sec…",
  user: "Go ahead…",
  waiting: "One moment…",
  listening: "Listening…",
};

export function moodLabel(mood: CallMood): string {
  return COPY[mood];
}

/** Thinking art while Kubera is working; logo otherwise. */
export function moodMascot(mood: CallMood): "/kubera-thinking.png" | "/kubera-logo.png" {
  return mood === "working" ? "/kubera-thinking.png" : "/kubera-logo.png";
}

export function moodPulses(mood: CallMood): boolean {
  return mood === "working" || mood === "waiting";
}
