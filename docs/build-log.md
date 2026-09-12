# Build log

Raw material for the decision journal and for the live session. Organised by
pass: what broke, what I decided, what I measured.

> **This is not the decision journal.** The assignment requires the journal to
> be written entirely by me, and says AI-generated journal content disqualifies
> the submission. This file is engineering notes produced during the build —
> source material to write from, not text to copy.

---

## Pass 1 — scaffold

Monorepo: Next.js web + Python Pipecat/Daily agent, `docker compose up --build`.
FastAPI session API creates a Daily room, mints tokens, starts a bot, returns
client credentials.

---

## Pass 2 — voice experience

### Bug: the transcript ate words and duplicated sentences

**Symptom.** Captions broke into stubby lines, sentences disappeared, and some
lines rendered twice ("Hi there! Hi there!").

**How I found it.** Reading the code did not reveal it. I captured raw RTVI
traffic from a live call in a headless browser. Every sentence arrives on
`bot-output` **twice**:

```
segment_id 1005  spoken_status "new"        text "Hi there!"   <- the text
segment_id 1008  spoken_status "completed"  text "Hi there!"   <- speech progress
```

The `segment_id` differs between the two phases, so deduping on it is
impossible. On top of that `onBotTtsText` wrote the same text a third time, and
the old `upsertCaption` replace-rule made each new sentence overwrite the
previous one. Two visible symptoms, one root cause.

**Decision.** Rewrote captions as a turn-based model (`lib/transcript.ts`),
mirroring how `@pipecat-ai/client-react` handles the same protocol: only
`spoken_status: "new"` adds text; `in-progress`/`completed` advance a spoken
cursor; a turn closes on `bot-stopped-speaking`, never on a segment.

**Option I rejected.** Dedupe on text content — 5 lines instead of 275. It
breaks the moment the bot legitimately repeats itself ("Sorry — sorry, go
ahead"), and it throws away the progress data that makes the karaoke dimming
work.

**Lesson worth repeating in an interview.** The bug was only visible in the
wire traffic. The two phases look identical in the code apart from one field.

### Bug: the greeting could fire twice, or never

Three separate faults in one handler.

| Fault | Fix |
|---|---|
| `on_client_connected` aliases `on_participant_joined` — fires for *every* participant, so a rejoin re-prompted the LLM mid-conversation | `on_first_participant_joined` + explicit once-guard |
| If the user wins the race into the room, Daily reports no join event and the greeting never fires | `on_joined` checks `participants()` and greets from there |
| LLM-generated greeting with no fallback — a slow provider means silence | 8s watchdog speaks a fixed line via `TTSSpeakFrame(append_to_context=True)` |

**Why 8s:** measured cold start (connect + first completion) was ~4.2s. 6s was
racing it.

**Trade-off accepted.** A hardcoded fallback is less natural than the LLM's, but
silence on connect is the worst possible first impression. The fallback goes
into the LLM context so the conversation stays coherent afterwards.

**Also:** `POST /sessions` used to `sleep(0.3)` and claim `ready`. It now waits
on a real join event, so `ready` means the bot is actually in the room. Costs
~5s at session create, spent on the connecting screen where the user already
expects to wait.

### Session lifecycle

- Any participant leaving killed the pipeline → now gated on the room being empty.
- No `idle_timeout_secs` → a dead browser tab left a bot billing in an empty
  room. Now 120s.
- No idle handling → `user_idle_timeout=30`, one check-in, then a goodbye and a
  graceful `EndWorkerFrame`.
- Closing the tab never released the session → `pagehide` + `DELETE` with
  `keepalive: true` (`sendBeacon` cannot do DELETE).

**Why 30s and not 20s:** money conversations have long pauses. Being nagged
while doing mental arithmetic is worse than a little silence.

### Things I decided NOT to do in pass 2

- **Turn-taking tuning.** Pipecat 1.10 already defaults to
  `LocalSmartTurnAnalyzerV3` and the bundled ONNX model loads fine. Touching VAD
  `stop_secs` would have been tuning without evidence — the cut-offs were the
  transcript bug. **Pass 3 proved me wrong; see below.**
- **STT hallucination.** Sarvam produces fluent sentences from non-speech audio
  (a tone became a Telugu movie review). Silero lets tonal noise through. Fixing
  it means tuning VAD or STT thresholds, which I would rather do against real
  recordings than guess at. Flagged, not fixed.
- **Merging consecutive same-speaker turns.** Looks odd, but only happens when a
  response is barged over before its first sentence. Merging would be a display
  fiction.

### A hypothesis I tested and disproved

I assumed a money agent would mispronounce Indian currency amounts. Tested a
Sarvam TTS→STT round trip: ₹40,000 and ₹1,50,000 both came back clean. No work
needed. Worth noting because it is the kind of assumption that quietly becomes
a day of unnecessary work.

---

## Pass 3 — latency

Scope: the one quality problem worth fixing before adding tools.

### The instrument came before the fix

Nothing measured latency, so the first change was an instrument. Pipecat ships
`UserBotLatencyObserver`, which measures user-stopped-speaking →
bot-started-speaking and, with `enable_metrics`, attributes the interval part by
part. Wired into the worker's `observers` plus a p50/p95 summary per call. No
custom code.

### Metric: time-to-first-content-token

Realistic mid-call turn (real system prompt, 4 turns of history), 6 samples per
model, through the project's own API keys.

| model | p50 | min | max | spread |
|---|---|---|---|---|
| **sarvam-105b-conversations** | **0.366s** | 0.304s | 0.389s | **1.3×** |
| mistralai/ministral-8b-2512 | 0.520s | 0.466s | 0.578s | 1.2× |
| meta-llama/llama-3.1-8b (Groq) | 0.656s | 0.174s | 0.906s | 5.2× |
| openai/gpt-4.1-nano | 0.818s | 0.797s | 1.331s | 1.7× |
| anthropic/claude-haiku-4.5 | 1.235s | 0.880s | 3.142s | 3.6× |
| google/gemini-2.5-flash-lite | 1.652s | 1.592s | 3.334s | 2.1× |
| **openai/gpt-4o-mini** *(was)* | **1.816s** | 0.715s | 2.926s | 4.1× |

**Decision: Sarvam `sarvam-105b-conversations`**, OpenRouter kept switchable via
`LLM_PROVIDER`.

Reasoning beyond the p50:

- **Spread matters more than median.** The old setup ranged 0.7s–2.9s on
  *identical* requests because OpenRouter re-routes per request and you inherit
  whatever that provider's queue looks like. A predictable 0.37s is a better
  conversation than an average that occasionally stalls for 3s.
- **One vendor already in the pipeline** (STT and TTS are Sarvam) — no new key,
  no new failure mode.
- **It is the conversation-tuned variant** — the one model Pipecat's Sarvam
  service excludes from its reasoning set, which is why its first token is
  early. Reasoning models are the wrong shape for voice: you pay thinking tokens
  before the first spoken word.

Gated on three checks before committing, because speed is worthless without
them: reply quality (short, one question per turn), code-switching (handled
"Mera rent badh gaya hai by four thousand"), and **tool calling** — "note my rent
is now twenty four thousand rupees" produced
`log_expense(category="rent", amount_inr=24000)` with `finish_reason: tool_calls`.

### Metric: in-pipeline A/B

| | LLM inference (greeting) | LLM inference (user turn) |
|---|---|---|
| Sarvam | **0.351s** | **0.329s** |
| OpenRouter (gpt-4.1-nano) | 1.586s | 0.853s |
| OpenRouter (gpt-4o-mini, before) | ~1.7s | 1.704s |

Clean turns: **1.33–1.46s** end to end, from ~2.4s.

Also set `max_tokens=200` — a backstop against a monologue, not a shaping tool.
In text you skim a long answer; in voice you sit through it.

### What the instrument caught that I had wrong

In pass 2 I concluded turn-taking was not worth touching. The breakdown:

```
0.200s  endpointing wait     [config: VAD stop_secs]
0.154s  transcription        [SarvamRealtimeSTT]
2.848s  turn detection       [config: user turn strategies]   <- now the biggest
0.329s  LLM inference        [SarvamLLM]
0.172s  sentence aggregation [config: text_aggregation_mode]
0.567s  speech synthesis     [SarvamTTS]
4.270s  TOTAL
```

With the LLM fixed, turn detection became the dominant cost. 2.848s sits just
under smart-turn's 3s `stop_secs` ceiling, meaning the model never became
confident and fell back to the silence timeout.

**Caveat I am keeping visible rather than burying:** this was Chrome's fake-audio
device, which is noise, not speech. Smart-turn holding on ambiguous input is
expected. Real recorded speech is needed before tuning it.

**General lesson:** the bottleneck moved as soon as the first one was fixed, and
only the instrument showed where it went.

### Debugging note worth remembering

Latency logs did not appear on the first live test. Cause: a Docker container
from an earlier `docker compose up` was still listening on 7860 over IPv6, so
the browser was hitting a stale build. Cost a confusing test round.

---

## Pass 4 — financial core

### Decision: the LLM does no arithmetic

The model extracts facts from conversation and records them through tools; a
deterministic planner does every calculation.

**Why.** The assignment requires calculations to be "visible and testable" and
forbids inventing numbers. If the model has no arithmetic to do, it has none to
invent. It also means the maths is unit-testable in milliseconds rather than
through 40-second phone calls.

**Cost I accepted.** Rigidity. A user who says something the fact model did not
anticipate gets flattened into the nearest field, and the planner can only
produce plan shapes I coded. A more LLM-driven design would demo better on
unusual inputs. I took the deterministic one because correctness is an explicit
evaluation criterion and because it is defensible under questioning in a way
that "the model works it out" is not.

### Decision: day-by-day timeline, not monthly totals

A month does not go wrong because the totals are wrong. It goes wrong because of
**order**: a salary on the 28th against rent due on the 3rd is a crisis; the same
two numbers reversed are fine.

Two tests pin this down with *identical* monthly totals and opposite answers:
salary on the 10th + rent on the 20th nets +₹35,000 and is still a shortfall;
move the salary to the 18th and it is fine. Netting totals calls both
comfortable.

Consequence: the window is **30 days from today, not a calendar month**, so it
usually straddles two months and a monthly bill can legitimately occur twice.

### Decision: uncertainty resolves against the user, never toward the middle

Ranges are not vagueness to be averaged. Income plans at the **low** end,
outgoings at the **high** end; income is assumed to arrive **late** in its range
and bills to fall due **early**. Averaging produces a plan that is right on paper
and breaks in the third week.

### Decision: restatement is recorded, not blocked

The assignment wants both "ask for clarification when information conflicts" and
"allow the user to correct previous information". These are indistinguishable
from the data alone — only the agent can tell which the user meant.

So: the newer value always wins (a correction is far more common than a
contradiction), the change is recorded as a conflict, and it stays visible for
the agent to confirm and the card to show. A 5% tolerance stops a rounding
restatement from generating a pointless question.

### Bug I introduced and caught: zero was rejected

Validation required `amount >= 1`. "I have nothing until Friday" is the exact
situation this product is for — a real answer, not bad input. Negative is still
rejected: money owed is a debt fact, not a negative balance.

### Bug the smoke test caught that the unit tests did not

On a realistic scenario the planner told the user to cancel eating out **and**
streaming **and** drop their credit card to the minimum — when the card minimum
alone was enough.

**Cause.** The shortfall loop is greedy: it cuts the smallest available thing
first, then finds a much bigger lever, and never reconsiders the earlier cut.

**Fix.** A restoration pass. Every change is offered back, most recent first, and
kept only if the month stops balancing without it. What survives is a minimal
set — every remaining sacrifice is one the plan depends on.

**Test added.** A property test: putting *any* surviving cut back must break the
plan. So minimality holds by construction, not by inspection.

**Why this one matters.** The unit tests all passed. It took printing a realistic
scenario and reading the output to see that the plan was asking someone to give
up dinner for nothing. Correct-by-tests is not the same as sensible.

### Correction to my own earlier framing

I had described the shortfall as the month's net gap. It is the **deepest dip**.
In the unsolvable test that is ₹29,000 on the 18th, not the ₹19,000 you get by
netting the window. The deeper number is the one that matters — it is the moment
the payment actually bounces.

### Constraint enforced in code, not in the prompt

There is no "borrow" action in the planner's vocabulary. The assignment forbids
recommending another loan, and leaving it out of the type means the planner
cannot emit one even if a later prompt change invites it. A test asserts no
action text contains loan/borrow/credit line/advance.

### Docker footgun fixed

The agent image used an explicit `COPY server.py bot.py ...` list. Every new
module would have been silently missing from the image and failed only at
runtime under compose — i.e. it would break for a reviewer and nowhere else.
Now copies the package.

---

## Open items / known limitations

- STT hallucinates fluent text from non-speech audio (Silero lets tonal noise
  through). Flagged, not fixed.
- Turn detection measured at 2.848s on ambiguous input; needs real recorded
  speech before tuning.
- Language: `language_code="en-IN"` locked. Hinglish / code-mixed works
  (verified pass 2). A fully Hindi utterance is not auto-detected — untested.
  `language_code="auto"` and `mode="codemix"` exist if needed.
- Single-process, in-memory sessions; `/sessions` unauthenticated. De-scoped
  deliberately — neither affects conversation quality.

---

## Pass 5 — tools and the agent loop

### Decision: two tools, richer schema

`update_finances` (batched upserts + removals) and `build_plan`. Nothing else.

Flexibility went into the item schema — optional amount and day ranges,
frequency, credit-card minimum due, already-paid status, certainty — rather
than into more functions, because every extra tool is another round trip
between the user finishing a sentence and hearing a reply.

Two things I deliberately did **not** make tools:

- **Reading state back.** The model needs it every turn, so it is returned as
  the *result* of every write instead. A `get_state` tool would add a round trip
  to fetch something already in hand.
- **Anything that draws a card.** Cards are derived from state, so they cannot
  drift out of step with the conversation — there is nothing for the model to
  forget to update.

Corrections need no tool of their own: re-using an id *is* the correction.

### Testing method: real model against the real handlers

Unit tests cover the handlers. Separately I ran the actual Sarvam model through
the real handlers in a loop, with natural spoken phrasing, and read the
transcripts. Everything below was found that way, not by unit tests.

Extraction was strong out of the box: "somewhere between eighteen hundred and
three thousand two hundred, comes mid month" produced `amount_min: 1800,
amount_max: 3200, day_min: 15, day_max: 20, certainty: estimated`. Hinglish
("Mera rent badh gaya hai, ab chaubees hazaar hai, paanch tareekh ko") produced
the correct fact. Weekly, already-paid, minimum-due and retraction all mapped
correctly.

### Bug: invalid enum values were accepted silently

The model returned `kind: "one_time"` — confusing the field with `frequency`.
`Literal` type hints are **not enforced at runtime**, so the fact was stored
with a nonsense kind. It then failed to match anywhere kind is tested, including
the check that decides what can be cut when money is short, so a wedding gift
would have been silently un-cuttable.

**Fix.** Explicit enum validation in `Fact.__post_init__`, with the allowed
values in the error message.

### Bug: the model explained its own tool failure out loud, then lost the number

With validation added, the first live run produced this, spoken to the user:

> "I need to record that properly. The system needs me to classify it. Let me
> mark it as an optional expense since it's a gift you choose to give."

Two faults. Internal mechanics leaked into speech, and having said it would fix
the entry, it never re-called the tool — the ₹15,000 was simply lost.

**Fix.** The error result now says exactly what to do ("call update_finances
again immediately with those items fixed, do not mention this to the user"), and
the system prompt forbids mentioning tools, recording, systems or classifying.
Re-ran: silent retry with the corrected kind, and the user just hears "Noted."

### Bug: the agent deadlocked asking which day someone eats out

Worst of the three. `missing()` demanded a due date for every expense, so:

> USER: I spend around five thousand eating out, and a thousand on streaming.
> KUBERA: When do you usually spend that five thousand — spread across the
> month, or on specific days?
> USER: That's everything. Can you tell me how the month looks?
> KUBERA: I need to know when that eating out money is due, otherwise I cannot
> run the numbers.

The user had given a perfectly plannable figure and the agent refused to plan.

**Fix.** Split blocking gaps from refinements. `missing()` now blocks only on
what genuinely prevents a plan (money on hand, income, essentials, an amount).
Undated monthly spending is spread evenly across the 30 days — which is also the
honest shape of it: "about five thousand eating out" does not happen on one
afternoon. Missing dates move to `would_sharpen()`, mentioned but never blocking.

Rounding is integer rupees with the remainder on day one, so the spread parts
still sum to the figure the user said. There is a test for that.

### Bug: the model did arithmetic anyway, and got it wrong

Despite the prompt saying not to, it said:

> "After rent on the fifth and the bike EMI on the seventh, you will still be
> left with about nineteen thousand."

The real figure was ₹34,600. Wrong by ₹15,600, stated confidently.

**Diagnosis.** The prompt forbade arithmetic but the tool result did not contain
the number the model wanted to say, so it worked one out. A prohibition with no
alternative just gets ignored.

**Fix.** `spoken_plan` now returns every figure the model might reach for —
`left_at_the_end`, `lowest_balance`, `lowest_balance_day` — precomputed, with an
instruction to read them rather than derive anything. After the fix it said
"you will end with twenty-eight thousand six hundred" and "the tightest point is
on the thirtieth of September with seven thousand seven hundred seventy-six",
both matching the tool output exactly.

**Lesson worth keeping.** Telling a model not to do something works far less
well than removing its reason to. Both the arithmetic and the leaked-mechanics
bugs were fixed by giving it what it needed, not by adding a stronger rule.

### Note on method

Every bug in this pass came from reading transcripts of the real model against
the real handlers. The unit tests were all green throughout — and stayed green
while the agent was deadlocking, losing numbers and stating wrong totals.
