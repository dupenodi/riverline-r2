/**
 * The transcript model, against the RTVI contract it is built on.
 *
 * These exist because the previous version guessed: it prefix-matched
 * consecutive finals to choose between replacing and appending, and it treated
 * `accumulated_text` as a character offset into a different string. Both put
 * words on screen nobody said. Every case below is one of those guesses,
 * written down as the behaviour it should have had.
 *
 * Run with `npm test` (Node's built-in runner; no framework).
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  agentSegment,
  agentTurnEnded,
  agentTurnStarted,
  interrupted,
  lastAgentLine,
  liveUserLine,
  turnCaption,
  turnText,
  userFinal,
  userInterim,
  userSpeaking,
  type Transcript,
} from "./transcript.ts";

const EMPTY: Transcript = [];

describe("user transcripts", () => {
  it("shows an interim as soon as it arrives", () => {
    let t = userSpeaking(EMPTY);
    t = userInterim(t, "I have thirty");

    assert.equal(liveUserLine(t).interim, "I have thirty");
    assert.equal(liveUserLine(t).said, "");
  });

  it("replaces the previous interim instead of appending it", () => {
    // The bug this file exists for. Sarvam re-sends the whole utterance as it
    // revises, so appending produced "I have 30,000 I have 45,000".
    let t = userSpeaking(EMPTY);
    t = userInterim(t, "I have thirty");
    t = userInterim(t, "I have thirty thousand");
    t = userInterim(t, "I have forty five thousand");

    assert.equal(turnText(t[0]), "I have forty five thousand");
  });

  it("keeps a revised final rather than gluing it to the interim it replaced", () => {
    let t = userSpeaking(EMPTY);
    t = userInterim(t, "I currently have about 30,000");
    t = userFinal(t, "I currently have about 45,000, not 30,000.");

    assert.equal(turnText(t[0]), "I currently have about 45,000, not 30,000.");
  });

  it("accumulates several finals in one turn", () => {
    // A long answer can be segmented server-side into more than one utterance.
    let t = userSpeaking(EMPTY);
    t = userFinal(t, "I pay rent on the twentieth.");
    t = userFinal(t, "It is twenty four thousand.");

    assert.equal(
      turnText(t[0]),
      "I pay rent on the twentieth. It is twenty four thousand.",
    );
  });

  it("clears the interim once its final lands", () => {
    let t = userSpeaking(EMPTY);
    t = userInterim(t, "rent is twenty");
    t = userFinal(t, "Rent is twenty four thousand.");

    assert.equal(liveUserLine(t).interim, "");
    assert.equal(liveUserLine(t).said, "Rent is twenty four thousand.");
  });

  it("keeps words that were only ever an interim when the turn ends", () => {
    // They stopped talking and Kubera started before the final landed. Those
    // words were recognised; dropping them loses what the user actually said.
    let t = userSpeaking(EMPTY);
    t = userInterim(t, "and the car loan");
    t = agentTurnStarted(t);

    assert.equal(turnText(t[0]), "and the car loan");
  });

  it("goes quiet once Kubera has the floor", () => {
    let t = userSpeaking(EMPTY);
    t = userFinal(t, "Thirty thousand.");
    t = agentTurnStarted(t);

    assert.deepEqual(liveUserLine(t), { said: "", interim: "" });
  });

  it("ignores an empty final without discarding the turn", () => {
    let t = userSpeaking(EMPTY);
    t = userFinal(t, "Rent is due on the fifth.");
    t = userFinal(t, "   ");

    assert.equal(turnText(t[0]), "Rent is due on the fifth.");
  });

  it("drops a turn that never produced a word", () => {
    let t = userSpeaking(EMPTY); // a cough that tripped VAD
    t = agentTurnStarted(t);

    assert.equal(t.filter((turn) => turn.role === "user").length, 0);
  });
});

describe("assistant output", () => {
  const seg = (id: string, text: string, spoken: string) => ({ id, text, spoken });

  it("shows a sentence before the voice has reached it, dimmed", () => {
    // Sarvam's TTS reports no word timestamps, so a segment sits at spoken=""
    // for its whole duration. Withholding it leaves the screen blank for the
    // entire turn and then snaps it in.
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "What is your rent?", ""));

    assert.deepEqual(lastAgentLine(t), {
      spoken: "",
      pending: "What is your rent?",
    });
  });

  it("moves text from pending to spoken as the server reports it", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "What is your rent?", ""));
    t = agentSegment(t, seg("1", "What is your rent?", "What is your"));

    assert.deepEqual(lastAgentLine(t), {
      spoken: "What is your",
      pending: "rent?",
    });
  });

  it("uses accumulated_text verbatim, never a character count", () => {
    // The old code did `text.slice(0, accumulated.length)`, which silently
    // diverges the moment the server applies any transform to either string.
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "It is twenty four thousand.", "It is 24,000"));

    assert.equal(lastAgentLine(t).spoken, "It is 24,000");
  });

  it("keys segments by id, so a re-sent segment updates in place", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, { id: "1", text: "One.", spoken: "", create: true });
    t = agentSegment(t, { id: "2", text: "Two.", spoken: "", create: true });
    // Same id: progress updates in place even when create is false.
    t = agentSegment(t, {
      id: "1",
      text: "One.",
      spoken: "One.",
      create: false,
    });

    assert.equal(t[0].segments.length, 2);
    assert.deepEqual(lastAgentLine(t), { spoken: "One.", pending: "Two." });
  });

  it("stops the spoken run at the first unfinished segment", () => {
    // Segment two being done does not mean segment one was said.
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "One.", ""));
    t = agentSegment(t, seg("2", "Two.", "Two."));

    assert.equal(lastAgentLine(t).spoken, "");
    assert.equal(lastAgentLine(t).pending, "One. Two.");
  });

  it("treats a closed turn as fully said", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "Got it.", ""));
    t = agentTurnEnded(t);

    assert.deepEqual(lastAgentLine(t), { spoken: "Got it.", pending: "" });
  });

  it("keeps only what was voiced when the user talks over it", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "Your rent is due", "Your rent is due"));
    t = agentSegment(t, seg("2", "on the twentieth.", ""));
    t = interrupted(t);

    assert.equal(t[0].interrupted, true);
    assert.equal(lastAgentLine(t).spoken, "Your rent is due");
  });

  it("does not call a turn interrupted when the voice had finished", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "Got it.", "Got it."));
    t = interrupted(t);

    assert.equal(t[0].interrupted, false);
  });

  it("reads back past an empty turn to the last thing actually said", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "What is your rent?", "What is your rent?"));
    t = agentTurnEnded(t);
    t = userSpeaking(t);
    t = userFinal(t, "Twenty four thousand.");

    assert.equal(lastAgentLine(t).spoken, "What is your rent?");
  });

  it("does not double a sentence when completed uses a different segment_id", () => {
    // Live RTVI (captured in docs/build-log.md): one sentence, two messages,
    // two ids. Progress must advance the "new" segment, not append.
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, {
      id: "1005",
      text: "Hi there!",
      spoken: "",
      create: true,
    });
    t = agentSegment(t, {
      id: "1008",
      text: "Hi there!",
      spoken: "Hi there!",
      create: false,
    });

    assert.equal(t[0].segments.length, 1);
    assert.deepEqual(turnCaption(t[0]), {
      spoken: "Hi there!",
      pending: "",
    });
  });

  it("progress without a matching segment is a no-op, not a new line", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, {
      id: "1008",
      text: "Hi there!",
      spoken: "Hi there!",
      create: false,
    });

    assert.equal(t[0]?.segments.length ?? 0, 0);
  });

  it("still allows the bot to say the same sentence twice on two news", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, {
      id: "1",
      text: "Sorry.",
      spoken: "",
      create: true,
    });
    t = agentSegment(t, {
      id: "2",
      text: "Sorry.",
      spoken: "",
      create: true,
    });

    assert.equal(t[0].segments.length, 2);
    assert.equal(turnText(t[0]), "Sorry. Sorry.");
  });
});

describe("turnCaption", () => {
  const seg = (id: string, text: string, spoken: string) => ({ id, text, spoken });

  it("splits an open agent turn at the voice", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "What is your rent?", "What is your"));

    assert.deepEqual(turnCaption(t[0]), {
      spoken: "What is your",
      pending: "rent?",
    });
  });

  it("splits an open user turn into finals and interim", () => {
    let t = userSpeaking(EMPTY);
    t = userFinal(t, "Rent is");
    t = userInterim(t, "twenty four");

    assert.deepEqual(turnCaption(t[0]), {
      spoken: "Rent is",
      pending: "twenty four",
    });
  });

  it("is what lastAgentLine and liveUserLine read from", () => {
    let t = agentTurnStarted(EMPTY);
    t = agentSegment(t, seg("1", "Got it.", "Got it."));
    t = agentTurnEnded(t);
    t = userSpeaking(t);
    t = userInterim(t, "Okay");

    assert.deepEqual(lastAgentLine(t), turnCaption(t[0]));
    assert.deepEqual(liveUserLine(t), {
      said: turnCaption(t[1]).spoken,
      interim: turnCaption(t[1]).pending,
    });
  });
});
