/**
 * The conversation, as the RTVI protocol actually reports it.
 *
 * Written against the message contract in Pipecat's `RTVIObserver`, not against
 * assumptions about it. The previous version guessed at both halves — it
 * prefix-matched consecutive final transcripts to decide whether to replace or
 * append, and it treated `accumulated_text` as a character offset into a
 * different string. Both are wrong often enough to put words on screen that
 * nobody said.
 *
 * --- What the bot side actually sends -------------------------------------
 *
 * `bot-output`, one message per aggregated segment (a sentence, by default):
 *
 *   spoken_status "new"          text = the whole segment, nothing voiced yet
 *                                (word-timestamp services, before synthesis)
 *   spoken_status "in-progress"  spoken_progress.accumulated_text = voiced so far
 *   spoken_status "completed"    the segment has been fully voiced
 *   spoken_status absent         will_be_spoken false: text that is never voiced
 *
 * Only "new" (and never-spoken text) may create a segment. Progress messages
 * often carry a *different* `segment_id` than the matching "new" — observed on
 * the wire — so they advance spoken by id when possible, otherwise by matching
 * unfinished text. Treating completed as an upsert-by-id doubles every sentence.
 *
 * `spoken_progress.accumulated_text` and `remaining_text` are *this segment's*
 * text split at the voice — `accumulated + remaining` is the segment. So the
 * spoken part is a string the server hands us, never something to compute.
 *
 * Sarvam's TTS reports no word timestamps, so here a segment goes straight from
 * "new" to "completed" when the sentence finishes. The caption therefore shows
 * whole sentences as the model produces them and marks them voiced a sentence
 * at a time. That is a property of the provider, not a thing to work around.
 *
 * --- What the user side actually sends ------------------------------------
 *
 * `user-transcription` is a straight pass-through of the STT service's frames:
 * `{ text, final }` and nothing else. There is no accumulation contract at the
 * RTVI layer, so the semantics are the provider's:
 *
 *   final: false   the current utterance as recognised so far. Each one
 *                  supersedes the last — replace, never append.
 *   final: true    that utterance is settled. A long turn can contain several,
 *                  so settled utterances accumulate.
 *
 * That is the realtime contract Sarvam, Deepgram and AssemblyAI all implement.
 * It is written down here as one model rather than re-inferred per message,
 * which is what makes it checkable against live RTVI `user-transcription`
 * messages (interim vs final) during a real call rather than assuming.
 * logs every interim and final verbatim, so one call confirms or refutes it.
 */

export type TurnRole = "user" | "agent";

/** One aggregated chunk of speech, tracked by the id the server gave it. */
export type Segment = {
  id: string;
  /** The whole segment. */
  text: string;
  /** How much of it the voice has said, as the server reports it. */
  spoken: string;
};

export type Turn = {
  id: string;
  role: TurnRole;
  /** Assistant: one entry per `segment_id`. User: one entry per final. */
  segments: Segment[];
  /** User only: the current interim, replaced wholesale until a final lands. */
  interim: string;
  closed: boolean;
  /** The user talked over this turn before the voice reached the end of it. */
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

/** Everything in the turn, settled and in flight. */
export function turnText(turn: Turn): string {
  return join([...turn.segments.map((s) => s.text), turn.interim]);
}

/**
 * How much of the turn has reached the air.
 *
 * For the assistant this is the spoken part of each segment in order, stopping
 * at the first the voice has not finished — text after a gap has not been said,
 * however much of it exists. Everything the user said, they said.
 */
export function spokenText(turn: Turn): string {
  if (turn.role === "user") return turnText(turn);
  const parts: string[] = [];
  for (const segment of turn.segments) {
    parts.push(segment.spoken);
    if (segment.spoken.trim() !== segment.text.trim()) break;
  }
  return join(parts);
}

/** Text the model has produced that the voice has not reached. */
export function pendingText(turn: Turn): string {
  if (turn.role === "user") return "";
  const parts: string[] = [];
  let reached = false;
  for (const segment of turn.segments) {
    const done = segment.spoken.trim() === segment.text.trim();
    if (reached || !done) {
      // The tail of the segment the voice is inside, then all that follows it.
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

// --- turn boundaries ---------------------------------------------------------

function closeOpen(transcript: Transcript): Transcript {
  return (
    transcript
      .map((turn) => (turn.closed ? turn : commit(turn)))
      // A cough that tripped VAD, or a reply cut off before its first word,
      // would otherwise leave an empty speaker in the recap.
      .filter((turn) => !isEmpty(turn))
  );
}

/**
 * Close a turn, keeping what it had.
 *
 * A user turn can end with an interim outstanding — they stop talking and the
 * assistant starts before the final lands. Those words were recognised and are
 * the best record there is, so they are promoted rather than dropped.
 */
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

// --- user --------------------------------------------------------------------

/** The user started, or resumed, speaking. */
export function userSpeaking(transcript: Transcript): Transcript {
  return openTurn(transcript, "user");
}

/**
 * An interim result: the utterance in flight, as currently recognised.
 *
 * It replaces the previous interim outright. Appending it — or prefix-matching
 * to decide whether to append — is what put "I have 30,000 I have 45,000" on
 * screen when the recogniser revised an earlier word.
 */
export function userInterim(transcript: Transcript, text: string): Transcript {
  return updateOpen(transcript, "user", (turn) => ({ ...turn, interim: text }));
}

/** A final result: one settled utterance. A turn may contain several. */
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

// --- assistant ---------------------------------------------------------------

/** The assistant began composing a reply; the user's turn is over. */
export function agentTurnStarted(transcript: Transcript): Transcript {
  return openTurn(transcript, "agent");
}

/**
 * One `bot-output` message, applied to the open agent turn.
 *
 * Every field comes from the server. `spoken` is `accumulated_text` verbatim;
 * nothing here measures, slices by index, or compares prefixes to work out how
 * far the voice has got.
 *
 * `create` is the RTVI phase gate:
 *   true   spoken_status "new" (or never-spoken text) — append if the id is new
 *   false  in-progress / completed — advance spoken only, never append
 *
 * Live traffic gives the progress message a *different* segment_id from "new".
 * Progress therefore falls back to the unfinished segment with the same text.
 * Appending on completed is what doubled every sentence on screen.
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
      // Keep the id from "new"; only the spoken cursor moves.
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

/** The assistant finished speaking its turn. */
export function agentTurnEnded(transcript: Transcript): Transcript {
  return closeOpen(transcript);
}

/**
 * The user started talking while the assistant still had the floor.
 *
 * Only a turn with words left to say was actually cut off; someone clearing
 * their throat over the last syllable is not an interruption.
 */
export function interrupted(transcript: Transcript): Transcript {
  const last = transcript[transcript.length - 1];
  if (!last || last.role !== "agent" || last.closed) return transcript;
  const cutShort = pendingText(last) !== "";
  const next = [...transcript];
  next[next.length - 1] = { ...last, interrupted: cutShort, closed: true };
  return next.filter((turn) => !isEmpty(turn));
}

// --- what the call screen reads ----------------------------------------------

/**
 * One turn, split for captions: what has landed vs what is still in flight.
 *
 * Assistant: `spoken` has reached the air; `pending` is produced but not yet
 * voiced. A finished turn (unless cut off) is all spoken.
 * User: `spoken` is the settled finals; `pending` is the current interim.
 */
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
  // A finished turn was all said, bar the part an interruption cut off.
  if (turn.closed && !turn.interrupted) {
    return { spoken: turnText(turn), pending: "" };
  }
  return { spoken: spokenText(turn), pending: pendingText(turn) };
}

/**
 * The last thing Kubera said, split at the voice.
 *
 * The caller shows both and dims the tail, so a sentence is readable as soon
 * as it exists and you can still see where the voice is in it.
 */
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

/**
 * What the user is saying right now: settled utterances, then the one in
 * flight. Only an open user turn counts, so the caption goes quiet as soon as
 * Kubera takes the floor.
 */
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
