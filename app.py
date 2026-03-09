"""
app.py — Bookly AI Customer Support Agent
Run with: OS streamlit run app.py
"""

import html
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

import anthropic
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import db  # ensures DB is initialised on startup
from kb import search as kb_search
from tools import get_order_status, initiate_refund, cancel_order, reset_password

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Bookly Support",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Featured books
# ---------------------------------------------------------------------------

FEATURED_BOOKS = [
    {"title": "The Covenant of Water",              "author": "Abraham Verghese",                  "genre": "Fiction",    "isbn": "9780802162175", "bg": "#fff1f2", "accent": "#e11d48"},
    {"title": "Man's Search for Meaning",           "author": "Viktor Frankl",                     "genre": "Psychology", "isbn": "9780807014271", "bg": "#f0fdf4", "accent": "#16a34a"},
    {"title": "Thinking, Fast and Slow",            "author": "Daniel Kahneman",                   "genre": "Psychology", "isbn": "9780374533557", "bg": "#f0fdf4", "accent": "#15803d"},
    {"title": "The Beginning of Infinity",          "author": "David Deutsch",                     "genre": "Science",    "isbn": "9780143121350", "bg": "#eff6ff", "accent": "#2563eb"},
    {"title": "Meditations",                        "author": "Marcus Aurelius",                   "genre": "Philosophy", "isbn": "9780140449334", "bg": "#fefce8", "accent": "#ca8a04"},
    {"title": "Zero to One",                        "author": "Peter Thiel & Blake Masters",       "genre": "Business",   "isbn": "9780804139021", "bg": "#f8fafc", "accent": "#0f172a"},
    {"title": "Blitzscaling",                       "author": "Reid Hoffman & Chris Yeh",          "genre": "Business",   "isbn": "9781524761417", "bg": "#f8fafc", "accent": "#1e293b"},
    {"title": "The Innovator's Dilemma",            "author": "Clayton M. Christensen",            "genre": "Business",   "isbn": "9781633691780", "bg": "#f8fafc", "accent": "#334155"},
    {"title": "The Lean Startup",                   "author": "Eric Ries",                         "genre": "Business",   "isbn": "9780307887894", "bg": "#f8fafc", "accent": "#475569"},
    {"title": "The Score Takes Care of Itself",     "author": "Bill Walsh",                        "genre": "Leadership", "isbn": "9781591843412", "bg": "#fdf4ff", "accent": "#9333ea"},
    {"title": "Superintelligence",                  "author": "Nick Bostrom",                      "genre": "AI / Tech",  "isbn": "9780198739838", "bg": "#f5f3ff", "accent": "#7c3aed"},
    {"title": "Einstein: His Life and Universe",    "author": "Walter Isaacson",                   "genre": "Biography",  "isbn": "9780743264747", "bg": "#fdf2f8", "accent": "#db2777"},
    {"title": "Brave New World",                    "author": "Aldous Huxley",                     "genre": "Fiction",    "isbn": "9780060850524", "bg": "#fff7ed", "accent": "#ea580c"},
    {"title": "Secrets of Sand Hill Road",          "author": "Scott Kupor",                       "genre": "Business",   "isbn": "9781982106348", "bg": "#f0f9ff", "accent": "#0284c7"},
    {"title": "The Master Algorithm",               "author": "Pedro Domingos",                    "genre": "AI / Tech",  "isbn": "9780465065707", "bg": "#f5f3ff", "accent": "#6d28d9"},
    {"title": "Sapiens",                            "author": "Yuval Noah Harari",                 "genre": "History",    "isbn": "9780062316097", "bg": "#fff7ed", "accent": "#c2410c"},
    {"title": "The Second Machine Age",             "author": "Erik Brynjolfsson & Andrew McAfee", "genre": "Technology", "isbn": "9780393350647", "bg": "#f0fdfa", "accent": "#0f766e"},
]

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,300;0,400;1,300&family=Inter:wght@300;400;500;600&display=swap');

/* ── Global ──────────────────────────────────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

.stApp {
    background: #f0ece4;
    font-family: 'Inter', -apple-system, sans-serif;
}

/* Remove default block container padding */
.block-container {
    padding: 1.5rem 1.5rem 1rem !important;
    max-width: 100% !important;
}

/* ── Make first column the white card ────────────────────────────────────── */
[data-testid="stColumn"]:first-child > div:first-child {
    background: #ffffff;
    border-radius: 20px;
    border: 1px solid #e2dbd2;
    box-shadow: 0 2px 28px rgba(0,0,0,0.07);
    overflow: hidden;
}

/* Remove gap between stacked elements inside the card */
[data-testid="stColumn"]:first-child > div:first-child > div {
    gap: 0 !important;
}

/* ── Card: logo bar ──────────────────────────────────────────────────────── */
.card-logo {
    padding: 16px 20px 14px;
    border-bottom: 1px solid #f0ece4;
    display: flex;
    align-items: center;
    gap: 10px;
}
.card-logo-text {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.2rem;
    font-weight: 600;
    color: #1c1917;
    letter-spacing: -0.02em;
}
.card-logo-text span { color: #7c3aed; }
.card-logo-dot {
    width: 8px; height: 8px;
    background: #4ade80;
    border-radius: 50%;
    margin-left: auto;
}
.card-logo-status {
    font-size: 0.72rem;
    color: #78716c;
    margin-right: 4px;
}

/* ── Card: featured books ────────────────────────────────────────────────── */
.card-books {
    padding: 8px 16px 8px;
    border-bottom: 1px solid #f0ece4;
    background: #faf8f4;
}
.books-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}
.books-badge {
    font-size: 0.57rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #7c3aed;
    background: #f5f3ff;
    border: 1px solid #ddd6fe;
    padding: 2px 7px;
    border-radius: 3px;
}
.books-label {
    font-size: 0.76rem;
    font-weight: 500;
    color: #78716c;
}
.books-scroll {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 2px;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
}
.books-scroll::-webkit-scrollbar { display: none; }
.book-card {
    flex-shrink: 0;
    width: 90px;
    border-radius: 7px;
    border-left: 2px solid;
    border-top: 1px solid rgba(0,0,0,0.06);
    border-right: 1px solid rgba(0,0,0,0.06);
    border-bottom: 1px solid rgba(0,0,0,0.06);
    overflow: hidden;
    background: #fff;
    transition: transform 0.15s, box-shadow 0.15s;
    cursor: default;
}
.book-card:hover { transform: translateY(-2px); box-shadow: 0 4px 14px rgba(0,0,0,0.10); }
.book-cover { width: 100%; height: 90px; overflow: hidden; }
.book-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.book-meta { padding: 6px 7px 7px; }
.book-genre { font-size: 0.54rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 3px; }
.book-title { font-size: 0.68rem; font-weight: 600; color: #1c1917; line-height: 1.25;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

/* ── Card: chat area ─────────────────────────────────────────────────────── */
.chat-bg {
    background: #f7f5f2;
    padding: 14px 14px 0;
}

/* iMessage-style bubbles */
.bubble-row-user {
    display: flex;
    justify-content: flex-end;
    margin: 3px 0 3px 60px;
}
.bubble-row-amelia {
    display: flex;
    justify-content: flex-start;
    align-items: flex-end;
    gap: 8px;
    margin: 3px 60px 3px 0;
}
.bubble-avatar {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #1c1917;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Fraunces', serif;
    font-size: 0.75rem; font-weight: 600; color: #fff;
    flex-shrink: 0;
}
.bubble-user {
    background: #007aff;
    color: #ffffff;
    border-radius: 18px 18px 4px 18px;
    padding: 9px 14px;
    font-size: 0.88rem;
    line-height: 1.45;
    word-break: break-word;
    max-width: 100%;
}
.bubble-amelia {
    background: #ffffff;
    color: #1c1917;
    border-radius: 18px 18px 18px 4px;
    padding: 9px 14px;
    font-size: 0.88rem;
    line-height: 1.45;
    word-break: break-word;
    max-width: 100%;
    border: 1px solid #e7e0d8;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.bubble-amelia strong { font-weight: 600; }
.bubble-amelia em { font-style: italic; }
.bubble-amelia code { background: #f1f0ee; border-radius: 4px; padding: 1px 5px; font-size: 0.82rem; }

.chat-intro {
    text-align: center;
    padding: 20px 16px 12px;
    color: #a8a29e;
    font-size: 0.78rem;
}
.chat-intro strong { color: #78716c; font-weight: 500; }

/* ── chat_input styling — single border only ─────────────────────────────── */
[data-testid="stChatInput"] {
    background: #ffffff !important;
    border-top: 1px solid #f0ece4 !important;
    padding: 10px 14px !important;
    box-shadow: none !important;
    outline: none !important;
}
/* Remove Streamlit's own outer wrapper border/shadow */
[data-testid="stChatInput"] > div {
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
    background: transparent !important;
}
/* The textarea gets the one visible border */
[data-testid="stChatInput"] textarea {
    background: #f7f5f2 !important;
    border: 1.5px solid #e2dbd2 !important;
    border-radius: 20px !important;
    color: #1c1917 !important;
    font-size: 0.88rem !important;
    font-family: 'Inter', sans-serif !important;
    resize: none !important;
    outline: none !important;
    box-shadow: none !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #007aff !important;
    box-shadow: 0 0 0 3px rgba(0,122,255,0.10) !important;
    background: #ffffff !important;
    outline: none !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #a8a29e !important; }

/* ── Activity panel ──────────────────────────────────────────────────────── */
.activity-panel {
    background: #ffffff;
    border: 1px solid #e2dbd2;
    border-radius: 16px;
    padding: 16px;
    box-shadow: 0 2px 16px rgba(0,0,0,0.05);
}
.activity-panel-title {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #a8a29e;
    margin-bottom: 12px;
}
.activity-item {
    font-size: 0.77rem;
    line-height: 1.5;
    padding: 6px 9px;
    border-radius: 6px;
    margin-bottom: 5px;
    border-left: 3px solid;
    color: #1c1917;
}
.ai-intent { background: #f5f3ff; border-left-color: #7c3aed; }
.ai-tool   { background: #eff6ff; border-left-color: #2563eb; }
.ai-search { background: #f0fdf4; border-left-color: #16a34a; }
.ai-ok     { background: #f8fafc; border-left-color: #64748b; }
.ai-error  { background: #fff1f2; border-left-color: #e11d48; }
.activity-empty { color: #d4cdc6; font-size: 0.77rem; font-style: italic; text-align: center; padding-top: 24px; }

/* Hide Streamlit's container border on the scrollable chat box */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}

/* ── Quick reply chips ───────────────────────────────────────────────────── */
[data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"] {
    background: #ffffff;
    border-top: 1px solid #f0ece4;
    padding: 8px 10px 10px !important;
    gap: 6px !important;
    flex-wrap: wrap;
}
[data-testid="stColumn"]:first-child [data-testid="stButton"] > button {
    background: #faf8f5 !important;
    color: #57534e !important;
    border: 1px solid #e2dbd2 !important;
    border-radius: 20px !important;
    padding: 5px 4px !important;
    font-size: 0.74rem !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    min-height: 0 !important;
    line-height: 1.4 !important;
    width: 100% !important;
    transition: background 0.15s, color 0.15s, border-color 0.15s !important;
}
[data-testid="stColumn"]:first-child [data-testid="stButton"] > button:hover {
    background: #f5f3ff !important;
    color: #7c3aed !important;
    border-color: #c4b5fd !important;
    box-shadow: none !important;
}
[data-testid="stColumn"]:first-child [data-testid="stButton"] > button:focus {
    box-shadow: 0 0 0 2px rgba(124,58,237,0.20) !important;
    outline: none !important;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: #d4cdc6; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Claude tools
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "get_order_status",
        "description": "Get shipping status and tracking for a customer order by order ID.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
    },
    {
        "name": "initiate_refund",
        "description": "Initiate a return and refund for an order. Only call this AFTER the customer has explicitly confirmed they want to proceed (e.g. replied 'yes', 'please go ahead', 'confirm'). Never call speculatively.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
    },
    {
        "name": "cancel_order",
        "description": (
            "Cancel a Processing order. Requires the order ID and the customer's full name "
            "exactly as on the order to verify identity. Cannot cancel orders that have already shipped — "
            "suggest a return instead. Only call after the customer has confirmed they want to cancel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id":      {"type": "string"},
                "customer_name": {"type": "string", "description": "Full name as on the order"},
            },
            "required": ["order_id", "customer_name"],
        },
    },
    {
        "name": "reset_password",
        "description": "Send a password reset email. Require the customer's email first.",
        "input_schema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
    },
    {
        "name": "search_knowledge_base",
        "description": "Search Bookly's policy KB for shipping, returns, or account info.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
]

SYSTEM_PROMPT = """You are Amelia, a friendly AI concierge for Bookly, an online bookstore.

Scope — you handle ONLY these three categories:
  1. Order status inquiries (checking status, tracking, cancellations)
  2. Return and refund requests
  3. General questions about Bookly policies (shipping, returns, payments, BookClub, eBooks, account/password)

If a customer asks about ANYTHING else — booking flights, recommendations, unrelated topics, general chat — firmly but warmly decline: "I'm here specifically to help with order status, returns, and Bookly policies. For anything else, please visit bookly.com or contact our team directly." Do NOT attempt to answer out-of-scope questions even partially.

Rules:
1. Only call tools when the customer explicitly asks for that action — never proactively look up orders or trigger operations.
2. Never fabricate order details — always call get_order_status when a customer asks about an order.
3. Require order ID before calling get_order_status or initiate_refund; require email before reset_password.
4. Use search_knowledge_base for all policy questions; base answers solely on retrieved content.
5. For refunds: first explain what will happen (amount, timeline), then WAIT for the customer to explicitly confirm in a separate reply before calling initiate_refund. Never call initiate_refund on a first request.
6. For cancellations: require the order ID and customer's full name. Explain that only Processing orders can be cancelled, then confirm before calling cancel_order. If the order has shipped, suggest a return instead.
7. After successfully completing a request, ask: "Is there anything else I can help you with today?"
8. If the customer says they are done (e.g. "no", "that's all", "goodbye", "thanks"), reply with a warm farewell tied to their last interaction — e.g. after an order status check: "Hope your [book title] arrives right on time! Enjoy the read! 📦"; after a refund: "Hope the refund goes smoothly — we look forward to seeing you again at Bookly! 📚"; after a cancellation: "No worries at all! Hope to see you back at Bookly soon!"; after a password reset: "Stay secure and happy reading! 📖" — then end your message with exactly this token on its own line: [END_SESSION]

Style: warm, concise, plain language. Resolve in as few turns as possible."""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_INTENT_LABELS = {
    "get_order_status": "order_status",
    "initiate_refund": "refund_request",
    "cancel_order": "order_cancellation",
    "reset_password": "password_reset",
    "search_knowledge_base": "policy_query",
}


def _execute_tool(name: str, inp: dict) -> dict:
    if name == "get_order_status":     return get_order_status(**inp)
    if name == "initiate_refund":      return initiate_refund(**inp)
    if name == "cancel_order":         return cancel_order(**inp)
    if name == "reset_password":       return reset_password(**inp)
    if name == "search_knowledge_base":
        docs = kb_search(inp["query"])
        return {"documents": [d["text"] for d in docs], "sources": [d["id"] for d in docs]}
    return {"error": f"Unknown tool: {name}"}


def run_agent(api_messages: list, activity_log: list) -> tuple[str, list]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        activity_log.append(("error", "ANTHROPIC_API_KEY not set"))
        return "Configuration error: please set ANTHROPIC_API_KEY.", api_messages

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=1024,
        system=SYSTEM_PROMPT, tools=TOOLS, messages=api_messages,
    )

    while resp.stop_reason == "tool_use":
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            activity_log.append(("intent", _INTENT_LABELS.get(block.name, "general_inquiry")))
            activity_log.append(("tool", block.name, block.input))
            try:
                result = _execute_tool(block.name, block.input)
                if block.name == "search_knowledge_base":
                    for src in result.get("sources", []):
                        activity_log.append(("retrieval", src))
                activity_log.append(("result", "success"))
            except Exception as exc:
                result = {"error": str(exc)}
                activity_log.append(("error", str(exc)))
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})

        api_messages = api_messages + [
            {"role": "assistant", "content": resp.content},
            {"role": "user", "content": results},
        ]
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=1024,
            system=SYSTEM_PROMPT, tools=TOOLS, messages=api_messages,
        )

    text = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    if not text:
        text = "I'm sorry, I wasn't able to generate a response. Please try again."
    if not any(i[0] == "intent" for i in activity_log):
        activity_log.append(("intent", "general_inquiry"))
    activity_log.append(("result", "response generated"))
    return text, api_messages + [{"role": "assistant", "content": resp.content}]


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _md(text: str) -> str:
    """Minimal markdown → HTML for bubble display."""
    t = html.escape(text)
    t = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*(.*?)\*',     r'<em>\1</em>',         t)
    t = re.sub(r'`(.*?)`',       r'<code>\1</code>',     t)
    # Bullet lists
    lines = t.split('\n')
    out, in_list = [], False
    for line in lines:
        if re.match(r'^[-•] ', line):
            if not in_list:
                out.append('<ul style="margin:6px 0 6px 16px;padding:0">')
                in_list = True
            out.append(f'<li style="margin:2px 0">{line[2:]}</li>')
        else:
            if in_list:
                out.append('</ul>')
                in_list = False
            out.append(line if line else '<br>')
    if in_list:
        out.append('</ul>')
    return ''.join(out)


def _render_bubble(role: str, content: str):
    if role == "user":
        st.markdown(
            f'<div class="bubble-row-user">'
            f'<div class="bubble-user">{html.escape(content)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="bubble-row-amelia">'
            f'<div class="bubble-avatar">A</div>'
            f'<div class="bubble-amelia">{_md(content)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_activity(activity: list[tuple]) -> str:
    rows, seen = [], set()
    for item in activity:
        k = item[0]
        if k == "intent":
            if item[1] in seen: continue
            seen.add(item[1])
            rows.append(f'<div class="activity-item ai-intent">&#127919; Intent: <strong>{item[1]}</strong></div>')
        elif k == "tool":
            params = ", ".join(f"{k}={v!r}" for k, v in (item[2] if len(item) > 2 else {}).items())
            rows.append(f'<div class="activity-item ai-tool">&#128295; <strong>{item[1]}</strong><br><code style="font-size:0.69rem;color:#64748b">{params}</code></div>')
        elif k == "retrieval":
            rows.append(f'<div class="activity-item ai-search">&#128269; vector_search &rarr; <strong>{item[1]}</strong></div>')
        elif k == "result":
            rows.append(f'<div class="activity-item ai-ok">&#10003; {item[1]}</div>')
        elif k == "error":
            rows.append(f'<div class="activity-item ai-error">&#10007; {item[1]}</div>')
    return "\n".join(rows)


def _books_html() -> str:
    cards = []
    for b in FEATURED_BOOKS:
        cover = f"https://covers.openlibrary.org/b/isbn/{b['isbn']}-M.jpg"
        cards.append(
            f'<div class="book-card" style="border-left-color:{b["accent"]}">'
            f'<div class="book-cover" style="background:{b["bg"]}">'
            f'<img src="{cover}" alt="" loading="lazy" onerror="this.style.display=\'none\'">'
            f'</div>'
            f'<div class="book-meta">'
            f'<div class="book-genre" style="color:{b["accent"]}">{b["genre"]}</div>'
            f'<div class="book-title">{b["title"]}</div>'
            f'</div></div>'
        )
    return (
        '<div class="card-books">'
        '<div class="books-header">'
        '<span class="books-badge">Staff Picks</span>'
        '<span class="books-label">Featured this week</span>'
        '</div>'
        '<div class="books-scroll">' + "".join(cards) + '</div>'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_AMELIA_GREETING = (
    "Hi there! Welcome to Bookly! 📚 I'm Amelia, your concierge. "
    "I can help you with questions about an order, need help with a return, "
    "or want to know about our policies — just ask!"
)

_QUICK_REPLIES = [
    ("Track my order",       "I'd like to check the status of my order."),
    ("Return a book",        "I want to return a book and get a refund."),
    ("Cancel my order",      "I need to cancel an order I just placed."),
    ("Reset my password",    "I forgot my password and need to reset it."),
    ("Return policy",        "What is your return and refund policy?"),
]

if "messages"       not in st.session_state:
    st.session_state.messages       = [{"role": "assistant", "content": _AMELIA_GREETING}]
if "api_messages"   not in st.session_state: st.session_state.api_messages   = []
if "activity"       not in st.session_state: st.session_state.activity       = []
if "quick_prompt"   not in st.session_state: st.session_state.quick_prompt   = None
if "last_agent_ts"  not in st.session_state: st.session_state.last_agent_ts  = time.time()
if "idle_nudge_sent" not in st.session_state: st.session_state.idle_nudge_sent = False
if "session_ended"  not in st.session_state: st.session_state.session_ended  = False

# Auto-refresh every 20 s so the idle check fires without user interaction
st_autorefresh(interval=20_000, key="idle_refresh")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

col_main, col_activity = st.columns([5, 2], gap="medium")

# ── Main white card ───────────────────────────────────────────────────────

with col_main:

    # 1. Logo bar
    st.markdown("""
    <div class="card-logo">
      <div class="card-logo-text">book<span>ly</span></div>
      <span class="card-logo-status">Amelia is online</span>
      <div class="card-logo-dot"></div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Featured books strip
    st.markdown(_books_html(), unsafe_allow_html=True)

    # 3. Scrollable iMessage-style conversation
    st.markdown('<div class="chat-bg">', unsafe_allow_html=True)

    chat_box = st.container(height=320, border=False)
    with chat_box:
        for msg in st.session_state.messages:
            _render_bubble(msg["role"], msg["content"])

        # Auto-scroll to bottom after new messages
        if st.session_state.messages:
            st.markdown(
                '<div id="chat-bottom"></div>'
                '<script>document.getElementById("chat-bottom")'
                '.scrollIntoView({behavior:"smooth"});</script>',
                unsafe_allow_html=True,
            )

    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.session_ended:
        # Session is over — show a reset button instead of input
        st.markdown(
            '<div style="background:#ffffff;border-top:1px solid #f0ece4;'
            'padding:14px 16px;text-align:center;">'
            '<span style="font-size:0.78rem;color:#a8a29e">'
            'This session has ended.</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("Start a new conversation", key="new_session", use_container_width=True):
            for key in ["messages", "api_messages", "activity", "last_agent_ts",
                        "idle_nudge_sent", "session_ended", "quick_prompt"]:
                st.session_state.pop(key, None)
            st.rerun()
        prompt = None
    else:
        # 4. Quick reply chips
        qr_cols = st.columns(len(_QUICK_REPLIES))
        for col, (label, full_prompt) in zip(qr_cols, _QUICK_REPLIES):
            if col.button(label, key=f"qr_{label}", use_container_width=True):
                st.session_state.quick_prompt = full_prompt
                st.rerun()

        # 5. Chat input (Enter to send)
        prompt = st.chat_input("Message Amelia…")

# ── Activity panel ────────────────────────────────────────────────────────

with col_activity:
    st.markdown(
        '<div class="activity-panel">'
        '<div class="activity-panel-title">Agent Activity</div>',
        unsafe_allow_html=True,
    )
    if st.session_state.activity:
        st.markdown(_render_activity(st.session_state.activity), unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="activity-empty">Waiting for activity&hellip;</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Idle nudge — fires on each auto-refresh if waiting > 60 s
# ---------------------------------------------------------------------------

_IDLE_TIMEOUT = 60  # seconds

if (
    not st.session_state.session_ended
    and not st.session_state.idle_nudge_sent
    and len(st.session_state.messages) > 1
    and st.session_state.messages[-1]["role"] == "assistant"
    and time.time() - st.session_state.last_agent_ts > _IDLE_TIMEOUT
):
    nudge = "Still there? No rush — take your time. I'm here whenever you're ready!"
    st.session_state.messages.append({"role": "assistant", "content": nudge})
    st.session_state.idle_nudge_sent = True
    st.rerun()

# ---------------------------------------------------------------------------
# Process input
# ---------------------------------------------------------------------------

_END_TOKEN = "[END_SESSION]"

active_prompt = prompt or st.session_state.pop("quick_prompt", None)

if active_prompt and not st.session_state.session_ended:
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    st.session_state.api_messages.append({"role": "user", "content": active_prompt})
    # User replied — reset idle tracking
    st.session_state.idle_nudge_sent = False

    with st.spinner(""):
        activity_log: list[tuple] = []
        response_text, new_api_messages = run_agent(
            st.session_state.api_messages, activity_log,
        )

    # Detect session-end signal from Amelia
    if _END_TOKEN in response_text:
        response_text = response_text.replace(_END_TOKEN, "").strip()
        st.session_state.session_ended = True

    st.session_state.messages.append({"role": "assistant", "content": response_text})
    st.session_state.api_messages = new_api_messages
    st.session_state.activity = activity_log
    st.session_state.last_agent_ts = time.time()
    st.rerun()
