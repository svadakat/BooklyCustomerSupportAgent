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
from tools import get_order_status, initiate_refund, cancel_order

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
    padding: 14px 20px 12px;
    border-bottom: 1px solid #f0ece4;
    display: flex;
    align-items: center;
    gap: 10px;
}
/* Logo bar: nested columns row */
[data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"]:first-of-type {
    background: #ffffff;
    border-bottom: 1px solid #f0ece4;
    gap: 0 !important;
    align-items: center;
}
[data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"]:first-of-type
    > [data-testid="stColumn"] > div:first-child {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}
[data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"]:first-of-type
    > [data-testid="stColumn"] {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
[data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"]:first-of-type
    > [data-testid="stColumn"]:last-child {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 16px !important;
}
[data-testid="stColumn"]:first-child [data-testid="stHorizontalBlock"]:first-of-type
    [data-testid="stToggle"] label {
    font-size: 0.72rem;
    color: #78716c;
}

/* ── Inline turn layout (bubble + activity side by side in chat) ─────────── */
.turn-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    margin: 4px 0;
}
.turn-bubble { flex: 1; min-width: 0; }
.turn-activity {
    width: 220px;
    flex-shrink: 0;
    background: #f8f7f5;
    border: 1px solid #e2dbd2;
    border-radius: 10px;
    padding: 8px 10px;
    max-height: 160px;
    overflow-y: auto;
}
.turn-activity-title {
    font-size: 0.62rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #a8a29e;
    margin-bottom: 5px;
}
.card-logo-text {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.2rem;
    font-weight: 600;
    color: #1c1917;
    letter-spacing: -0.02em;
}
.card-logo-text span { color: #7c3aed; }
.card-logo-status {
    font-size: 0.72rem;
    color: #78716c;
    margin-right: 4px;
}

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
.activity-empty { color: #d4cdc6; font-size: 0.77rem; font-style: italic; text-align: center; padding-top: 24px; }

/* ── Activity timeline ───────────────────────────────────────────────────── */
.tl-turn-header {
    font-size: 0.60rem;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #a8a29e;
    margin: 10px 0 6px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #f0ece4;
}
.tl-turn-header:first-child { margin-top: 2px; }
.tl-track {
    position: relative;
    padding-left: 18px;
    margin: 0;
}
.tl-track::before {
    content: '';
    position: absolute;
    left: 5px;
    top: 6px;
    bottom: 4px;
    width: 2px;
    background: linear-gradient(to bottom, #e2dbd2, #f5f3f0);
    border-radius: 1px;
}
.tl-item {
    position: relative;
    margin-bottom: 9px;
    display: flex;
    align-items: flex-start;
}
.tl-dot {
    position: absolute;
    left: -15px;
    top: 4px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 2px solid #ffffff;
    flex-shrink: 0;
    z-index: 1;
}
.tl-intent .tl-dot { background: #7c3aed; box-shadow: 0 0 0 2px #ddd6fe; }
.tl-tool   .tl-dot { background: #2563eb; box-shadow: 0 0 0 2px #bfdbfe; }
.tl-search .tl-dot { background: #16a34a; box-shadow: 0 0 0 2px #bbf7d0; }
.tl-ok     .tl-dot { background: #64748b; box-shadow: 0 0 0 2px #e2e8f0; }
.tl-error  .tl-dot { background: #e11d48; box-shadow: 0 0 0 2px #fecdd3; }
.tl-content { font-size: 0.74rem; line-height: 1.5; color: #1c1917; }
.tl-label   { font-weight: 600; }
.tl-detail  { font-size: 0.67rem; color: #64748b; font-family: monospace; word-break: break-word; }
.tl-ts      { font-size: 0.60rem; font-weight: 400; color: #a8a29e; font-family: monospace; margin-left: 6px; }

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
        "description": "Get shipping status and tracking for a customer order. Requires confirmation number, full name, and zip code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "confirmation_number": {"type": "string", "description": "Confirmation number from the order confirmation email, e.g. CF-A7K2M"},
                "full_name":           {"type": "string", "description": "Customer's full name as on the account"},
                "zip_code":            {"type": "string", "description": "Customer's billing/shipping zip code"},
            },
            "required": ["confirmation_number", "full_name", "zip_code"],
        },
    },
    {
        "name": "initiate_refund",
        "description": "Initiate a return and refund for an order. Only call this AFTER the customer has explicitly confirmed they want to proceed. Requires confirmation number, full name, and zip code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "confirmation_number": {"type": "string", "description": "Confirmation number from the order confirmation email, e.g. CF-A7K2M"},
                "full_name":           {"type": "string", "description": "Customer's full name as on the account"},
                "zip_code":            {"type": "string", "description": "Customer's billing/shipping zip code"},
            },
            "required": ["confirmation_number", "full_name", "zip_code"],
        },
    },
    {
        "name": "cancel_order",
        "description": (
            "Cancel a Processing order. Requires confirmation number, full name, and zip code to verify identity. "
            "Cannot cancel orders that have already shipped — suggest a return instead. "
            "Only call after the customer has confirmed they want to cancel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "confirmation_number": {"type": "string", "description": "Confirmation number from the order confirmation email, e.g. CF-A7K2M"},
                "full_name":           {"type": "string", "description": "Customer's full name as on the account"},
                "zip_code":            {"type": "string", "description": "Customer's billing/shipping zip code"},
            },
            "required": ["confirmation_number", "full_name", "zip_code"],
        },
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
  3. General questions about Bookly policies (shipping, returns, payments, BookClub, eBooks)

If a customer asks about ANYTHING else — booking flights, recommendations, unrelated topics, general chat — firmly but warmly decline: "I'm here specifically to help with order status, returns, and Bookly policies. For anything else, please visit bookly.com or contact our team directly." Do NOT attempt to answer out-of-scope questions even partially.

Rules:
1. Never call a tool unless the customer has explicitly requested that action in the current conversation. Do not look up orders, trigger refunds, or cancel orders unprompted. However, once the customer has stated their intent AND supplied all three required credentials, call the tool immediately — do not ask for a second confirmation.
2. Never fabricate order details — always call get_order_status when a customer asks about an order.
3. Credential gates — required before calling each tool:
   • get_order_status / initiate_refund / cancel_order: confirmation number (format CF-XXXXX), full name, and zip code — all three must be collected before calling; no credentials needed for general policy questions.
   Collect any missing credentials one at a time, then call the tool immediately once all are provided.
4. Use search_knowledge_base for all policy questions; base answers solely on retrieved content.
5. For refunds: first explain what will happen (amount, timeline), then WAIT for the customer to explicitly confirm in a separate reply before calling initiate_refund. Never call initiate_refund on a first request.
6. For cancellations: collect all three credentials (confirmation number, full name, zip code). Explain that only Processing orders can be cancelled, then confirm before calling cancel_order. If the order has shipped, suggest a return instead.
7. After successfully completing a request, ask: "Is there anything else I can help you with today?"
8. If the customer says they are done (e.g. "no", "that's all", "goodbye", "thanks"), reply with a warm farewell tied to their last interaction — e.g. after an order status check: "Hope your [book title] arrives right on time! Enjoy the read! 📦"; after a refund: "Hope the refund goes smoothly — we look forward to seeing you again at Bookly! 📚"; after a cancellation: "No worries at all! Hope to see you back at Bookly soon!" — then end your message with exactly this token on its own line: [END_SESSION]

Style: warm, concise, plain language. Resolve in as few turns as possible."""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_INTENT_LABELS = {
    "get_order_status": "order_status",
    "initiate_refund": "refund_request",
    "cancel_order": "order_cancellation",
    "search_knowledge_base": "policy_query",
}


def _execute_tool(name: str, inp: dict) -> dict:
    if name == "get_order_status":     return get_order_status(**inp)
    if name == "initiate_refund":      return initiate_refund(**inp)
    if name == "cancel_order":         return cancel_order(**inp)
    if name == "search_knowledge_base":
        docs = kb_search(inp["query"])
        return {"documents": [d["text"] for d in docs], "sources": [d["id"] for d in docs]}
    return {"error": f"Unknown tool: {name}"}


def _tool_result_detail(tool_name: str, result: dict) -> str:
    if tool_name == "get_order_status":
        parts = [f"status: {result.get('status', '—')}"]
        if result.get("carrier"):
            parts.append(f"carrier: {result['carrier']}")
        if result.get("tracking_number"):
            parts.append(f"tracking: {result['tracking_number']}")
        if result.get("delivery_estimate"):
            parts.append(f"est. delivery: {result['delivery_estimate']}")
        return " · ".join(parts)
    if tool_name == "initiate_refund":
        return f"refund initiated · return_id: {result.get('return_id', '—')}"
    if tool_name == "cancel_order":
        return f"order cancelled · {result.get('message', '')}"
    return "success"


def run_agent(api_messages: list, activity_log: list) -> tuple[str, list]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        activity_log.append(("error", "ANTHROPIC_API_KEY not set"))
        return "Configuration error: please set ANTHROPIC_API_KEY.", api_messages

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=1024,
        system=SYSTEM_PROMPT, tools=TOOLS, messages=api_messages,
    )

    def _ts() -> str:
        return time.strftime("%H:%M:%S")

    while resp.stop_reason == "tool_use":
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            activity_log.append(("intent", _INTENT_LABELS.get(block.name, "general_inquiry"), {}, _ts()))
            activity_log.append(("tool", block.name, block.input, _ts()))
            try:
                result = _execute_tool(block.name, block.input)
                if block.name == "search_knowledge_base":
                    for src in result.get("sources", []):
                        activity_log.append(("retrieval", src, {}, _ts()))
                    activity_log.append(("result", "kb docs retrieved", {}, _ts()))
                elif result.get("found") is False or result.get("success") is False:
                    activity_log.append(("error", result.get("message", "Tool returned an error"), {}, _ts()))
                else:
                    detail = _tool_result_detail(block.name, result)
                    activity_log.append(("result", detail, {}, _ts()))
            except Exception as exc:
                result = {"error": str(exc)}
                activity_log.append(("error", str(exc), {}, _ts()))
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})

        api_messages = api_messages + [
            {"role": "assistant", "content": resp.content},
            {"role": "user", "content": results},
        ]
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=1024,
            system=SYSTEM_PROMPT, tools=TOOLS, messages=api_messages,
        )

    text = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
    if not text:
        text = "I'm sorry, I wasn't able to generate a response. Please try again."
    if not any(i[0] == "intent" for i in activity_log):
        activity_log.append(("intent", "general_inquiry", {}, _ts()))
    activity_log.append(("result", "response generated", {}, _ts()))
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


def _render_bubble(role: str, content: str, activity: list | None = None):
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
    """Render one turn's activity log as a vertical timeline with timestamps."""
    items, seen = [], set()
    for item in activity:
        k = item[0]
        ts = item[-1] if isinstance(item[-1], str) and len(item[-1]) == 8 and item[-1].count(":") == 2 else ""
        ts_html = f'<span class="tl-ts">{ts}</span>' if ts else ""

        if k == "intent":
            if item[1] in seen:
                continue
            seen.add(item[1])
            items.append(
                '<div class="tl-item tl-intent">'
                '<div class="tl-dot"></div>'
                '<div class="tl-content">'
                f'<div class="tl-label">&#127919;&nbsp;{html.escape(item[1])}{ts_html}</div>'
                '</div></div>'
            )
        elif k == "tool":
            params = ", ".join(f"{p}={v!r}" for p, v in (item[2] if isinstance(item[2], dict) else {}).items())
            detail = f'<div class="tl-detail">{html.escape(params)}</div>' if params else ""
            items.append(
                '<div class="tl-item tl-tool">'
                '<div class="tl-dot"></div>'
                '<div class="tl-content">'
                f'<div class="tl-label">&#128295;&nbsp;{html.escape(item[1])}{ts_html}</div>'
                f'{detail}'
                '</div></div>'
            )
        elif k == "retrieval":
            items.append(
                '<div class="tl-item tl-search">'
                '<div class="tl-dot"></div>'
                '<div class="tl-content">'
                f'<div class="tl-label">&#128269;&nbsp;{html.escape(item[1])}{ts_html}</div>'
                '</div></div>'
            )
        elif k == "result":
            items.append(
                '<div class="tl-item tl-ok">'
                '<div class="tl-dot"></div>'
                '<div class="tl-content">'
                f'<div class="tl-label">&#10003;&nbsp;{html.escape(item[1])}{ts_html}</div>'
                '</div></div>'
            )
        elif k == "error":
            items.append(
                '<div class="tl-item tl-error">'
                '<div class="tl-dot"></div>'
                '<div class="tl-content">'
                f'<div class="tl-label">&#10007;&nbsp;{html.escape(item[1])}{ts_html}</div>'
                '</div></div>'
            )
    if not items:
        return ""
    return '<div class="tl-track">' + "\n".join(items) + "</div>"


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
    ("Return policy",        "What is your return and refund policy?"),
]

if "messages"       not in st.session_state:
    st.session_state.messages       = [{"role": "assistant", "content": _AMELIA_GREETING}]
if "api_messages"   not in st.session_state: st.session_state.api_messages   = []
if "quick_prompt"   not in st.session_state: st.session_state.quick_prompt   = None
if "last_agent_ts"  not in st.session_state: st.session_state.last_agent_ts  = time.time()
if "idle_nudge_sent" not in st.session_state: st.session_state.idle_nudge_sent = False
if "session_ended"  not in st.session_state: st.session_state.session_ended  = False
if "show_activity"  not in st.session_state: st.session_state.show_activity  = True
if "pending_agent"  not in st.session_state: st.session_state.pending_agent  = False

# Auto-refresh every 20 s so the idle check fires without user interaction
st_autorefresh(interval=20_000, key="idle_refresh")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

if st.session_state.show_activity:
    col_main, col_activity = st.columns([5, 2], gap="medium")
else:
    col_main = st.columns(1)[0]
    col_activity = None

# ── Main white card ───────────────────────────────────────────────────────

with col_main:

    # 1. Logo bar with activity toggle
    _logo_col, _toggle_col = st.columns([5, 1])
    with _logo_col:
        st.markdown("""
        <div class="card-logo">
          <div class="card-logo-text">book<span>ly</span></div>
          <span class="card-logo-status">Amelia is online</span>
        </div>
        """, unsafe_allow_html=True)
    with _toggle_col:
        st.toggle("Activity", key="show_activity")

    # 2. Scrollable iMessage-style conversation
    st.markdown('<div class="chat-bg">', unsafe_allow_html=True)

    chat_box = st.container(height=450, border=False)
    with chat_box:
        # Scroll to top so the most recent message (rendered first) is visible
        if st.session_state.messages:
            st.markdown(
                '<div id="chat-top"></div>'
                '<script>document.getElementById("chat-top")'
                '.scrollIntoView({behavior:"smooth"});</script>',
                unsafe_allow_html=True,
            )

        for msg in reversed(st.session_state.messages):
            _render_bubble(msg["role"], msg["content"], msg.get("activity"))


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
            for key in ["messages", "api_messages", "last_agent_ts",
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

        # 5. Chat input (Enter to send)
        prompt = st.chat_input("Message Amelia…")

# ── Activity panel (own white card, right column) ─────────────────────────

if col_activity is not None:
    with col_activity:
        st.markdown(
            '<div class="activity-panel">'
            '<div class="activity-panel-title">Agent Activity</div>',
            unsafe_allow_html=True,
        )
        turns = [msg for msg in st.session_state.messages if msg.get("activity")]
        if turns:
            act_box = st.container(height=450, border=False)
            with act_box:
                total = len(turns)
                for i, msg in enumerate(reversed(turns)):
                    turn_num = total - i
                    st.markdown(
                        f'<div class="tl-turn-header">Turn {turn_num}</div>',
                        unsafe_allow_html=True,
                    )
                    rendered = _render_activity(msg["activity"])
                    if rendered:
                        st.markdown(rendered, unsafe_allow_html=True)
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

# Phase 1 — show user message immediately, then rerun to trigger the agent
if active_prompt and not st.session_state.session_ended:
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    st.session_state.api_messages.append({"role": "user", "content": active_prompt})
    st.session_state.idle_nudge_sent = False
    st.session_state.pending_agent = True
    st.rerun()

# Phase 2 — user message is already visible; now run the agent
if st.session_state.pending_agent and not st.session_state.session_ended:
    st.session_state.pending_agent = False
    with st.spinner(""):
        activity_log: list[tuple] = []
        response_text, new_api_messages = run_agent(
            st.session_state.api_messages, activity_log,
        )

    # Detect session-end signal from Amelia
    if _END_TOKEN in response_text:
        response_text = response_text.replace(_END_TOKEN, "").strip()
        st.session_state.session_ended = True

    st.session_state.messages.append({"role": "assistant", "content": response_text, "activity": activity_log})
    st.session_state.api_messages = new_api_messages
    st.session_state.last_agent_ts = time.time()
    st.rerun()
