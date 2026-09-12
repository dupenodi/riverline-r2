/**
 * Turn-based transcript model for the live caption panel.
 *
 * RTVI delivers the bot's reply as a stream of `bot-output` events and the
 * user's speech as interim + final transcripts. Rendering each event as its own
 * line is what makes the panel look shredded, so everything here folds back
 * into one entry per conversational turn.
 *
 * The `bot-output` lifecycle (RTVI 2.0.0) is two-phase, and each sentence
 * arrives twice:
 *
 *   spoken_status: "new"          → the sentence text, queued but not yet voiced
 *   spoken_status: "in-progress"  → how much of it has been voiced so far
 *   spoken_status: "completed"    → the sentence finished playing
 *
 * Only the first carries text; the rest advance a spoken cursor. Treating the
 * later events as new text is what duplicates every sentence. `segment_id`
 * differs between the two phases, so — as in @pipecat-ai/client-react — the
 * cursor matches by id when it can and otherwise walks the segments in order.
 * A turn is finalized by bot-stopped-speaking, never by a segment.
 */

export type TurnRole = "user" | "agent";

export type Segment = {
  /** RTVI segment_id, or a synthetic id when the server omits one. */
  id: string;
  text: string;
};

export type Turn = {
  id: string;
  role: TurnRole;
  /** Text of the turn, in the order the server produced it. */
  segments: Segment[];
  /** Segments fully voiced so far. */
  spokenParts: number;
  /** Characters voiced within `segments[spokenParts]`. */
  spokenChars: number;
  /** Words still being recognised — shown dimmed, replaced on the next final. */
  draft: string;
  /** No more text will be added to this turn. */
  closed: boolean;
  /** The user talked over this turn before it finished. */
  interrupted: boolean;
};

export type Transcript = Turn[];

/** Keep memory (and the DOM) bounded on long calls. */
const MAX_TURNS = 60;

let seq = 0;
function nextId(role: TurnRole): string {
  seq += 1;
  return `${role}-${seq}`;
}

/** How much of `turn` has actually reached the air, as plain text. */
export function spokenText(turn: Turn): string {
  const whole = turn.segments.slice(0, turn.spokenParts).map((s) => s.text);
  const partial = turn.segments[turn.spokenParts]?.text.slice(0, turn.spokenChars);
  if (partial) whole.push(partial);
  return whole.join(" ").replace(/\s+/g, " ").trim();
}

/**
 * The turn as plain text.
 *
 * A turn cut short by the user only ever reached the air as far as the spoken
 * cursor, so the recap quotes that much rather than text Kubera never said.
 */
export function turnText(turn: Turn): string {
  if (turn.interrupted) return spokenText(turn);
  return turn.segments
    .map((s) => s.text)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

export function isEmpty(turn: Turn): boolean {
  return turnText(turn) === "" && turn.draft.trim() === "";
}

function newTurn(role: TurnRole): Turn {
  return {
    id: nextId(role),
    role,
    segments: [],
    spokenParts: 0,
    spokenChars: 0,
    draft: "",
    closed: false,
    interrupted: false,
  };
}

function openTurn(transcript: Transcript, role: TurnRole): Transcript {
  const last = transcript[transcript.length - 1];
  if (last && last.role === role && !last.closed) return transcript;
  return [...closeOpenTurns(transcript), newTurn(role)].slice(-MAX_TURNS);
}

function closeOpenTurns(transcript: Transcript): Transcript {
  return transcript
    .map((turn) => (turn.closed ? turn : commit(turn)))
    // Drop turns that never produced any text (a cough that tripped VAD, an LLM
    // response cut off before its first sentence) so the panel does not fill
    // with empty speaker labels.
    .filter((turn) => !isEmpty(turn));
}

/**
 * Close a turn, keeping whatever it had.
 *
 * A turn can end while its last words are still only a draft — the user stops
 * talking and the assistant starts before a final transcript lands. Promoting
 * the draft keeps those words instead of dropping them.
 */
function commit(turn: Turn): Turn {
  const draft = turn.draft.trim();
  if (!draft) return { ...turn, closed: true, draft: "" };
  return said({ ...turn, draft: "" }, mergeFinal(turnText(turn), draft));
}

function updateLast(
  transcript: Transcript,
  role: TurnRole,
  fn: (turn: Turn) => Turn,
): Transcript {
  const opened = openTurn(transcript, role);
  const next = [...opened];
  next[next.length - 1] = fn(next[next.length - 1]);
  return next;
}

/**
 * Fold a new final transcript into what the turn already has.
 *
 * Providers differ: some send each utterance once, some re-send the whole turn
 * so far. Comparing prefixes covers both without assuming either.
 */
function mergeFinal(existing: string, incoming: string): string {
  const a = existing.trim();
  const b = incoming.trim();
  if (!a) return b;
  if (!b) return a;
  if (b.startsWith(a)) return b;
  if (a.endsWith(b)) return a;
  return `${a} ${b}`;
}

/** Replace a turn's text with one settled utterance. Nothing is pending. */
function said(turn: Turn, text: string): Turn {
  return {
    ...turn,
    closed: true,
    segments: [{ id: `${turn.id}-said`, text }],
    spokenParts: 1,
    spokenChars: 0,
  };
}

/** The user started (or resumed) speaking. */
export function userSpeaking(transcript: Transcript): Transcript {
  return openTurn(transcript, "user");
}

/** An interim recognition result — shown, but never committed. */
export function userInterim(transcript: Transcript, text: string): Transcript {
  return updateLast(transcript, "user", (turn) => ({ ...turn, draft: text }));
}

/** A final recognition result for part or all of the user's turn. */
export function userFinal(transcript: Transcript, text: string): Transcript {
  if (!text.trim()) {
    return updateLast(transcript, "user", (turn) => ({ ...turn, draft: "" }));
  }
  return updateLast(transcript, "user", (turn) => ({
    ...said(turn, mergeFinal(turnText(turn), text)),
    // The user may keep talking; only the assistant's turn closes this one.
    closed: false,
    draft: "",
  }));
}

/** The assistant began composing a reply; the user's turn is over. */
export function agentTurnStarted(transcript: Transcript): Transcript {
  return openTurn(transcript, "agent");
}

/**
 * A `bot-output` event carrying text (`spoken_status: "new"`, or text that will
 * never be spoken). Appends a segment; re-sends of the same id just update it.
 */
export function agentText(
  transcript: Transcript,
  segment: Segment,
  { willBeSpoken = true }: { willBeSpoken?: boolean } = {},
): Transcript {
  if (!segment.text.trim()) return transcript;
  return updateLast(transcript, "agent", (turn) => {
    const index = turn.segments.findIndex((s) => s.id === segment.id);
    const segments =
      index === -1
        ? [...turn.segments, segment]
        : turn.segments.map((s, i) => (i === index ? segment : s));
    const next = { ...turn, segments };
    // Text that bypasses TTS is on screen the moment it arrives; there will be
    // no progress event to move the cursor past it.
    return willBeSpoken ? next : { ...next, spokenParts: segments.length, spokenChars: 0 };
  });
}

/**
 * A `bot-output` progress event. Carries no new text — it reports how far the
 * voice has got, so the caption can stay level with the audio.
 */
export function agentProgress(
  transcript: Transcript,
  { segmentId, accumulated }: { segmentId?: string; accumulated: string },
): Transcript {
  const last = transcript[transcript.length - 1];
  if (!last || last.role !== "agent" || last.closed) return transcript;
  if (last.segments.length === 0) return transcript;

  // Match the segment the server names; otherwise take the next unspoken one.
  let index = segmentId
    ? last.segments.findIndex((s) => s.id === segmentId)
    : -1;
  if (index === -1) index = Math.min(last.spokenParts, last.segments.length - 1);

  const text = last.segments[index].text;
  const chars = Math.min(accumulated.length, text.length);
  const advanced =
    chars >= text.length
      ? { spokenParts: index + 1, spokenChars: 0 }
      : { spokenParts: index, spokenChars: chars };

  // Progress never goes backwards, even if events arrive out of order.
  if (
    advanced.spokenParts < last.spokenParts ||
    (advanced.spokenParts === last.spokenParts &&
      advanced.spokenChars < last.spokenChars)
  ) {
    return transcript;
  }

  const next = [...transcript];
  next[next.length - 1] = { ...last, ...advanced };
  return next;
}

/** The assistant finished speaking its turn. */
export function agentTurnEnded(transcript: Transcript): Transcript {
  return closeOpenTurns(transcript);
}

/**
 * The user started talking while the assistant still had the floor.
 *
 * Only a turn with text left to say was actually cut off; someone clearing
 * their throat over the last syllable is not an interruption, so the turn
 * closes normally and the panel shows no cut marker.
 */
export function interrupted(transcript: Transcript): Transcript {
  const last = transcript[transcript.length - 1];
  if (!last || last.role !== "agent" || last.closed) return transcript;
  const cutShort =
    last.spokenParts < last.segments.length || last.spokenChars > 0;
  const next = [...transcript];
  next[next.length - 1] = { ...last, interrupted: cutShort, closed: true };
  return next.filter((t) => !isEmpty(t));
}
