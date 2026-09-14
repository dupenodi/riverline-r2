# Assignment checklist

Riverline AI Engineer take-home. `[x]` done, `[ ]` still open.
Decision journal is owned by a separate pass — do not generate it here.

## Submit

- [x] `docker compose up --build` brings up web + agent
- [x] README: Docker, every env var, where keys come from, exact command, exact URL
- [x] `.env.example` matches the variables the code reads
- [x] Tests: 67 agent + 31 web, engine math without a microphone
- [ ] Demo video
- [ ] Decision journal (`DECISION_JOURNAL.md`, hand-written; AI text disqualifies)

## Voice (assignment §2)

- [x] Start / end a call in the browser, speak naturally
- [x] Real-time agent on Pipecat + Daily
- [x] Live transcript (turn model, spoken-cursor dimming, barge-in)
- [x] Greeting, idle timeout, hang-up / tab close
- [x] Conversational Indian English, one question at a time, not a fixed form
- [x] Corrections: reuse item `id`, send only the change
- [x] Conflicting amounts stay visible; agent can ask which is right
- [x] After “that’s all”, wait for yes, then recap from `speak` (no recomputing)
- [ ] Full Hindi utterance under `en-IN` lock (Hinglish verified; Hindi-only not)

## Finance engine (assignment §4 — calculations visible and testable)

- [x] LLM never does arithmetic; `cashflow.project(today, cash, entries)` owns numbers
- [x] 30 days from today (not a calendar month); order of cash flows, not monthly totals
- [x] Same totals, opposite sequence: salary 10th / rent 20th vs salary 28th / rent 3rd
- [x] Ranges resolve against the user (inflow min, outflow max)
- [x] Daily / weekly / once / monthly cadences; daily burn × 30 in upcoming
- [x] Relative dates via `in_days` (tomorrow = 1), not a guessed calendar day
- [x] `owed` is money coming in; `debt` is money they must pay
- [x] Two amounts on two dates are two facts (same label allowed)
- [x] Paid this cycle is not counted again as due
- [x] No borrow / loan / invest action in the planner
- [x] Unsolvable path states the gap; does not invent a way out
- [x] Advice payoff (lowest + date) is engine-owned; bullets may be rewritten by Sarvam

## Agent tools (assignment §3)

Two tools. Flexibility is in the item schema.

    record(name?, cash?, items[])
    forget(ids[])

- [x] `record` / `forget` only — no `get_state` (state is the tool result)
- [x] Snapshot published over RTVI after every mutation (`version` monotonic)
- [x] Server-side enum validation; bad args instruct a silent retry
- [x] Prompt: speak only numbers from `speak`, never mention tools, never invent
- [x] Vague amounts (`amount_min` / `amount_max`) and days (`day_min` / `day_max`)
- [x] Credit-card `min_due` in the schema (used when the user gives it)

## Generative UI (assignment §3)

Client is a renderer. One snapshot. No second copy of the math.

- [x] Calendar: 30 days from today, in/out dots, day sheet with labelled moves
- [x] Rail: cash, finish, lowest, entries by kind, missing, conflicts
- [x] Advice: bullets from this ledger, **Payoff** last and highlighted
- [x] Cards appear as they fill; empty rail is omitted
- [x] Changed groups pulse
- [x] Client drops snapshots with `version` ≤ current
- [x] Estimates read as a range (`~`), not a fake exact

## Optional depth

- [ ] Track A — deeper conversational eval
- [ ] Track B — recorded-speech regression set

## Known limitations (accepted)

- STT can hallucinate fluent text from non-speech (Silero lets tonal noise through)
- Smart-turn ~2.8s on fake-audio; needs real recordings before tuning
- `/sessions` is unauthenticated (local demo)
- SIPs land as `debt` if that is how they were recorded
- Advice rewrite needs `SARVAM_API_KEY`; without it the rail still shows engine-backed draft bullets
