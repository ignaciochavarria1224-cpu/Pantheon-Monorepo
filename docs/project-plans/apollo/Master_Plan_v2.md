# Master Plan: Project Apollo
### A Unified, AI-Native Personal Operating System — and Eventually, a Digital Twin

> *This is the complete non-technical roadmap. No code. No weekly tasks. Only the vision, principles, phases, and integration logic.*

---

## I. The Core Vision

You are not building a chatbot. You are not building a dashboard.

You are building two things simultaneously — and understanding the difference matters:

**Layer 1 — The Operating System.** A single intelligent agent that sits above all your existing tools (Olympus, Meridian, Black Book), accepts natural language, and acts as your executive function. A command center that unifies everything you've already built.

**Layer 2 — The Digital Twin.** Over time, as Apollo absorbs your decisions, reasoning, patterns, journals, and mental models, it stops being a tool you use and starts becoming a mirror of how you think. The endgame is not "an AI assistant." It is an AI version of you — one that knows your data, mimics your reasoning style, can answer questions *as* you, and eventually makes decisions you would make without needing to ask every time.

**Layer 1 is the foundation. Layer 2 is the destination.**

The three existing systems become peripherals of Apollo:

- **Black Book** = your financial ledger (Reflex app, Neon PostgreSQL)
- **Meridian** = your long-term memory and reasoning engine (Obsidian vault + Karpathy framework; codebase embedded in Black Book)
- **Olympus** = your automated trading and funding engine; its decision brain is **Apex** (paper trading, currently isolated)

Apollo is new. It has its own app, its own name, its own memory, and its own personality. Everything else adapts to it.

---

## II. Apollo's Own Mind

This is the most important architectural idea that distinguishes Apollo from a simple integration layer.

Apollo does not just *read* from your other systems. It builds and maintains its **own persistent memory** — a living model of who you are.

### What Apollo Remembers

| Memory Type             | What It Contains                                    | Where It Lives    |
|-------------------------|-----------------------------------------------------|-------------------|
| **Conversation History**| Every interaction with Apollo, timestamped          | Apollo local DB   |
| **Learned Patterns**    | Habits, tendencies, behavioral rhythms              | Apollo local DB   |
| **Decision Log**        | Decisions you've made + the reasoning you gave      | Apollo local DB   |
| **Mental Models**       | Your beliefs, frameworks, principles, how you think | Apollo Mind Vault |
| **The Self**            | A continuously updated model of you as a person     | Apollo Mind Vault |

### The Apollo Mind Vault

Apollo's highest-level memory lives in its own Obsidian vault — separate from Meridian's vault, but linked to it.

- **Meridian's vault** = your journals, raw thoughts, daily notes, question cycles. The *input* of your mind.
- **Apollo's Mind Vault** = distilled knowledge about *you* — extracted patterns, articulated mental models, decision frameworks, self-knowledge. The *model* of your mind.

Apollo reads Meridian's vault as source material. It writes its own conclusions into the Apollo Mind Vault. Over time, the Mind Vault becomes the substrate of the digital twin.

Think of it this way: Meridian captures what you think. The Apollo Mind Vault captures *how* you think.

---

## III. First Principles (The Constitution)

1. **You are the source of truth.** Apollo records what you say. It never assumes, hallucinates, or overwrites without confirmation.
2. **No unnecessary duplication.** Financial facts live in Black Book. Raw journals live in Meridian. Distilled self-knowledge lives in the Apollo Mind Vault. Each system owns its domain.
3. **AI is a tool, not the system.** LLMs provide understanding and generation. The real intelligence is the retrieval system that finds the right data at the right moment.
4. **Voice and text are equal.** Whisper to your phone or type on your laptop — same result, same routing.
5. **Privacy by default.** Everything runs locally or on your own infrastructure. No third-party cloud training on your life.
6. **You are the owner.** Any API keys are yours. No hidden subscriptions. No monthly fees to use your own system.
7. **Idempotency matters.** Telling Apollo the same thing twice does not duplicate records. It asks first.
8. **Graceful failure.** If a connected system is unavailable, Apollo queues the action and syncs later.
9. **Auditability always.** Every action Apollo takes is logged: `2026-04-13 14:32 — Added expense $15 lunch per user voice.`
10. **Autonomous action is earned, not assumed.** Apollo asks before acting until it has demonstrated it knows you well enough to be trusted. Autonomy is unlocked phase by phase.

---

## IV. The Five Phases of Apollo

Each phase delivers a working, valuable system. You stop at any phase and have something real.

**The phases are ordered by what to build first** — not by complexity. Phase 1 is the bridge, because without connecting your systems, nothing else is possible.

---

### Phase 1: The Bridge

**Goal: Apollo connects, reads, and triggers your three existing systems.**

This is the first priority. Before Apollo can record, query, or learn — it must be able to talk to Olympus, Meridian, and Black Book. Everything else is built on top of this.

**Capabilities:**

- Apollo can read from Black Book (account balances, recent transactions, category summaries)
- Apollo can read from Meridian (scan Obsidian vault, retrieve journal entries, trigger the question cycle)
- Apollo can read from Olympus (consume its exported status file — PnL, positions, alerts via Apex)
- Apollo can trigger each system's own processes on command
- Apollo **cannot write to Olympus** — read-only, always

**What you can say:**

- "What's Olympus doing right now?"
- "Run the Meridian question cycle."
- "Show me Black Book's spending summary for this month."
- "What positions is Apex holding?"

**Current integration reality:**

- Meridian already has its own codebase embedded inside Black Book — this connection is the template for how Apollo integrates
- Olympus is currently isolated; Phase 1 establishes its read-only export contract (a JSON status file written by Apex on a timer)
- Olympus and Black Book share a Neon database — this is confirmed and means Apollo can read both with a single connection

**Success feels like:** A unified command center. One voice. Three systems respond.

---

### Phase 2: The Recording Secretary

**Goal: Apollo reliably captures what you say, in your own words, into the right place.**

**Capabilities:**

- You speak or type a fact — expense, journal entry, investment note, decision, idea
- Apollo identifies the type and routes it to the right system
- Apollo confirms what it recorded and where
- Apollo can be reached via the Reflex web UI, via voice, or via WhatsApp message (see Delivery Channels)

**What you can say:**

- "Spent $40 at CVS, health, from checking."
- "Journal: had a good meeting with Marcus today, he's interested in partnering."
- "Decision: I'm going to hold NVDA through earnings because of X."

**Decision logging** is a first-class entity type here — not just expenses and journals. Every decision you log feeds the digital twin.

**Session approvals** are introduced here. Apollo uses three permission levels and remembers which you've granted:

| Phrase             | Behavior                                          |
|--------------------|---------------------------------------------------|
| *"just this once"* | Execute without asking — ask again next time      |
| *"always allow"*   | Remember permanently; never ask for this action again |
| *silence / default*| Always ask before acting                          |

**Success feels like:** A reliable digital clerk that never misplaces a receipt, a thought, or a choice.

---

### Phase 3: The Oracle

**Goal: Apollo answers questions about all your recorded data — and delivers a briefing without being asked.**

**Capabilities:**

- Natural language questions translated to structured queries (Black Book)
- Full-text and semantic search of Meridian's Obsidian vault
- Cross-system answers: "How much did I spend the week Olympus had its worst drawdown?"
- Answers always include sources (date, system, note title)
- **Daily Brief:** Every morning, a scheduled agent runs automatically. It checks Olympus status, yesterday's spending, any open Meridian questions, and optional news topics you care about. It delivers a single brief — either spoken aloud or sent as a notification — without you asking.

**What you can ask:**

- "How much did I spend on groceries last month?"
- "What did I journal about stress in February?"
- "What was my reasoning when I first bought NVDA?"
- "On the days I logged poor sleep, how did my spending change?"
- "Give me the morning briefing." *(or it just runs at 7am)*

The cross-system question is the most powerful capability here — it's something none of your three systems can do alone. The Daily Brief makes Apollo proactive for the first time.

**Success feels like:** A private, intelligent search engine over your entire life — plus a morning briefing that arrives before you even open your phone.

---

### Phase 4: The Chronicler

**Goal: Apollo learns your patterns, acts without being told, and triggers cross-system responses when something meaningful happens.**

**Capabilities:**

- Detects behavioral patterns (time-based, category-based, sentiment-based)
- Surfaces anomalies proactively: "Your spending this week is 40% above your average."
- Asks clarifying questions at the right moments: "You usually log a coffee expense around 8am — did you skip today?"
- Begins populating the Apollo Mind Vault with inferred mental models: "I've noticed you always reduce risk in your portfolio when your journal sentiment is negative."
- **Cross-system triggers:** When a pattern or event fires in one system, Apollo can initiate an action in another. Examples:
  - Black Book detects overspending in a category → Meridian gets a prompt to ask about it in tomorrow's journal cycle
  - Olympus (via Apex) reports a drawdown above your threshold → Meridian queues a reflection question; Apollo notifies you immediately
  - Meridian detects a shift in stated risk tolerance across multiple journal entries → Apollo flags it for you and notes it in the Mind Vault

Rule-based triggers fire first. AI-generated inferences layer on top. Confirmation is always required before Apollo acts on an inference.

**Success feels like:** An attentive presence that notices things before you do — and connects dots across systems you'd never have checked simultaneously.

---

### Phase 5a: The Mirror

**Goal: Apollo becomes a digital twin — an AI version of you.**

This is the first endgame. By Phase 5a, Apollo has years of your decisions, reasoning, patterns, beliefs, financial behavior, and journal entries. It doesn't just know your data. It knows *you*.

**Capabilities:**

- **Answers *as* you.** Ask it what you would think about a decision, and it reasons in your voice using your actual past reasoning.
- **Thinks like you.** Its recommendations are grounded in your own articulated mental models, not generic advice.
- **Acts autonomously** in domains where you've explicitly granted permission — never beyond.
- **Simulates outcomes** against your real goals: "If you save $200 more per month, you'll hit your vacation goal by July — based on how you've actually been spending."
- **Advises from your own wisdom** — surfaces relevant past decisions and their outcomes before you make a new one.

Apollo never becomes fully autonomous without your explicit trust grant. Autonomy is earned domain by domain, proved by track record.

**The Mirror is transparent:** Apollo always shows its reasoning — "I'm suggesting this because on three similar occasions you chose X, and your journal on those days cited Y."

**Success feels like:** A trusted advisor that knows you better than you know yourself — because it's built entirely from you.

---

### Phase 5b: The Hub

**Goal: Apollo becomes your CEO. You remain the board.**

This phase is built entirely on top of a working Mirror. Do not attempt it until 5a is running smoothly.

**Capabilities:**

- Apollo runs the day-to-day operations of your systems and, eventually, your broader work
- You can spin up specialized sub-agents on demand by describing what you want in natural language: *"I need an agent that watches my email for invoices and logs them to Black Book."* Apollo generates the agent, gives it the right tools, and sets it running. You approve it. It works in the background until you retire it.
- Agent permissions follow the same trust model as individual actions — scoped, logged, revokable
- The session approval model expands: entire agent classes can be permanently allowed or permanently blocked

**The board-CEO model:**

| Role      | Who        | Responsibility                                      |
|-----------|------------|-----------------------------------------------------|
| **Board** | You        | Strategic decisions, trust grants, final approval   |
| **CEO**   | Apollo     | Day-to-day execution, delegation, system management |
| **Staff** | Sub-agents | Scoped tasks, background work, one domain each      |

Apollo never acts outside the permissions you've explicitly granted. Every agent it spawns is logged, auditable, and terminable.

**Success feels like:** You speak the intent once. Apollo figures out how to execute it and delegates accordingly. You only see what requires your decision.

---

## V. Delivery Channels

Apollo is not tied to a single interface. The same brain is accessible from wherever you are.

| Channel              | Phase Available | Notes                                                        |
|----------------------|-----------------|--------------------------------------------------------------|
| **Reflex Web UI**    | Phase 1         | Primary desktop interface; dark, minimal chat                |
| **Voice Input**      | Phase 1         | Whisper (faster-whisper tiny model); offline, on-device      |
| **WhatsApp Bridge**  | Phase 2         | Message your Apollo number from anywhere; no dedicated app needed; uses open-source bridge (whatsapp-web.js or equivalent) |
| **Daily Brief Push** | Phase 3         | Scheduled delivery; spoken or notification; no input needed  |
| **Mobile App**       | Future          | Dedicated app wrapping the same API; longer-term goal        |

The architecture is channel-agnostic from the start. Every input — typed, spoken, or messaged — hits the same `/chat` endpoint and goes through the same brain. Adding a new channel never requires changing the core.

---

## VI. Integration Architecture

### Current State (What Exists Today)

| System        | Status                                        | Apollo Integration Path                                          |
|---------------|-----------------------------------------------|------------------------------------------------------------------|
| **Black Book**| Live Reflex app, Neon PostgreSQL              | Read + write via shared DB or API; triggers cross-system alerts  |
| **Meridian**  | Codebase embedded inside Black Book           | Read vault (markdown); trigger script; write to daily notes; receives triggers from Apollo |
| **Olympus**   | Isolated; shares Neon DB with Black Book      | Read-only via Apex-exported JSON status file                     |

### Apollo's Own Components

- **Apollo App:** Separate application (web + WhatsApp + voice) with its own UI and LLM logic
- **Apollo Mind Vault:** Its own Obsidian vault — linked to Meridian's, owned by Apollo. Contains distilled self-knowledge, mental models, decision frameworks
- **Apollo Memory DB:** Local SQLite database for conversation history, learned patterns, decision logs, and session approval rules
- **Apollo Brain:** Anthropic Claude API with function-calling to all connected systems
- **Apollo Search Index:** Local ChromaDB vector database; search indexes over all vaults and databases
- **Daily Brief Agent:** Scheduled process; runs on a timer; no user input required

### How Apollo Talks to Each System

**Black Book**
- Reads via direct Postgres connection to the shared Neon DB
- Writes via the same connection (add transaction, update category)
- Triggers cross-system responses when spending anomalies are detected
- No changes to Black Book required

**Meridian**
- Reads by scanning the Obsidian vault folder (markdown files)
- Writes by appending to daily notes or creating new notes
- Triggers the Meridian question-generation script
- Receives trigger requests from Apollo (e.g., "add this question to tomorrow's cycle")
- No changes to Obsidian required

**Olympus / Apex**
- Reads from an exported status file (JSON) that Apex publishes on a schedule
- No writes, ever — Olympus remains isolated and Apex controls its own trades
- Apex can push alerts to Apollo (drawdown thresholds, position changes) via the same status file

---

## VII. The Feedback Loop Architecture

This is what separates Apollo from a simple integration layer. The three systems are not isolated. Events in one system ripple through Apollo to the others.

```
Black Book ──────────────────────► Apollo ◄──────────────── Olympus / Apex
  │  Spending anomaly detected         │  Drawdown > threshold reported
  │                                    │
  ▼                                    ▼
Apollo detects → notifies you    Apollo notifies you
Apollo queues Meridian trigger   Apollo queues Meridian trigger
  │                                    │
  └──────────────► Meridian ◄──────────┘
                   Next question cycle includes
                   the triggered reflection prompt
```

**Defined triggers (Phase 4):**

| Event                                  | Source System  | Apollo Action                                          |
|----------------------------------------|----------------|--------------------------------------------------------|
| Spending in any category > 2x average  | Black Book     | Notify user; queue Meridian reflection prompt          |
| Olympus drawdown > user-defined %      | Olympus / Apex | Notify user immediately; queue Meridian journal prompt |
| Meridian detects risk-tolerance shift  | Meridian       | Flag in Mind Vault; surface to user for confirmation   |
| No journal entry for 3+ days           | Meridian       | Apollo prompts user gently                             |
| No expense logged for 48+ hours        | Black Book     | Apollo asks if logging has fallen behind               |

All triggers are configurable. None fire autonomously until Phase 4 is active and you've opted in.

---

## VIII. Data Flow Examples

**Example 1: Morning briefing (Phase 3)**

1. 7:00am — Daily Brief Agent fires automatically
2. Apollo reads Olympus status.json → PnL, open positions from Apex
3. Apollo queries Black Book → yesterday's spending summary
4. Apollo scans Meridian → any open questions from last cycle
5. Apollo: "Olympus is up 0.8% today, 4 positions open. You spent $67 yesterday, mostly food. Meridian has 2 unanswered questions from Tuesday. Nothing urgent."

**Example 2: Logging a decision**

1. You: "Decision: I'm not increasing my 401k contribution this quarter because I want to keep cash available for Olympus to go live."
2. Apollo writes to Apollo Memory DB (decision log) and appends to today's Meridian note
3. Apollo: "Logged. Decision: hold 401k contribution. Reason: cash reserve for Olympus live transition."

**Example 3: Cross-system trigger (Phase 4)**

1. Black Book detects dining spend is 3x weekly average on Wednesday
2. Apollo flags it: "Your dining spend this week is already three times your average. Want to note why, or should I add a reflection prompt to tomorrow's Meridian cycle?"
3. You: "Add it to Meridian."
4. Apollo appends a custom question to tomorrow's journal cycle: "You spent significantly more on dining this week — what was driving that?"

**Example 4: Cross-system query (Phase 3)**

1. You: "On the weeks Olympus had a drawdown over 3%, how did my journaling change?"
2. Apollo queries Olympus status history → finds 3 such weeks
3. Apollo scans Meridian vault for those date ranges
4. Apollo: "In those 3 weeks, your journal entries were notably shorter and you mentioned stress twice. You also spent 28% more on dining out."

**Example 5: The Mirror answering as you (Phase 5a)**

1. You: "Should I start taking on freelance clients to increase income?"
2. Apollo retrieves: your stated goals from Meridian, current Olympus performance, spending patterns from Black Book, relevant past decision log entries
3. Apollo: "Based on your own reasoning from March, you said your priority is compounding Olympus — not adding income streams that fragment focus. Your cash position has improved 18% since then. The question you'd probably ask yourself is: does this distract from Olympus going live?"

**Example 6: Spinning up a sub-agent (Phase 5b)**

1. You: "I need something that watches for large transactions in Black Book and asks me to categorize them if they're uncategorized."
2. Apollo: "I can set that up. It'll check Black Book twice a day for transactions over $50 with no category and message you via WhatsApp to categorize them. Want to allow this permanently?"
3. You: "Yes."
4. Apollo creates the agent, logs it, and it begins running in the background.

---

## IX. What Done Looks Like at Each Phase

| Phase                    | You Know It Works When                                                                    |
|--------------------------|-------------------------------------------------------------------------------------------|
| **Phase 1 — Bridge**     | "What's Olympus doing?" returns real data. "Run Meridian" triggers the script.            |
| **Phase 2 — Recording**  | You say an expense in natural language and it appears in Black Book within seconds. WhatsApp works as an input channel. |
| **Phase 3 — Oracle**     | You ask a cross-system question and get an answer with sources. The daily brief runs at 7am without you asking. |
| **Phase 4 — Chronicler** | Apollo notices something before you do and asks about it. An Olympus drawdown triggers a Meridian question the next morning. |
| **Phase 5a — Mirror**    | You ask "what would I do here?" and Apollo reasons in your voice using your actual past data. |
| **Phase 5b — Hub**       | You describe a background task in plain language and Apollo runs it as a persistent agent.  |

---

## X. What This Plan Does Not Include

- Technical stack choices (Python, Reflex, vector DB selection, etc.) — those are implementation details covered in the Build Plan
- Timelines — your pace is your own; a phase could take a weekend or a month
- Cost estimates — depends on API usage and local vs. cloud LLM choices
- Hardware ambitions (ambient microphones, projector interfaces) — valid long-term directions but no architectural decisions hinge on them yet

---

## XI. The Final Picture

When all phases are complete, you will have:

- A single point of entry for all personal knowledge, financial tracking, and trading oversight
- A private AI that never forgets and never shares
- All your existing tools still running — now enhanced, unified, and triggering each other
- A morning briefing that arrives automatically, every day, without being asked
- A voice in your WhatsApp that executes commands from anywhere
- The ability to talk to your own history as naturally as you'd talk to yourself
- A system that grows into a mirror of how you think — built from your actual decisions, not someone else's framework
- And eventually, a CEO that runs your systems while you make the calls that only you can make

You are not building software. You are building an extension — and eventually a reflection — of your own mind.

---

*End of Master Plan — Revision 2*
*Build one phase at a time. The Bridge (Phase 1) is the gate. Nothing else opens until it works.*
