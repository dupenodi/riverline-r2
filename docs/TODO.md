# Kubera — assignment TODO

Tracks the Riverline assignment requirements. `[x]` = done, `[~]` = partial.

## Done

- [x] Web app: start/end a voice call, speak naturally
- [x] Real-time voice agent on Pipecat + Daily
- [x] Live transcript (turn model, spoken-cursor dimming, barge-in marks)
- [x] Greeting / idle / session lifecycle
- [x] Turn-latency instrumentation + provider benchmark
- [x] `docker compose up --build` brings up web + agent, one command

## 1. Financial core  (assignment §4 — "calculations must be visible and testable")

- [x] `finance.py` — facts model: id, kind, label, amount, day_of_month,
      certainty (known|estimated); conflict tracking on re-statement
- [x] `plan.py` — 30-day day-by-day timeline, running balance, min-balance day
- [x] Shortfall resolution: cut optional, then card minimums, then a
      restoration pass so no unnecessary sacrifice survives
- [x] Unsolvable path: state the gap plainly, never invent a way out
- [x] Hard constraints in code: no borrow action exists in the vocabulary
- [x] `tests/test_plan.py` — 35 tests, all passing

## 2. Agent tools  (assignment §3)

Two tools only. Flexibility lives in the item schema, not in more tools —
every extra tool is another round trip on the latency path.

    update_finances(items: [...], remove: [id])
      id          LLM-chosen, stable; re-using an id IS the correction
      kind        income | essential | debt | optional | balance
      label       "Rent", "HDFC car loan"
      amount      integer rupees
      amount_min/max          "around 40 to 50 thousand"
      day / day_min / day_max "the 5th" | "first week" | "mid-month"
      frequency   monthly | weekly | quarterly | one_time
      minimum_due credit cards: min vs full balance
      status      due | already_paid
      certainty   known | estimated

    build_plan()  — run planner, publish final plan

- [x] `update_finances` with the schema above
- [x] `build_plan`
- [x] Server-side validation incl. enum checking (Literal is not enforced at
      runtime); errors return an instruction to retry silently
- [x] State returned as the result of every write (no get_state tool)
- [x] Rewrite system prompt: no arithmetic, no invented numbers, no leaking
      tool mechanics into speech, the five must-nots
- [ ] Re-check turn latency with tool calls on the critical path

### Conversation edge cases the schema must survive

- [x] Vague amounts: "around 40-50k" -> range + certainty=estimated
- [x] Vague dates: "first week", "mid-month" -> day_min/day_max
- [x] Non-monthly cadence: weekly groceries hit the 30-day window 4x
- [x] Credit card min-due vs full balance (the main shortfall lever)
- [x] "I already paid this month's EMI" -> status=already_paid, not counted
- [x] One-off lumps: "wedding gift 15k on the 20th"
- [x] Retraction: "forget the gym thing" -> remove
- [x] Same thing named twice ("electricity" / "power bill") -> same id
- [x] Multiple facts in one utterance -> batch
- [ ] "How much have I told you so far?" -> read injected state, no tool call
- [ ] Income landing AFTER the crunch (salary 28th, rent 3rd) — the case a
      monthly-totals approach gets wrong

### Language (no change unless the test fails)

Currently language_code="en-IN" locked on STT and TTS. Hinglish / code-mixed
speech works (verified in pass 2). A fully Hindi utterance under an en-IN lock
is NOT auto-detected.

- [ ] TEST: speak a full Hindi sentence, see what en-IN returns
- [ ] Only if it fails: language_code="auto", or mode="codemix"

## 3. Generative cards  (assignment §3)

Server computes everything; the client is a dumb renderer over one snapshot.
A second client-side implementation of the math could disagree with the tested
one, and then "calculations are visible and testable" stops being true.

    { type: "finance_state", version: 7,
      facts: [...],
      derived: { position, timeline[30], missing[], conflicts[] },
      plan: null | {...} }

Monotonic `version` so a late message cannot overwrite a newer one.

- [x] Push `finance_state` snapshot over RTVI after every mutation
- [ ] Client store, ignores any snapshot with version <= current

### Components

- [ ] `PositionCard` — hero: surplus/shortfall AND when it hits
- [ ] `CashflowCalendar` — THE centerpiece. 30 days from today (not a calendar
      month — the window straddles two months), 5 rows of 7, month boundary
      marked, each cell tinted by closing balance, crunch day flagged
- [ ] `MoneyInHand` / `IncomeCard` / `EssentialsCard` / `DebtsCard` /
      `OptionalCard` — the ledger, each appearing only once it has content
- [ ] `MissingInfoCard` — what's still needed; doubles as progress
- [ ] `ConflictCard` — "you said 20k, then 24k"
- [ ] `PlanCard` — ordered actions, or the plain unsolvable statement

### Cross-cutting

- [ ] Changed cards pulse — the user sees their words land. This is what makes
      it feel generative rather than a dashboard
- [ ] Estimates visually distinct (dashed, ~ prefix) — a guess must never read
      as a fact
- [ ] Layout: voice left (orb, transcript), cards right; tabs on mobile
- [ ] Empty state: cards appear as they fill, not 9 empty boxes at call start

## 4. Conversation quality  (assignment §2)

- [ ] Ask for clarification on conflicting numbers
- [ ] Handle corrections to previously given information
- [ ] Confirm the user understands the plan
- [ ] No fixed questionnaire — questions driven by what is missing

## 5. Submission

- [ ] README: Docker setup, every env var, how to supply keys, exact command,
      exact local address
- [ ] `.env.example` matches the final variable set
- [ ] Test + evaluation results
- [ ] Short list: what works / what doesn't / what's next / where AI helped /
      where AI was wrong
- [ ] Demo video
- [ ] **Decision journal — must be written by me, not AI. AI-written content
      disqualifies the submission. Write entries while working.**

## Optional depth (pick ONE track)

- [ ] Track A — conversational intelligence (overlaps §4, cheaper from here)
- [ ] Track B — evaluation & regression testing

## Known limitations (documented, not fixed)

- STT hallucinates fluent text from non-speech audio (Silero lets tonal noise through)
- Turn detection measured at 2.8s on ambiguous input; needs real recorded
  speech before tuning
- Single-process, in-memory sessions; `/sessions` unauthenticated
