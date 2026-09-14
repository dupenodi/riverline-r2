import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { callMood, moodLabel, moodMascot, moodPulses } from "./call-mood.ts";

describe("callMood", () => {
  it("uses priority ending → muted → speaking → working → user → waiting/listening", () => {
    assert.equal(callMood({ ending: true, agentSpeaking: true }), "ending");
    assert.equal(callMood({ muted: true, hasLines: true }), "muted");
    assert.equal(callMood({ muted: true, agentSpeaking: true }), "speaking");
    assert.equal(callMood({ agentSpeaking: true, thinking: true }), "speaking");
    assert.equal(callMood({ thinking: true, userSpeaking: true }), "working");
    assert.equal(callMood({ userSpeaking: true, hasLines: true }), "user");
    assert.equal(callMood({}), "waiting");
    assert.equal(callMood({ hasLines: true }), "listening");
  });

  it("keeps short copy and mascot mapping", () => {
    assert.equal(moodLabel("working"), "One sec…");
    assert.equal(moodMascot("working"), "/kubera-thinking.png");
    assert.equal(moodMascot("listening"), "/kubera-logo.png");
    assert.equal(moodPulses("working"), true);
    assert.equal(moodPulses("speaking"), false);
  });
});
