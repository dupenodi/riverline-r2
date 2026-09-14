/** RTVI transcript state: interim replaces; progress advances spoken only. */

export type TurnRole = "user" | "agent";

export type Segment = {
  id: string;
  text: string;
  /** Voiced so far (server `accumulated_text`, not computed). */
  spoken: string;
};

export type Turn = {
  id: string;
  role: TurnRole;
  segments: Segment[];
  /** User only: current interim, replaced wholesale until a final. */
  interim: string;
  closed: boolean;
  interrupted: boolean;
};

export type Transcript = Turn[];

const MAX_TURNS = 60;

let seq = 0;
function nextId(role: TurnRole): string {
  seq += 1;
  return `${role}-${seq}`;
}

function newTurn(role: TurnRole): Turn {
  return {
    id: nextId(role),
    role,
    segments: [],
    interim: "",
    closed: false,
    interrupted: false,
  };
}

function join(parts: string[]): string {
  return parts
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ");
}

export function turnText(turn: Turn): string {
  return join([...turn.segments.map((s) => s.text), turn.interim]);
}

/** Spoken through the first unfinished assistant segment; users are all said. */
export function spokenText(turn: Turn): string {
  if (turn.role === "user") return turnText(turn);
  const parts: string[] = [];
  for (const segment of turn.segments) {
    parts.push(segment.spoken);
    if (segment.spoken.trim() !== segment.text.trim()) break;
  }
  return join(parts);
}

export function pendingText(turn: Turn): string {
  if (turn.role === "user") return "";
  const parts: string[] = [];
  let reached = false;
  for (const segment of turn.segments) {
    const done = segment.spoken.trim() === segment.text.trim();
    if (reached || !done) {
      parts.push(
        reached ? segment.text : segment.text.slice(segment.spoken.length),
      );
      reached = true;
    }
  }
  return join(parts);
}

export function isEmpty(turn: Turn): boolean {
  return turnText(turn) === "";
}

function closeOpen(transcript: Transcript): Transcript {
  return transcript
    .map((turn) => (turn.closed ? turn : commit(turn)))
    .filter((turn) => !isEmpty(turn));
}

/** Close a turn; promote leftover user interim rather than drop it. */
function commit(turn: Turn): Turn {
  if (turn.role !== "user" || !turn.interim.trim()) {
    return { ...turn, closed: true, interim: "" };
  }
  return {
    ...turn,
    closed: true,
    interim: "",
    segments: [
      ...turn.segments,
      {
        id: `${turn.id}-s${turn.segments.length}`,
        text: turn.interim,
        spoken: turn.interim,
      },
    ],
  };
}

function openTurn(transcript: Transcript, role: TurnRole): Transcript {
  const last = transcript[transcript.length - 1];
  if (last && last.role === role && !last.closed) return transcript;
  return [...closeOpen(transcript), newTurn(role)].slice(-MAX_TURNS);
}

function updateOpen(
  transcript: Transcript,
  role: TurnRole,
  fn: (turn: Turn) => Turn,
): Transcript {
  const opened = openTurn(transcript, role);
  const next = [...opened];
  next[next.length - 1] = fn(next[next.length - 1]);
  return next;
}

export function userSpeaking(transcript: Transcript): Transcript {
  return openTurn(transcript, "user");
}

/** Replace interim wholesale — never append. */
export function userInterim(transcript: Transcript, text: string): Transcript {
  return updateOpen(transcript, "user", (turn) => ({ ...turn, interim: text }));
}

export function userFinal(transcript: Transcript, text: string): Transcript {
  return updateOpen(transcript, "user", (turn) => {
    if (!text.trim()) return { ...turn, interim: "" };
    return {
      ...turn,
      interim: "",
      segments: [
        ...turn.segments,
        { id: `${turn.id}-s${turn.segments.length}`, text, spoken: text },
      ],
    };
  });
}

export function agentTurnStarted(transcript: Transcript): Transcript {
  return openTurn(transcript, "agent");
}

/**
 * Apply one `bot-output`. `create` true = append if new id; false = advance
 * spoken only (fallback: unfinished segment with same text — ids often differ).
 */
export function agentSegment(
  transcript: Transcript,
  {
    id,
    text,
    spoken,
    create = true,
  }: { id: string; text: string; spoken: string; create?: boolean },
): Transcript {
  if (!text.trim() && !spoken.trim()) return transcript;
  return updateOpen(transcript, "agent", (turn) => {
    let index = turn.segments.findIndex((segment) => segment.id === id);
    if (index === -1 && !create) {
      const want = text.trim();
      index = turn.segments.findIndex(
        (segment) =>
          segment.text.trim() === want &&
          segment.spoken.trim() !== segment.text.trim(),
      );
      if (index === -1) return turn;
      const existing = turn.segments[index];
      const segments = turn.segments.map((segment, i) =>
        i === index ? { ...existing, text, spoken } : segment,
      );
      return { ...turn, segments };
    }
    const segment: Segment = { id, text, spoken };
    const segments =
      index === -1
        ? [...turn.segments, segment]
        : turn.segments.map((existing, i) => (i === index ? segment : existing));
    return { ...turn, segments };
  });
}

export function agentTurnEnded(transcript: Transcript): Transcript {
  return closeOpen(transcript);
}

/** User barge-in; only marks interrupted if words were still pending. */
export function interrupted(transcript: Transcript): Transcript {
  const last = transcript[transcript.length - 1];
  if (!last || last.role !== "agent" || last.closed) return transcript;
  const cutShort = pendingText(last) !== "";
  const next = [...transcript];
  next[next.length - 1] = { ...last, interrupted: cutShort, closed: true };
  return next.filter((turn) => !isEmpty(turn));
}

export function turnCaption(turn: Turn): {
  spoken: string;
  pending: string;
} {
  if (turn.role === "user") {
    return {
      spoken: join(turn.segments.map((segment) => segment.text)),
      pending: turn.interim.trim(),
    };
  }
  if (turn.closed && !turn.interrupted) {
    return { spoken: turnText(turn), pending: "" };
  }
  return { spoken: spokenText(turn), pending: pendingText(turn) };
}

export function lastAgentLine(transcript: Transcript): {
  spoken: string;
  pending: string;
} {
  for (let i = transcript.length - 1; i >= 0; i -= 1) {
    const turn = transcript[i];
    if (turn.role !== "agent" || isEmpty(turn)) continue;
    return turnCaption(turn);
  }
  return { spoken: "", pending: "" };
}

export function liveUserLine(transcript: Transcript): {
  said: string;
  interim: string;
} {
  const turn = transcript[transcript.length - 1];
  if (!turn || turn.role !== "user" || turn.closed) {
    return { said: "", interim: "" };
  }
  const { spoken, pending } = turnCaption(turn);
  return { said: spoken, interim: pending };
}
