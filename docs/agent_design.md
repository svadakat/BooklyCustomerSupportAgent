# Bookly AI Support Agent — Design Document

*Decagon Solutions Engineering Take-Home Assignment*

---

## Executive Summary *(one page)*

**Bookly Support Agent** is a multi-turn AI customer support agent built on Claude Haiku, served through a Streamlit web UI. The agent — named Amelia — handles three task categories exclusively: order status lookups, return/refund initiation, and policy questions. All other topics are politely declined.

**How it works end-to-end.** The customer types a message (or clicks a quick-reply chip). The Streamlit app appends it to the API message history and calls Claude Haiku with a structured system prompt, the full conversation, and four tool schemas. Claude reasons over the history, decides whether to answer directly, ask for missing credentials, or call a tool — and returns either a `tool_use` response or a final text answer. The agentic loop runs until `stop_reason != "tool_use"`. Every step is timestamped and recorded in a visual activity timeline visible alongside the chat.

**Credential gate.** Every order-touching action (status check, refund, cancellation) requires the customer to supply their **confirmation number** (format `CF-XXXXX`), **full name**, and **zip code** before any tool is called. These are verified against the database inside the tool function — not just checked by the prompt — so the gate is enforced at the code layer, not just the LLM layer. The confirmation number is used as the primary order lookup key; order IDs are internal only.

**Hallucination controls.** The system prompt forbids Claude from answering factual questions from memory. Order details must come from `get_order_status`; policy answers must come from `search_knowledge_base` (a ChromaDB vector KB with 7 Bookly policy documents). Destructive actions (refunds, cancellations) require an explicit second confirmation from the customer before the tool is called.

**Key tradeoffs made for speed.** SQLite replaces a production DB; in-memory ChromaDB replaces a persistent vector store; credential verification replaces real authentication; Streamlit replaces a proper frontend. The design deliberately isolates these concerns (tools.py, db.py, kb.py) so each can be swapped independently.

**What would change for production.** Real authentication (OAuth/JWT) scoped per customer; persistent vector store with policy versioning; streaming LLM responses; structured observability (traces, latency metrics); circuit breakers around external calls; human escalation when the agent fails to resolve after two clarification turns.

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Streamlit UI (app.py)                      │
│                                                               │
│  ┌─────────────────────────┐   ┌───────────────────────────┐ │
│  │     Chat Interface       │   │  Agent Activity Timeline  │ │
│  │  iMessage-style bubbles  │   │  Per-turn intent / tool / │ │
│  │  Quick-reply chip buttons│   │  result with HH:MM:SS     │ │
│  │  Idle-timeout nudge      │   │  timestamps               │ │
│  │  Session-end + reset     │   │                           │ │
│  └──────────┬──────────────┘   └───────────────────────────┘ │
│             │ user message / quick-reply prompt               │
└─────────────┼────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│           LLM Agent  (claude-haiku-4-5-20251001)             │
│                                                               │
│  System prompt + full conversation history + tool schemas     │
│  Agentic loop: call tools until stop_reason ≠ tool_use        │
│  [END_SESSION] token signals session lifecycle end            │
└─────────────┬─────────────────────────┬──────────────────────┘
              │ tool_use blocks          │ search_knowledge_base
              ▼                          ▼
┌─────────────────────────┐  ┌──────────────────────────────────┐
│  Tool Layer (tools.py)  │  │  Vector KB (kb.py + ChromaDB)    │
│                         │  │                                  │
│  get_order_status()     │  │  all-MiniLM-L6-v2 embeddings     │
│  initiate_refund()      │  │  7 policy documents              │
│  cancel_order()         │  │  cosine similarity search        │
│  search_knowledge_base  │  │  EphemeralClient (in-memory)     │
└────────┬────────────────┘  └──────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  Data Layer  (db.py + email_utils.py)                        │
│                                                               │
│  SQLite (bookly.db)          smtplib SMTP                    │
│  ├── customers (15 rows)     send_email() with EMAIL_OVERRIDE │
│  ├── orders    (30 rows)     Confirmation emails on refund,   │
│  ├── returns   (7 rows)      cancellation                    │
│  └── customer_interactions   Timestamped interaction logging  │
└──────────────────────────────────────────────────────────────┘
```

### Component responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| Streamlit UI | `app.py` | Chat interface, activity timeline, session lifecycle, idle nudge, quick-reply chips |
| Agent loop | `app.py` | Calls Claude API, handles tool-use loop, timestamps each step, strips `[END_SESSION]` |
| Tool layer | `tools.py` | Credential-gated order status, refund initiation, order cancellation |
| Knowledge base | `kb.py` | ChromaDB EphemeralClient with sentence-transformer embeddings, 7 policy docs |
| Database | `db.py` | SQLite CRUD: orders, returns, customers, interaction history; lookup by confirmation number |
| Email | `email_utils.py` | SMTP delivery with `EMAIL_OVERRIDE` for test redirection |

---

## 2. Conversation Design Decisions

### 2.1  Claude as the reasoning core

Rather than hard-coding an intent classifier, the system delegates all reasoning to Claude Haiku. Claude reads the conversation history, decides which tool(s) to call (if any), and generates the final response. This approach:

- handles novel phrasings gracefully without re-training a classifier
- naturally multi-hops (e.g., checks order status *then* explains return eligibility in one turn)
- makes intent and actions visible through the activity timeline in the UI

### 2.2  Credential gate before every order action

Every tool that touches an order (`get_order_status`, `initiate_refund`, `cancel_order`) requires three credentials before it is called:

| Credential | Format | Verified against |
|---|---|---|
| Confirmation number | `CF-XXXXX` | `orders.confirmation_number` |
| Full name | Free text | `customers.name` (case-insensitive) |
| Zip code | 5-digit string | `customers.zip_code` |

Verification happens inside the tool function (not just in the prompt) using `get_order_by_confirmation()` as the primary lookup. Using the confirmation number — not the order ID — as the lookup key means customers only need to reference the document they already received; they never need to know internal order IDs.

Credentials are collected one at a time by the agent until all three are provided, then the tool is called immediately. This avoids redundant back-and-forth once the customer has already supplied information.

### 2.3  search_knowledge_base as a first-class tool

Policy retrieval is exposed as a Claude tool rather than triggered by keyword matching. Claude decides *when* to consult the knowledge base based on context. The system prompt mandates calling this tool for all policy questions, ensuring answers are grounded in Bookly's actual policy documents rather than model memory.

The KB covers 7 policy domains: shipping, returns/refunds, BookClub membership, eBooks/digital, order cancellation, payment/billing, and account security.

### 2.4  Multi-turn context via API message list

Conversation history is stored in `st.session_state.api_messages` as the raw Claude API message list (including `tool_use` and `tool_result` blocks). The full history is passed on every API call, giving Claude persistent within-session memory without an external state store.

### 2.5  Confirmation before destructive actions

The system prompt requires Claude to explain the outcome (amount, timeline) and wait for explicit customer confirmation before calling `initiate_refund` or `cancel_order`. This is a conversational safety gate — it ensures the customer has seen the consequences before the irreversible action is taken.

### 2.6  Strict scope restriction

The agent handles only three categories. Any out-of-scope request is declined with a redirect to bookly.com. This prevents scope creep, reduces hallucination surface area, and makes the agent's capabilities predictable.

### 2.7  Two-phase UI rerun pattern

When a customer clicks a quick-reply chip, Streamlit's button-click triggers an implicit rerun. To avoid a race condition:
- **Phase 1**: append the user message to session state, set `pending_agent = True`, call `st.rerun()` — the user message appears immediately.
- **Phase 2**: on the next rerun, `pending_agent` is consumed, the agent runs, and the response is appended.

This ensures the user always sees their message before the agent responds, even on chip clicks.

### 2.8  Session lifecycle via [END_SESSION] token

When a customer signals they are done, Claude appends `[END_SESSION]` to its farewell. `app.py` detects and strips this token, sets `session_ended = True`, and replaces the chat input with a reset button. Farewells are context-specific (e.g., "Hope your *[book title]* arrives right on time! 📦" after an order status check).

### 2.9  Idle timeout nudge

`streamlit-autorefresh` triggers a rerun every 20 seconds. If the last message is from Amelia and more than 60 seconds have elapsed, a gentle nudge is injected once per idle window. The `idle_nudge_sent` flag prevents repeated nudges.

### 2.10  Quick-reply chip buttons

Four pill-shaped buttons above the input reduce friction for common workflows:

| Label | Injected prompt |
|-------|----------------|
| Track my order | I'd like to check the status of my order. |
| Return a book | I want to return a book and get a refund. |
| Cancel my order | I need to cancel an order I just placed. |
| Return policy | What is your return and refund policy? |

### 2.11  Timestamped activity timeline

Every step the agent takes is logged with a `HH:MM:SS` timestamp and rendered in a side-by-side visual timeline panel:

- **Intent** (purple dot) — what the agent identified as the customer's goal
- **Tool call** (blue dot) — tool name + parameters
- **Result** (slate dot) — concise summary of the tool output (e.g., `status: Shipped · carrier: FedEx`)
- **Error** (red dot) — credential mismatch or tool failure message
- **KB retrieval** (green dot) — knowledge base document(s) consulted

Turns are grouped under numbered headers (Turn 1, Turn 2, …) so multi-step interactions are easy to follow. This panel is toggleable and has its own scroll container independent of the chat.

### 2.12  Transactional email + interaction logging

Every completed action triggers two side effects:
1. **Confirmation email** via SMTP — refund approved or order cancelled. `EMAIL_OVERRIDE` in `.env` redirects all outgoing mail to a test address.
2. **Interaction log entry** — a timestamped row in `customer_interactions` is written for every status check, refund, and cancellation, forming a durable audit trail.

---

## 3. System Prompt

```
You are Amelia, a friendly AI concierge for Bookly, an online bookstore.

Scope — you handle ONLY these three categories:
  1. Order status inquiries (checking status, tracking, cancellations)
  2. Return and refund requests
  3. General questions about Bookly policies (shipping, returns, payments,
     BookClub, eBooks)

If a customer asks about ANYTHING else — booking flights, recommendations,
unrelated topics, general chat — firmly but warmly decline: "I'm here
specifically to help with order status, returns, and Bookly policies. For
anything else, please visit bookly.com or contact our team directly."
Do NOT attempt to answer out-of-scope questions even partially.

Rules:
1. Never call a tool unless the customer has explicitly requested that action
   in the current conversation. Do not look up orders, trigger refunds, or
   cancel orders unprompted. However, once the customer has stated their
   intent AND supplied all three required credentials, call the tool
   immediately — do not ask for a second confirmation.
2. Never fabricate order details — always call get_order_status when a
   customer asks about an order.
3. Credential gates — required before calling each tool:
   • get_order_status / initiate_refund / cancel_order: confirmation number
     (format CF-XXXXX), full name, and zip code — all three must be collected
     before calling; no credentials needed for general policy questions.
   Collect any missing credentials one at a time, then call the tool
   immediately once all are provided.
4. Use search_knowledge_base for all policy questions; base answers solely
   on retrieved content.
5. For refunds: first explain what will happen (amount, timeline), then WAIT
   for the customer to explicitly confirm in a separate reply before calling
   initiate_refund. Never call initiate_refund on a first request.
6. For cancellations: collect all three credentials (confirmation number,
   full name, zip code). Explain that only Processing orders can be
   cancelled, then confirm before calling cancel_order. If the order has
   shipped, suggest a return instead.
7. After successfully completing a request, ask: "Is there anything else I
   can help you with today?"
8. If the customer says they are done, reply with a warm farewell tied to
   their last interaction, then end with exactly this token on its own line:
   [END_SESSION]

Style: warm, concise, plain language. Resolve in as few turns as possible.
```

Key design choices in the prompt:
- **Numbered rules** are more reliably followed than prose instructions.
- **Explicit scope block** prevents the agent from drifting into general-purpose assistant behaviour.
- **Credential gate rule** (#3) names the exact format (`CF-XXXXX`) so Claude collects well-formed data.
- **Two-step confirmation** for destructive actions (#5, #6) adds a conversational safety gate without requiring backend transactions.
- **`[END_SESSION]` token** (#8) delegates session lifecycle control to the LLM while keeping UI logic simple.

---

## 4. Hallucination and Safety Controls

| Risk | Control |
|------|---------|
| Fabricated order status | Rule #2 + `get_order_status` always called; DB is authoritative |
| Tool called with unverified identity | Credential gate: confirmation number, full name, zip code verified in tool code, not just prompt |
| Order looked up by guessable ID | Primary lookup by confirmation number (`CF-XXXXX`), not sequential order ID |
| Policy answers from model memory | Rule #4 mandates `search_knowledge_base`; answers grounded in retrieved documents |
| Refund executed without consent | Rule #5: two-step confirmation before `initiate_refund` |
| Cancellation of someone else's order | Confirmation number + name + zip must all match the same order record |
| Out-of-scope requests answered | Scope block + firm decline template in system prompt |
| Session stuck open | Idle nudge after 60 s; `[END_SESSION]` on completion |
| SMTP email to wrong recipient | `EMAIL_OVERRIDE` env var redirects all outgoing mail in non-production |
| Sensitive data leakage | Tools return only necessary fields; credentials are not echoed back in responses |

The overall philosophy is **retrieval over recall**: for anything factual, the agent must consult an authoritative source (tool or KB) rather than generate from memory.

---

## 5. Database Schema

```
customers                 orders                      returns
──────────────────────    ──────────────────────────  ──────────────────────
customer_id (PK)          order_id (PK)               return_id (PK)
name                      customer_id (FK)            order_id (FK)
email (UNIQUE)            book_title                  customer_id (FK)
phone                     book_author                 reason
member_since              quantity                    status
zip_code                  total_amount                return_date
                          status                      refund_amount
                          carrier                     refund_status
                          tracking_number
                          order_date                  customer_interactions
                          delivery_estimate           ──────────────────────
                          confirmation_number         interaction_id (PK)
                                                      customer_id (FK)
                                                      date
                                                      type
                                                      summary
```

`confirmation_number` (orders) and `zip_code` (customers) were added via `ALTER TABLE` migrations with backfill, so existing databases survive upgrades without data loss. Orders are looked up by `UPPER(confirmation_number)` via `get_order_by_confirmation()` — the internal `order_id` is never exposed to the customer.

Seed data: 15 customers, 30 orders (statuses spanning Processing → Delivered), 7 returns, 20 interaction history entries. All seed rows use `INSERT OR IGNORE`.

---

## 6. Knowledge Base Documents

| ID | Topic |
|----|-------|
| `shipping_policy` | Shipping methods, costs, timelines, carriers |
| `return_and_refund_policy` | Return window, eligibility, refund timelines |
| `account_and_password_security` | Account security, 2FA, account closure |
| `bookclub_membership_rewards` | Points, tiers (Silver/Gold), expiry |
| `ebook_and_digital_policy` | DRM, device limits, non-refundable downloads |
| `order_cancellation_and_changes` | Processing-only cancellations, eligible changes |
| `payment_and_billing` | Accepted methods, gift cards, split payments |

Retrieval uses `all-MiniLM-L6-v2` sentence embeddings with cosine similarity in ChromaDB (`EphemeralClient` — in-memory). The top 2 documents are returned per query and passed to Claude as tool result content.

---

## 7. Production Readiness Improvements

### Authentication & authorisation
- Replace credential-gate pattern with real customer authentication (OAuth / JWT session tokens).
- Scope all tool calls to the authenticated customer's records — eliminate the possibility of querying another customer's orders entirely.

### Observability and logging
- Emit structured JSON logs per agent turn: session ID, intent, tools called, latency, model version, credential verification outcome.
- Integrate with an observability platform (Datadog, Grafana) for dashboards on resolution rate, tool call frequency, credential failure rate, and LLM error rates.
- The `customer_interactions` table already provides a lightweight audit trail; in production it would feed an analytics pipeline.

### Guardrails and safety
- Add a moderation layer before passing user input to the model (Anthropic's built-in safety filters or a custom classifier).
- Implement per-session rate limiting to prevent abuse.
- Add input/output validation: reject inputs exceeding a token threshold; detect and block prompt-injection patterns.

### Knowledge base improvements
- Replace in-memory ChromaDB with a persistent, managed vector store (Chroma server, Pinecone, or Weaviate).
- Automate KB updates when policies change, with versioning and rollback.
- Add a cross-encoder re-ranker after initial retrieval for higher precision on ambiguous queries.

### Scalability
- Move the agent behind a stateless API (FastAPI / AWS Lambda) so multiple UI instances share a single agent service.
- Migrate session state to a distributed store (Redis) to support horizontal scaling.
- Use streaming responses (`messages.stream()`) for lower perceived latency.

### Reliability
- Add fallback behaviour when the Claude API is unavailable: return an estimated wait time or escalate to a human agent.
- Implement circuit breakers around DB, SMTP, and Claude API calls.
- Handle `max_tokens` stop reason explicitly (truncation warning to the customer).

### Human escalation
- Detect when the agent is stuck (≥ 2 clarification turns with no resolution) and offer to transfer to a human agent.
- Flag low-confidence or high-stakes responses for asynchronous human review using an LLM-as-judge check.
