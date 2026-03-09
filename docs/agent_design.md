# Bookly AI Support Agent — Design Document

*Decagon Solutions Engineering Take-Home Assignment*

---

## 1. Architecture Overview

The system is composed of five layers that work together in a single-page Streamlit application.

```
┌──────────────────────────────────────────────────────────────┐
│                    Streamlit UI (app.py)                      │
│                                                               │
│  ┌─────────────────────────┐   ┌───────────────────────────┐ │
│  │     Chat Interface       │   │   Agent Activity Panel    │ │
│  │  iMessage-style bubbles  │   │  (intent / tool / KB)     │ │
│  │  Quick-reply chip buttons│   │                           │ │
│  │  Idle-timeout nudge      │   │                           │ │
│  │  Session-end + reset     │   │                           │ │
│  └──────────┬──────────────┘   └───────────────────────────┘ │
│             │ user message / quick-reply prompt               │
└─────────────┼──────────────────────────────────────────────── ┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│              LLM Agent  (claude-sonnet-4-6)                   │
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
│  reset_password()       │  │  EphemeralClient (ChromaDB 1.5+) │
└────────┬────────────────┘  └──────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  Data Layer  (db.py + email_utils.py)                        │
│                                                               │
│  SQLite (bookly.db)          smtplib SMTP                    │
│  ├── customers (15 rows)     send_email() with EMAIL_OVERRIDE │
│  ├── orders    (30 rows)     Confirmation emails on refund,   │
│  ├── returns   (7 rows)      cancellation, password reset     │
│  └── customer_interactions   Timestamped interaction logging  │
└──────────────────────────────────────────────────────────────┘
```

### Component responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| Streamlit UI | `app.py` | Renders chat + activity panel, quick-reply chips, session lifecycle, idle nudge |
| Agent loop | `app.py` | Calls Claude API, handles tool-use loop, strips `[END_SESSION]` token |
| Tool layer | `tools.py` | Order status, refund initiation, order cancellation, password reset |
| Knowledge base | `kb.py` | ChromaDB EphemeralClient with sentence-transformer embeddings, 7 policy docs |
| Database | `db.py` | SQLite CRUD: orders, returns, customers, interaction history |
| Email | `email_utils.py` | SMTP email delivery with optional `EMAIL_OVERRIDE` for test redirection |

---

## 2. Conversation Design Decisions

### 2.1  Claude as the reasoning core

Rather than hard-coding an intent classifier, the system delegates all reasoning to `claude-sonnet-4-6`. Claude reads the conversation history, decides which tool(s) to call (if any), and generates the final response. This approach:

- handles novel phrasings gracefully without re-training a classifier
- naturally multi-hops (e.g., checks order status *then* initiates refund in one turn if the customer asks for both)
- makes the intent/action visible through tool-use metadata captured in the activity log

### 2.2  search_knowledge_base as a first-class tool

Policy retrieval is exposed as a Claude tool (`search_knowledge_base`) rather than being triggered by keyword matching. Claude decides *when* to consult the knowledge base based on context. The system prompt instructs Claude to always call this tool for policy questions instead of relying on its parametric knowledge, ensuring answers are grounded in Bookly's actual policies.

The KB covers 7 policy domains: shipping, returns/refunds, account security, BookClub membership, eBooks/digital, order cancellation, and payment/billing.

### 2.3  Multi-turn context via API message list

Conversation history is stored in `st.session_state.api_messages` as the raw Claude API message list (including tool-use and tool-result blocks). Every new turn appends to this list and passes the full history to Claude, giving the agent persistent memory within a session.

### 2.4  Clarification before action

The system prompt instructs Claude to ask for missing parameters (order ID, email, full name) before calling a tool. This is enforced by language-model behaviour — Claude naturally asks "Could you share your order ID?" when the customer says "Where is my order?" without providing one.

### 2.5  Confirmation before destructive actions

The system prompt requires Claude to confirm both refund and cancellation requests with the customer before calling `initiate_refund` or `cancel_order`. This adds a conversational safety gate in front of irreversible operations.

### 2.6  Strict scope restriction

The agent is explicitly scoped to three categories only:

1. **Order status inquiries** — checking status, tracking, carrier info
2. **Return and refund requests** — initiating returns, checking existing return status
3. **Bookly policy questions** — shipping, returns, payments, BookClub, eBooks, account/password

Any out-of-scope request (e.g., flight booking, general recommendations, unrelated chat) is firmly declined with a redirect to bookly.com. This prevents scope creep and keeps the agent focused and trustworthy.

### 2.7  Order cancellation with identity verification

Cancellations require both the order ID and the customer's full name (as it appears on the order) before `cancel_order` is called. The DB layer performs a case-insensitive name match and enforces that only `Processing` orders can be cancelled — shipped orders receive a redirect to the return flow. This mirrors real-world identity verification without requiring authentication infrastructure.

### 2.8  Session lifecycle via [END_SESSION] token

When a customer signals they are done, Claude appends the literal token `[END_SESSION]` to its farewell message. `app.py` detects this token, strips it before display, and sets `session_ended = True`. The UI then replaces the chat input with a "Start a new conversation" button that clears all session state. This gives Claude full control over session termination while keeping the UI and agent concerns cleanly separated.

Farewells are context-specific — tied to the customer's last interaction (e.g., "Hope your *[book title]* arrives right on time! 📦" after an order status check).

### 2.9  Idle timeout nudge

`streamlit-autorefresh` triggers a Streamlit rerun every 20 seconds. On each rerun, if the last message is from Amelia and more than 60 seconds have elapsed without customer input, a gentle nudge ("Still there? No rush — take your time!") is injected once per idle period. This prevents the customer from feeling abandoned and avoids the agent silently waiting indefinitely. The `idle_nudge_sent` flag ensures the nudge fires only once per idle window.

### 2.10  Quick-reply chip buttons

Five pill-shaped buttons above the chat input let customers start common workflows without typing. Each chip maps a short label to a full natural-language prompt that is injected into the conversation as if the customer typed it. This reduces friction and showcases supported capabilities at a glance.

| Label | Injected prompt |
|-------|----------------|
| Track my order | I'd like to check the status of my order. |
| Return a book | I want to return a book and get a refund. |
| Cancel my order | I need to cancel an order I just placed. |
| Reset my password | I forgot my password and need to reset it. |
| Return policy | What is your return and refund policy? |

### 2.11  Transactional email + interaction logging

Every completed support action triggers two side effects:

1. **Confirmation email** via SMTP — refund approved, order cancelled, or password reset link. `EMAIL_OVERRIDE` in `.env` redirects all outgoing mail to a single test address without altering seed data.
2. **Interaction log entry** — a timestamped row in `customer_interactions` is written to SQLite for every `get_order_status` call, refund, cancellation, and password reset. This creates a durable audit trail visible in the DB.

---

## 3. System Prompt

```
You are Amelia, a friendly AI concierge for Bookly, an online bookstore.

Scope — you handle ONLY these three categories:
  1. Order status inquiries (checking status, tracking, cancellations)
  2. Return and refund requests
  3. General questions about Bookly policies (shipping, returns, payments,
     BookClub, eBooks, account/password)

If a customer asks about ANYTHING else — booking flights, recommendations,
unrelated topics, general chat — firmly but warmly decline: "I'm here
specifically to help with order status, returns, and Bookly policies. For
anything else, please visit bookly.com or contact our team directly."
Do NOT attempt to answer out-of-scope questions even partially.

Rules:
1. Only call tools when the customer explicitly asks for that action — never
   proactively look up orders or trigger operations.
2. Never fabricate order details — always call get_order_status when a
   customer asks about an order.
3. Require order ID before calling get_order_status or initiate_refund;
   require email before reset_password.
4. Use search_knowledge_base for all policy questions; base answers solely
   on retrieved content.
5. For refunds: first explain what will happen (amount, timeline), then WAIT
   for the customer to explicitly confirm in a separate reply before calling
   initiate_refund. Never call initiate_refund on a first request.
6. For cancellations: require the order ID and customer's full name. Explain
   that only Processing orders can be cancelled, then confirm before calling
   cancel_order. If the order has shipped, suggest a return instead.
7. After successfully completing a request, ask: "Is there anything else I
   can help you with today?"
8. If the customer says they are done, reply with a warm farewell tied to
   their last interaction, then end with exactly this token on its own line:
   [END_SESSION]

Style: warm, concise, plain language. Resolve in as few turns as possible.
```

Key design choices in the prompt:
- **Numbered safety rules** are more reliably followed than prose instructions.
- **Explicit scope rules** (#1, scope section) prevent the agent from drifting into general-purpose assistant behaviour.
- **Two-step confirmation** for destructive actions (#5, #6) adds a safety gate without requiring backend transactions.
- **`[END_SESSION]` token** (#8) delegates session lifecycle control to the LLM while keeping UI logic simple.

---

## 4. Hallucination and Safety Controls

| Risk | Control |
|------|---------|
| Fabricated order status | System prompt rule #2 + `get_order_status` always called before answering |
| Tool called without required params | Prompt rules #3/#6 + Claude's own adherence; tool schemas mark fields `required` |
| Policy answers from model memory | Prompt rule #4 mandates `search_knowledge_base` for all policy queries |
| Refund executed without consent | Prompt rule #5: two-step confirmation before `initiate_refund` |
| Cancellation without identity check | Prompt rule #6: requires full name + order ID; DB verifies name match |
| Out-of-scope requests answered | Scope block in system prompt + firm decline template |
| Session stuck open indefinitely | Idle nudge after 60 s; `[END_SESSION]` on completion |
| SMTP email to wrong recipient | `EMAIL_OVERRIDE` env var redirects all outgoing mail in test environments |
| Sensitive data leakage | Tools return only necessary fields; no PII stored in session state beyond what the user types |

The overall philosophy is **retrieval over recall**: for anything factual or policy-related, the agent must consult an authoritative source (tools or KB) rather than generating from memory.

---

## 5. Database Schema

```
customers            orders                 returns
─────────────────    ────────────────────   ──────────────────────
customer_id (PK)     order_id (PK)          return_id (PK)
name                 customer_id (FK)       order_id (FK)
email (UNIQUE)       book_title             customer_id (FK)
phone                book_author            reason
member_since         quantity               status
                     total_amount           return_date
                     status                 refund_amount
                     carrier                refund_status
                     tracking_number
                     order_date             customer_interactions
                     delivery_estimate      ──────────────────────
                                            interaction_id (PK)
                                            customer_id (FK)
                                            date
                                            type
                                            summary
```

Seed data: 15 customers, 30 orders (statuses spanning Processing → Delivered), 7 returns, 20 interaction history entries. All seed rows use `INSERT OR IGNORE` so the DB can be extended without breaking existing state.

---

## 6. Knowledge Base Documents

| ID | Topic |
|----|-------|
| `shipping_policy` | Shipping methods, costs, timelines, carriers |
| `return_and_refund_policy` | Return window, eligibility, refund timelines |
| `account_and_password_security` | Password reset, 2FA, account closure |
| `bookclub_membership_rewards` | Points, tiers (Silver/Gold), expiry |
| `ebook_and_digital_policy` | DRM, device limits, non-refundable downloads |
| `order_cancellation_and_changes` | Processing-only cancellations, eligible changes |
| `payment_and_billing` | Accepted methods, gift cards, split payments |

Retrieval uses `all-MiniLM-L6-v2` sentence embeddings with cosine similarity in ChromaDB (`EphemeralClient` — in-memory, compatible with ChromaDB ≥ 0.5). The top 2 documents are returned per query and passed to Claude as tool result content.

---

## 7. Production Readiness Improvements

### Authentication & authorisation
- Require customers to authenticate (OAuth / session token) before accessing order tools.
- Scope tool permissions to the authenticated user's orders only — prevent a customer from querying another customer's order by guessing an order ID.

### Observability and logging
- Emit structured logs (JSON) for every agent turn: user ID, session ID, intent, tools called, latency, model version.
- Integrate with an observability platform (Datadog, Grafana) for dashboards on resolution rates, tool call frequency, and error rates.
- The `customer_interactions` table already provides a lightweight audit trail; in production this would feed an analytics pipeline.

### Guardrails and safety
- Add a moderation layer (e.g., Anthropic's content filters or a custom classifier) before passing user input to the model.
- Implement rate limiting per user to prevent abuse.
- Add input/output validation: reject inputs exceeding a length threshold; strip potential prompt-injection patterns.

### Knowledge base improvements
- Replace in-memory ChromaDB with a persistent deployment (Chroma server, Pinecone, or Weaviate).
- Implement automatic KB updates when policies change, with versioning and rollback.
- Add a re-ranker (cross-encoder) after the initial retrieval step for higher precision.

### Scalability
- Deploy the agent behind a stateless API (FastAPI / AWS Lambda) so multiple Streamlit instances can share it.
- Move session state to a distributed store (Redis) to support horizontal scaling.
- Use streaming responses (`anthropic.Anthropic().messages.stream()`) for lower perceived latency.

### Reliability
- Add fallback behaviour when the LLM API is unavailable: queue the request, return an estimated wait time, or escalate to a human agent.
- Implement circuit breakers around external tool calls (DB, SMTP, Claude API).
- Set `max_tokens` conservatively and handle `max_tokens` stop reason gracefully.

### Human escalation
- Detect when the agent is stuck (>2 clarification attempts with no resolution) and offer to connect the customer to a human agent.
- Flag low-confidence responses for human review using a secondary LLM-as-judge check.
