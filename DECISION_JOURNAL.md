# Decision journal

Written by me while working on the RIVERLINE-R2 assignment. Entries recorded as work happened.

---

## Entry 1

```
Date/time: 12th September 10:35 AM

What happened: Going through the Notion assignment given by RIVERLINE-R2. Before building anything, going through PipeCat and Daily infrastructure — what they provide and what they don't, how it works in a real product scenario. Trying to understand the underlying tech (WebRTC) and what other concepts there are. Also looking at technologies similar to PipeCat and Daily. Did a little reading on the underlying tech for UDP etc. For now not focusing on the build itself — want to plan out the implementation plan first and then get started. Assuming need to build a web app with a real-time voice agent talking and taking information from the user about their financials.

What I noticed: WebRTC is basically a communication protocol for real-time audio media streaming. Daily follows a room structure where it's easier for scaling instead of having multiple peer-to-peer connections that grow really fast — that concept is intriguing.

Options considered: n/a

Decision + why: Stick to PipeCat and Daily because the assignment strictly mentions to use them. Plan implementation first, then build. Frontend first — use a cloud design to build some basic components and get the full front end out of the way so I don't block myself on front end bugs (eat the frog). Then plan out the architecture for the PipeCat runtime. Then see where it goes.

What I tested: n/a

What changed my mind: n/a

AI suggestions rejected/corrected: n/a

Limitations accepted: n/a
```

---

## Entry 2

```
Date/time: 12th September 11:05 AM

What happened:
- Been planning how to structure the repository and what tech stack to use.
- Needed to choose the architecture for the voice agent.
- Assignment requires Pipecat and Daily.
- Considered whether to deploy the application or run it locally.
- Assignment states deployment is not required.
- Required submission flow is `docker compose up --build`.
- Tried to see if there are easy ways to host it for free / for people to try; Daily cloud is not free and requires billing.

What I noticed:
- Next.js is a good fit for the web UI.
- Pipecat's agent runtime is Python-based / fully Python-based.
- Daily provides the real-time communication layer.
- Assignment requires real-time voice rather than recorded messages.
- Hosting is not required by the assignment.

Options considered:
- Next.js + TypeScript for everything
- Next.js frontend + Python/Pipecat backend
- Different/self-hosted real-time transport
- Local development vs hosted deployment
- Host the frontend and agent separately
- Fully self-host the real-time voice infrastructure
- Keep the application local and use Daily's hosted service
- (Earlier lean:) Next.js monorepo / simple project easily runnable without a lot of dependencies

Decision + why:
Architecture:
- Next.js for frontend.
- Python + Pipecat for agent.
- Daily for real-time voice transport.
- Keep both applications in one repository.
- Run locally with Docker Compose.
- Use Daily's free tier rather than paying for hosting.
Why: Keeps responsibilities separated; fits technologies required by the assignment; avoids unnecessary infrastructure work; keeps implementation simple enough to understand and modify; deployment isn't required so local Docker is sufficient. Python has better support for the voice agent. PipeCat and Daily are fixed.

Hosting / deployment:
- Keep the application locally runnable through Docker Compose.
- Use Daily's hosted infrastructure for the required real-time voice communication.
- Do not deploy the application since deployment is explicitly not required.
Why: Avoid unnecessary hosting and infrastructure complexity; evaluation is based on local execution; Daily provides the real-time layer without operating WebRTC infrastructure myself; for a voice-only take-home, expected usage is small enough to stay within Daily free usage.

Trade-off / limitation accepted:
- Application depends on Daily's hosted service for the real-time connection.
- In exchange, avoid building and operating the underlying WebRTC infrastructure myself.
- If this were a production system, would revisit hosting and infrastructure based on scale, reliability, and cost.

What I tested: Tried to see if there are any easy ways to host it for free.

What changed my mind: Was thinking Next.js monorepo / simple project with fewer dependencies; then shifted because Python has better support for the voice agent — Next.js frontend + Python/Pipecat agent in the monorepo.

AI suggestions rejected/corrected: —

Limitations accepted: (see Trade-off above)
```

---

## Entry 3

```
Date/time: 12th September 12:21 PM

What happened: Took a short lunch break. Have a cloth design ready. Going to start building the cloth design HTML components and convert them into React components in TypeScript. Scaffolded the basic codebase architecture with proper file structure, agent for the web, etc. Also done the Docker setup. Pretty much everything till now is scaffolding.

What I noticed: —

Options considered: —

Decision + why: Finish the front end components and lock on to a design language etc., then start building the PipeCat agent.

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 4

```
Date/time: 12th September 12:28 PM

What happened: Parallelly working on cloud design — testing edge case scenarios, stress testing, and different front end tests. Also started on the back end in parallel. This is only for scaffolding. Logged in a user flow:
1. User starts the call.
2. We do a POST call to the sessions endpoint.
3. The agent uses DailyAPI to create a room, user token, and bot token.
4. It starts a room with the bot token.
5. We return the session_id and URL token to NextWeb.
6. Parallelly, we also join the room using the user token via PipeCat.
Once the user is in the call, voice media works over WebRTC; user can end the call at any time while connecting or talking to the agent. After leaving, we delete the session, cancel the pipeline, and clean up the room, etc. This is the basic skeleton going with right now.

What I noticed: —

Options considered: Have not considered any other options because it is pretty straightforward from here; once implementing the actual agent, then will have different limitations, suggestions, etc.

Decision + why: Going with this basic skeleton for the session/call flow (as above).

What I tested: Edge case scenarios, stress testing, and different front end tests (cloud design). Backend scaffolding in parallel.

What changed my mind: —

AI suggestions rejected/corrected: So far, do not have any rejected AI suggestions.

Limitations accepted: —
```

---

## Entry 5

```
Date/time: 12th September 12:44 PM

What happened: Understood the difference between Daily and PipeCat a little bit more clearly. Created a Daily cloud account; going to put the API key and use it in the project. Had to go back and make basics much clearer on the exact difference between what Daily and PipeCat are doing. Also looking at GitHub repositories already being used — don't want to reinvent the wheel from scratch; want to see good practices for PipeCat agents using Daily online and borrow some logic from there.

What I noticed: —

Options considered: Other providers like Twilio or other things that do similar things as Daily.

Decision + why: Stick with Daily/PipeCat — since PipeCat is also managed by Daily, think this is the best approach. Use Daily API key in the project. Look at existing GitHub repos for practices / borrow logic rather than reinventing from scratch.

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 6

```
Date/time: 12th September 1:44 PM

What happened: Discussed Daily vs Pipecat vs Pipecat Cloud — different products/keys; not interchangeable. Architecture — Pipecat = pipeline; Daily = rooms/media; sessions = our FastAPI. Why Daily is required — Pipecat needs a transport; this repo chose Daily. GitHub templates — prefer official pipecat-ai examples over random forks. What to copy — architectural patterns, not code dumps / Cloud / telephony. Action items proposed (awaiting yes/no): (1) real Daily rooms/tokens (2) background bot on POST (3) teardown on every exit (4) status surfacing (5) secrets server-side. Explicitly not decided: whether to approve action items 1–5; STT/LLM/TTS vendor choices; any implementation work (none done in this chat).

What I noticed: Daily vs Pipecat vs Pipecat Cloud are different products/keys; not interchangeable. Pipecat = pipeline; Daily = rooms/media; sessions = our FastAPI. Pipecat needs a transport; this repo chose Daily.

Options considered: Pipecat Cloud vs local; telephony; Voice UI Kit as a product dependency; random GitHub forks vs official pipecat-ai examples.

Decision + why:
- Host the bot: Local Docker Compose (not Pipecat Cloud)
- Media / rooms: Daily Cloud + DAILY_API_KEY
- Ignore for now: Pipecat Cloud API keys, telephony, Voice UI Kit as a product dependency
- Keep as-is: Split daily.py / bot.py / server.py; session API owns lifecycle
- Secrets: Server-only; browser gets room URL + user token only
- Reference repos: Official — simple-chatbot, core examples/, client-web — patterns only

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: Explicitly not decided — whether to approve action items 1–5; STT/LLM/TTS vendor choices; any implementation work (none done in this chat).
```

---

## Entry 7

```
Date/time: 12th September 9:13 PM

What happened: Resuming work on the project now; was occupied with freelance project. Design system ready along with all the scaffolding. Choosing STT/LLM/TTS-related provider with Indian language support. Found couple of boilerplates for Pipecat agent using Sarvam. Plan: first build a basic conversational agent that works decently well, then build incrementally by adding tools, UI support and more in-depth.

What I noticed: Riverline caters to the Indian population; a large part of the population speak regional languages. Sarvam and Rumik AI among the best models with good Indian languages support. Rumik has really good Hinglish TTS support; downside is it's only TTS. Have a bunch of free credits from Sarvam. Found couple of boilerplates for Pipecat agent using Sarvam.

Options considered: Sarvam; Rumik AI (Hinglish TTS but only TTS).

Decision + why: Go with Sarvam — have free credits from Sarvam; want provider with regional/Indian language support; Rumik is TTS-only. Start with basic conversational agent first, then incrementally add tools, UI support, more in-depth.

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 8 — Progress / E2E agent + UI

```
Date/time: 12th September ~10:57 PM

What happened: Trying to work in between blocks so I don't get bored. Reproduced a proper end-to-end working conversational agent without any action capabilities. Noticed the template wasn't that great, so had to make my own improvements. Also did some Next.js metadata cleanup housekeeping. Added simple live feedback to show audio levels in the UI. Frontend states wired up to the right events such as onBotLlmStarted, etc. Added keyboard shortcuts to quickly mute/end calls.

What I noticed: Template wasn't that great.

Options considered: —

Decision + why: Make own improvements; keep agent conversational-only for now (no action capabilities). Wire frontend states to the right events; add live audio-level feedback and mute/end keyboard shortcuts.

What I tested: End-to-end conversational agent (working).

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: No action capabilities yet.
```

---

## Entry 9 — Captions / speech cut off

```
Date/time: 12th September ~10:57 PM

What happened: Tried improving conversation quality. Some words were getting cut off while speaking. Made agent monitor logs from Docker container to understand what was going wrong.

What I noticed: Speech segments were getting captured twice on bot-output.

Options considered: Basic text content dedupe logic (AI suggestion); rewrite captions as turn-based model logic.

Decision + why: Rejected basic text content dedupe. Rewrote captions as turn-based model: only on spoken_status -> new, add the text; in-progress and completed advance a cursor matched by segment id; a turn is closed only by bot-stopped-speaking and not by a segment.

What I tested: Monitored Docker container logs; diagnosed double capture on bot-output.

What changed my mind: —

AI suggestions rejected/corrected: Agent suggested basic text content dedupe logic — rejected; rewrote captions as turn-based model logic instead.

Limitations accepted: —
```

---

## Entry 10 — Double greetings

```
Date/time: 12th September ~10:57 PM

What happened: Greetings were firing twice.

What I noticed: on_client_connected and on_participant_joined were essentially doing the same thing.

Options considered: —

Decision + why: Fixed by having just on_first_participant_joined with a only-once guard. Also added an 8s watchdog to speak a fixed line instead of a dynamic line every time.

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 11 — Session lifecycle

```
Date/time: 12th September ~10:57 PM

What happened: Improved the session lifecycle.

What I noticed: —

Options considered: —

Decision + why: Added idle timeout, graceful ending with a goodbye. Closing the tab also now cleans up the session (delete session call).

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 12

```
Date/time: 13th September 12:46 AM

What happened: Another block now. Been using OpenRouter GPT-4o mini for LLM with Sarvam TTS/STT. Everything was perfect but the LLM turn was causing a lot of latency compared to the other steps in the pipeline. Testing it out with Sarvam 105b model for completions also. Will take further steps based on how the metrics change.

What I noticed: LLM turn causing a lot of latency compared to other steps in the pipeline. Sarvam 105b much better for Indian languages. Already have Sarvam package for Pipecat — shouldn't be hard integrating.

Options considered: OpenRouter GPT-4o mini (LLM) + Sarvam TTS/STT; Sarvam 105b for completions also.

Decision + why: Testing Sarvam 105b for completions — better for Indian languages; already have Sarvam package for Pipecat so integration shouldn't be hard. Further steps based on how metrics change.

What I tested: Switching LLM to Sarvam 105b; watching metrics/latency vs OpenRouter GPT-4o mini.

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 13 — LLM provider: Sarvam default

```
Date/time: 13th September ~12:48 AM

What happened: Done. Sarvam is now the default LLM; OpenRouter stays fully wired as an alternative. Benchmarked time-to-first-content-token on a realistic mid-call turn (real system prompt, 4 turns of history), 6 samples each, through my own keys — full table in docs/metrics-llm-latency-2026-09-13.md. Before committing I checked things speed is worthless without: replies are short and voice-shaped; handled Hinglish input ("Mera rent badh gaya hai by four thousand"); tool calling works — "twenty four thousand rupees" → log_expense(category="rent", amount_inr=24000) with finish_reason: tool_calls. That was the gate, given where I'm headed next. Changes: bot.py — _build_llm() switching on LLM_PROVIDER (sarvam default, openrouter alternative), UserBotLatencyObserver + per-call p50/p95 summary, max_tokens=200. OpenRouter default also moved off gpt-4o-mini to gpt-4.1-nano so that path isn't the slowest option measured. .env.example — documents LLM_PROVIDER, SARVAM_LLM_MODEL; notes OPENROUTER_API_KEY only needed for that provider. docs/decisions-voice-ux.md — pass 3 appended with benchmark table, A/B, and turn-detection finding.

What I noticed: Sarvam won on both median and consistency — consistency matters more. Old setup ranged 0.7s–2.9s on identical requests because OpenRouter re-routes per call. In-pipeline: LLM inference dropped from ~1.7s to 0.33s. Clean turns now complete in 1.33–1.46s end to end, down from ~2.4s.

Options considered: sarvam-105b-conversations; ministral-8b; llama-3.1-8b (Groq); gpt-4.1-nano; claude-haiku-4.5; gemini-2.5-flash-lite; gpt-4o-mini (was).

Decision + why: Sarvam default LLM — won median and consistency; good on voice-shaped replies, Hinglish, and tool calling. Keep OpenRouter fully wired as alternative. Metrics live in a separate file because results will change after I add more things.

What I tested: Benchmark above; Hinglish input; tool calling gate; in-pipeline latency after switch.

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 14 — Turn detection now the bottleneck (correction)

```
Date/time: 13th September ~12:48 AM

What happened: I have to correct something I told myself / recorded earlier. In pass 2 I said turn-taking was fine and not worth touching. The instrument says otherwise. With the LLM fixed, turn detection became the dominant cost on ambiguous turns. Instrumented breakdown in docs/metrics-llm-latency-2026-09-13.md (endpointing, transcription, turn detection 2.848s, LLM, TTS → 4.270s total). That 2.848s sits just under smart-turn's 3s stop_secs ceiling — the model never got confident the user had finished and fell back to the silence timeout.

What I noticed: After LLM fix, turn detection is the biggest cost. Caveat I'd hold onto rather than act on: that was Chrome's fake-audio device, which is noise, not speech. Smart-turn stalling on ambiguous input is expected.

Options considered: Tune turn detection now vs wait for real recorded speech.

Decision + why: Hold onto the caveat rather than act on it yet — want real recorded speech before tuning. It's now measurable, and it's the next thing to look at.

What I tested: Instrumented pipeline timings (fake-audio).

What changed my mind: Earlier “turn-taking fine / not worth touching” — instrument showed otherwise after LLM latency was fixed.

AI suggestions rejected/corrected: —

Limitations accepted: Fake-audio measurement only; don't tune smart-turn until real recorded speech.
```

---

## Entry 15 — Stale Docker on 7860

```
Date/time: 13th September ~12:48 AM

What happened: One thing worth knowing for later: a Docker container is listening on 7860, so localhost:7860 from a browser can hit that stale build over IPv6 instead of a locally-run agent. Cost me a confusing test run.

What I noticed: Browser can hit stale Docker build on 7860 via IPv6 instead of local agent.

Options considered: —

Decision + why: —

What I tested: Confusing test run hit stale container.

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 16

```
Date/time: 13th September 12:55 AM

What happened: Latency has gone down by a lot. Hinglish support feels much better compared to the previous GPT-4o mini. Going to try and finish the end-to-end product before working on any more improvements.

What I noticed: Latency down a lot; Hinglish feels much better vs GPT-4o mini.

Options considered: More improvements now vs finish end-to-end product first.

Decision + why: Finish the end-to-end product before working on any more improvements.

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 17

```
Date/time: 13th September 11:46 AM

What happened: Resuming work again. Entire agent and everything ready along with the UI. UI made initially is not greatly readable. Since I have to show calculations and the ledger entirely properly in the UI, trying to simplify and make it properly user readable so that it's a polished product. Will get to actual agent-level testing again later once the product experience is properly done.

What I noticed: Initial UI not greatly readable — especially for calculations and the ledger.

Options considered: Agent-level testing now vs polish product experience / readable UI first.

Decision + why: Simplify and make UI properly user readable (calculations + ledger) for a polished product. Defer agent-level testing until product experience is properly done.

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 18

```
Date/time: 13th September 2:25 PM

What happened: Resuming work again after a bit. Built the entire agent. Trying to resolve a couple of issues by checking the actual Sarvam PipeCat documentation because the given examples are very basic and not useful — going through docs for parameters to tweak (waiting time before the agent takes its turn; transcription speed — modes like balanced, fast, etc.). Testing these things. Included a calendar view and proper calculation logic with all the tool calls, but not fully usable because system prompt and tool calls are not fully worked on yet — these are basic ones. Will try to make voice agent experience much better, then go into deeper logic of actual financial planning.

What I noticed: Given examples are very basic and not useful. Calendar/calculation/tool calls exist but not fully usable yet — system prompt and tool calls still basic.

Options considered: —

Decision + why: Improve voice agent experience first (docs tweaks: turn wait, transcription speed modes), then deeper financial planning logic.

What I tested: Tweaking Sarvam/PipeCat parameters (waiting time before agent turn; transcription speed modes: balanced, fast, etc.).

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: System prompt and tool calls still basic; calendar/calc/tools not fully usable yet.
```

---

## Entry 19

```
Date/time: 13th September 2:31 PM

What happened: Trying to test/tweak these parameters and see how conversation quality changes. Planning tweaks: bump stop seconds a little more — around 1 to 2 seconds at least; reduce confidence for speech-to-text a little because some words not getting captured correctly; experiment with stream type later; language code can be english for now; add some prompt that is the optional hint to help; increase temperature of text-to-speech a little; try text_aggregation_mode as token.

What I noticed: Some words not getting captured correctly. Stop seconds bumping is definitely going to be useful. Couple of other parameters trying out to see how conversation quality improves.

Options considered: Stream type (later); language codes (english for now); text_aggregation_mode as token; stop_secs ~1–2s; STT confidence lower; TTS temperature higher; optional hint prompt.

Decision + why: Bump stop seconds (~1–2s at least) — definitely useful. Reduce STT confidence a bit. Language code english for now. Add optional hint prompt if we can. Increase TTS temperature a little. Try text_aggregation_mode as token. Stream type later. Experiment and see how quality changes.

What I tested: Tweaking these parameters / watching conversation quality.

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: Stream type deferred for later; language fixed to english for now.
```

---

## Entry 20

```
Date/time: 13th September 3:16 PM

What happened: Had an amazing lunch; feel really sleepy. Arrived at a really good voice agent part — entire TTS/STT/completions pipeline works perfectly. Need to work on actual system prompt and tool calls a little more so scaffolding for the financial planner agent is improved. Also need to work on the copy so text feels more human and much more personal. Those are next steps — will work on that after a very short nap. Going through Sarvam docs and tweaking parameters (stop seconds and other things) actually really helped; will include that in commit messages and will commit.

What I noticed: Pipeline works perfectly. Sarvam docs + parameter tweaks (stop seconds etc.) really helped.

Options considered: —

Decision + why: Next — improve system prompt and tool calls (financial planner scaffolding); improve copy for more human/personal text. Nap first, then that. Commit with notes on Sarvam param tweaks.

What I tested: TTS/STT/completions pipeline (works perfectly); Sarvam parameter tweaks.

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: System prompt, tool calls, and copy still need more work.
```

---

## Entry 21

```
Date/time: 13th September 3:51 PM

What happened: Initial basic system prompt had a set of things it would walk through, like essential income, etc. Trying to remove these fixed categories or questions the agent asks and make it more flexible so any sort of information can be captured. Moving to a JSON-based approach to capture any sort of information. Also realized there is no way to mark something as none (e.g. user doesn't have any credit card) — adding that support. Also including a confirmation step for each of the numbers so the data is more solid.

What I noticed: Fixed categories/questions limit flexibility. No way to mark something as none today (e.g. no credit card).

Options considered: Fixed walkthrough categories vs flexible capture; JSON-based approach.

Decision + why: Remove fixed categories/questions; JSON-based approach for any information; add “none” support; confirmation step for each number for more solid data.

What I tested: —

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 22

```
Date/time: 13th September 10:06 PM

What happened: Agent pretty much working end to end perfectly. One other problem: since added a lot of tool calls, latency has increased a little bit. Also not added any thinking or status indicators to show it's executing tool calls in between. Next step: make sure agent properly follows three steps — (1) Gather all the information (2) Confirm all the information provided by the user (3) Build a plan. Following these for a working individual in India (rent, electricity, Wi-Fi, and basic things). Once user confirms details/financials, plan is generated and shown in a calendar view. Trying to solve latency issues and add thinking/status indicator in the agent UI so it doesn't feel like a jarring experience.

What I noticed: More tool calls → latency up a little. No thinking/status indicators during tool execution — can feel jarring.

Options considered: —

Decision + why: Enforce three-step flow (gather → confirm → build plan) for working individual in India basics; show plan in calendar after confirm. Fix latency; add thinking/status indicator in UI during tool calls.

What I tested: End-to-end agent (working perfectly aside from latency/UX gap).

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: Latency up from tool calls; no tool-status UI yet.
```

---

## Entry 23

```
Date/time: 14th September 12:24 PM

What happened: Resuming work again; gonna wrap up in a bit so I can focus on the demo video. Built a financial planner but didn't really feel like it was enough. Chatted with another Claude agent without any context of what was happening here. Trying to draft a fresh system prompt and a proper back end structure — edge cases, scenarios the agent has to handle, depending on what sort of questions the user might ask. Going to get rid of the existing prompt and tool calls, and define prompt and other things from scratch.

What I noticed: Financial planner as built didn't feel like enough.

Options considered: Keep iterating on existing prompt/tools vs scrap and redefine from scratch (with help from a fresh Claude chat, no prior context).

Decision + why: Get rid of existing prompt and tool calls; define prompt and other things from scratch — fresh system prompt + proper backend structure covering edge cases, scenarios, and user question types. Wrap up soon to focus on demo video.

What I tested: —

What changed my mind: Built planner didn't feel like enough → moving to fresh draft from scratch.

AI suggestions rejected/corrected: —

Limitations accepted: —
```

---

## Entry 24

```
Date/time: 14th September 10:25 PM

What happened: Rewrote system prompt, tool calls, and summarization logic for the agent, and a little bit of the UI for better look / better sections on the side. Couldn't get time to improve calculation logic / how the ledger is maintained. Bunch of agent-latency optimizations possible — latency reasonably good but can be improved. Limited set of tool calls to avoid getting bloated (limits ability to look at data and calculate any way it wants). Advice okay — looks at transactions and upcoming transactions; would improve. Would improve consistency (e.g. bulk vs one-by-one transactions). Not really gotten time to test that fully, but tested with real-life use cases and test data; some optional improvements done. Looks at where you'll come short / surplus; doesn't suggest settlement or repayment offers or things that harm the user; suggests decent financial advice based on inflow and outflow. Voice agent works well on optic consistency and latency. Could have worked more on calculation engine — thought assignment goal was how agent/experience feels and agent optimization. Would improve calculation engine and tool calls so it doesn't get bloated / hallucinate. Currently doesn't really hallucinate; pretty consistent with data provided. Extra optional depth: implemented summarization — conversational intelligence improved; handles corrections and interruptions properly; avoids repeated questions; keeps track of data correctly; UX feels natural. Would improve how final financial advice is presented in the UI (might not be highlighted correctly) but it works. Tested with a lot of real-life use cases. Wrapping up; creating demo video now.

What I noticed: Latency reasonably good but improvable. Limited tools avoid bloat but constrain flexible calc. Doesn't really hallucinate; consistent with provided data. Advice presentation in UI might not be highlighted correctly. Voice agent good on optic consistency and latency.

Options considered: More calculation-engine / ledger work vs focus on agent experience and optimization (assignment goal as I saw it). Bulk vs one-by-one transaction consistency (not fully tested).

Decision + why: Wrap up and create demo video. Accept current state: limited tools, decent advice, summarization/optional depth in; defer deeper calc engine, more latency opts, consistency testing, and advice UI highlighting.

What I tested: Real-life use cases and test data; a lot of real-life use cases. Optional improvements. Consistency bulk vs one-by-one not really fully tested.

What changed my mind: —

AI suggestions rejected/corrected: —

Limitations accepted: Calculation/ledger not improved as much as I'd like. Latency can still improve. Limited tool set. Consistency across bulk vs sequential input not fully tested. Final advice UI highlighting not as good as it could be. Didn't go deeper on calc engine given assignment focus on agent/experience/optimization.
```
