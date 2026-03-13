"""
db.py — SQLite database for Bookly: customers, orders, returns, and
        customer interaction history.

The DB file (bookly.db) is created next to this script on first import
and seeded with realistic demo data.
"""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bookly.db")


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Schema + seed
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    phone         TEXT,
    member_since  TEXT,
    zip_code      TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    order_id             TEXT PRIMARY KEY,
    customer_id          TEXT NOT NULL,
    book_title           TEXT NOT NULL,
    book_author          TEXT NOT NULL,
    quantity             INTEGER NOT NULL DEFAULT 1,
    total_amount         REAL NOT NULL,
    status               TEXT NOT NULL,
    carrier              TEXT,
    tracking_number      TEXT,
    order_date           TEXT NOT NULL,
    delivery_estimate    TEXT,
    confirmation_number  TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS returns (
    return_id       TEXT PRIMARY KEY,
    order_id        TEXT NOT NULL,
    customer_id     TEXT NOT NULL,
    reason          TEXT NOT NULL,
    status          TEXT NOT NULL,
    return_date     TEXT NOT NULL,
    refund_amount   REAL NOT NULL,
    refund_status   TEXT NOT NULL,
    FOREIGN KEY (order_id)     REFERENCES orders(order_id),
    FOREIGN KEY (customer_id)  REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS customer_interactions (
    interaction_id  TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    date            TEXT NOT NULL,
    type            TEXT NOT NULL,
    summary         TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
"""

_CUSTOMERS = [
    # (customer_id, name, email, phone, member_since, zip_code)
    # original 5
    ("C001", "Sarah Mitchell",    "sarah.mitchell@email.com",   "415-555-0101", "2023-04-12", "94102"),
    ("C002", "James Rodriguez",   "james.r@gmail.com",          "212-555-0182", "2022-11-03", "10001"),
    ("C003", "Emily Chen",        "emily.chen@bookworm.com",    "650-555-0247", "2021-06-18", "94301"),
    ("C004", "Michael Thompson",  "mthompson@work.com",         "312-555-0334", "2024-01-09", "60601"),
    ("C005", "Priya Sharma",      "priya.s@outlook.com",        "408-555-0456", "2023-09-22", "95101"),
    # 10 new customers
    ("C006", "David Kim",         "david.kim@techie.com",       "310-555-0612", "2022-03-15", "90001"),
    ("C007", "Rachel Green",      "rachel.g@hotmail.com",       "617-555-0771", "2023-07-04", "02101"),
    ("C008", "Omar Hassan",       "omar.hassan@gmail.com",      "713-555-0885", "2024-02-28", "77001"),
    ("C009", "Lisa Nguyen",       "lisa.nguyen@yahoo.com",      "503-555-0934", "2021-12-01", "97201"),
    ("C010", "Tom Bradley",       "t.bradley@company.com",      "202-555-1023", "2023-11-19", "20001"),
    ("C011", "Aisha Patel",       "aisha.patel@gmail.com",      "404-555-1145", "2022-08-30", "30301"),
    ("C012", "Carlos Rivera",     "c.rivera@outlook.com",       "305-555-1267", "2024-03-01", "33101"),
    ("C013", "Jennifer Wu",       "jen.wu@stanford.edu",        "650-555-1389", "2020-09-01", "94305"),
    ("C014", "Robert Davis",      "rdavis@enterprise.com",      "214-555-1401", "2023-05-17", "75201"),
    ("C015", "Natasha Ivanova",   "n.ivanova@gmail.com",        "206-555-1512", "2022-06-11", "98101"),
]

_ORDERS = [
    # (order_id, customer_id, book_title, book_author, qty, total, status, carrier, tracking, order_date, delivery_estimate, confirmation_number)

    # ── Original 10 ──────────────────────────────────────────────────────────
    ("B1001", "C001", "The Covenant of Water",                    "Abraham Verghese",                   1, 27.99, "Shipped",           "UPS",   "1Z999AA10191226791",   "2026-03-01", "2026-03-09", "CF-A7K2M"),
    ("B1002", "C002", "Zero to One + Sapiens (bundle)",           "Peter Thiel / Yuval Noah Harari",    2, 45.98, "Processing",        None,    None,                   "2026-03-05", "2026-03-12", "CF-B3X9P"),
    ("B1003", "C003", "Thinking, Fast and Slow",                  "Daniel Kahneman",                    1, 18.99, "Delivered",         "FedEx", "449044304137821",      "2026-02-13", "2026-02-20", "CF-C5N1Q"),
    ("B1004", "C004", "Meditations",                              "Marcus Aurelius",                    1, 14.99, "Out for Delivery",   "USPS",  "9400111899223397591",  "2026-03-04", "2026-03-07", "CF-D8L4R"),
    ("B1005", "C005", "Superintelligence",                        "Nick Bostrom",                       1, 24.99, "Shipped",           "FedEx", "788899820820",         "2026-03-03", "2026-03-10", "CF-E2W7S"),
    ("B1006", "C001", "The Beginning of Infinity",                "David Deutsch",                      1, 21.99, "Processing",        None,    None,                   "2026-03-06", "2026-03-13", "CF-F6Y3T"),
    ("B1007", "C002", "Man's Search for Meaning",                 "Viktor Frankl",                      1, 13.99, "Delivered",         "UPS",   "1Z999AA10191226792",   "2026-02-08", "2026-02-15", "CF-G4Z8U"),
    ("B1008", "C003", "Brave New World",                          "Aldous Huxley",                      1, 11.99, "Shipped",           "USPS",  "9400111899223397592",  "2026-03-02", "2026-03-09", "CF-H1V5V"),
    ("B1009", "C004", "Blitzscaling",                             "Reid Hoffman & Chris Yeh",           1, 29.99, "Delivered",         "FedEx", "449044304137822",      "2026-02-23", "2026-03-01", "CF-J9M2W"),
    ("B1010", "C005", "Sapiens",                                  "Yuval Noah Harari",                  1, 19.99, "Delivered",         "UPS",   "1Z999AA10191226793",   "2026-02-18", "2026-02-25", "CF-K7P6X"),

    # ── 20 new orders ────────────────────────────────────────────────────────
    ("B1011", "C006", "Zero to One",                              "Peter Thiel & Blake Masters",        1, 22.99, "Processing",        None,    None,                   "2026-03-06", "2026-03-13", "CF-L3Q1Y"),
    ("B1012", "C007", "Sapiens",                                  "Yuval Noah Harari",                  1, 19.99, "Shipped",           "UPS",   "1Z999AA10191226794",   "2026-03-02", "2026-03-09", "CF-M8R4Z"),
    ("B1013", "C008", "Man's Search for Meaning + Meditations",   "Viktor Frankl / Marcus Aurelius",    2, 28.98, "Delivered",         "FedEx", "449044304137823",      "2026-02-10", "2026-02-17", "CF-N2S7A"),
    ("B1014", "C009", "The Lean Startup",                         "Eric Ries",                          1, 23.99, "Shipped",           "FedEx", "788899820821",         "2026-03-04", "2026-03-11", "CF-P5T3B"),
    ("B1015", "C010", "Thinking, Fast and Slow",                  "Daniel Kahneman",                    1, 18.99, "Out for Delivery",   "USPS",  "9400111899223397593",  "2026-03-05", "2026-03-07", "CF-Q1U9C"),
    ("B1016", "C011", "Einstein: His Life and Universe",          "Walter Isaacson",                    1, 25.99, "Processing",        None,    None,                   "2026-03-06", "2026-03-13", "CF-R6V2D"),
    ("B1017", "C012", "Brave New World",                          "Aldous Huxley",                      1, 11.99, "Delivered",         "UPS",   "1Z999AA10191226795",   "2026-02-20", "2026-02-27", "CF-S4W8E"),
    ("B1018", "C013", "The Score Takes Care of Itself",           "Bill Walsh",                         1, 21.99, "Shipped",           "FedEx", "788899820822",         "2026-03-03", "2026-03-10", "CF-T7X1F"),
    ("B1019", "C014", "Superintelligence + Beginning of Infinity","Nick Bostrom / David Deutsch",        2, 46.98, "Processing",        None,    None,                   "2026-03-07", "2026-03-14", "CF-U3Y5G"),
    ("B1020", "C015", "Secrets of Sand Hill Road",                "Scott Kupor",                        1, 26.99, "Delivered",         "USPS",  "9400111899223397594",  "2026-02-14", "2026-02-21", "CF-V9Z4H"),
    ("B1021", "C001", "Zero to One",                              "Peter Thiel & Blake Masters",        1, 22.99, "Delivered",         "FedEx", "449044304137824",      "2026-02-05", "2026-02-12", "CF-W2A8J"),
    ("B1022", "C002", "The Innovator's Dilemma",                  "Clayton M. Christensen",             1, 24.99, "Shipped",           "UPS",   "1Z999AA10191226796",   "2026-03-04", "2026-03-11", "CF-X6B3K"),
    ("B1023", "C003", "Blitzscaling",                             "Reid Hoffman & Chris Yeh",           1, 29.99, "Processing",        None,    None,                   "2026-03-07", "2026-03-14", "CF-Y1C7L"),
    ("B1024", "C004", "Sapiens",                                  "Yuval Noah Harari",                  1, 19.99, "Delivered",         "FedEx", "449044304137825",      "2026-01-28", "2026-02-04", "CF-Z8D2M"),
    ("B1025", "C005", "The Master Algorithm",                     "Pedro Domingos",                     1, 23.99, "Shipped",           "UPS",   "1Z999AA10191226797",   "2026-03-05", "2026-03-12", "CF-A4E6N"),
    ("B1026", "C006", "Brave New World",                          "Aldous Huxley",                      1, 11.99, "Delivered",         "USPS",  "9400111899223397595",  "2026-02-22", "2026-03-01", "CF-B9F1P"),
    ("B1027", "C007", "The Covenant of Water",                    "Abraham Verghese",                   1, 27.99, "Out for Delivery",   "FedEx", "788899820823",         "2026-03-05", "2026-03-07", "CF-C5G4Q"),
    ("B1028", "C008", "Blitzscaling",                             "Reid Hoffman & Chris Yeh",           1, 29.99, "Processing",        None,    None,                   "2026-03-06", "2026-03-13", "CF-D2H8R"),
    ("B1029", "C009", "Meditations",                              "Marcus Aurelius",                    1, 14.99, "Shipped",           "UPS",   "1Z999AA10191226798",   "2026-03-03", "2026-03-10", "CF-E7J3S"),
    ("B1030", "C010", "The Second Machine Age",                   "Brynjolfsson & McAfee",              1, 22.99, "Delivered",         "FedEx", "449044304137826",      "2026-02-18", "2026-02-25", "CF-F1K9T"),
]

_RETURNS = [
    # (return_id, order_id, customer_id, reason, status, return_date, refund_amount, refund_status)

    # ── Original 2 ───────────────────────────────────────────────────────────
    ("R001", "B1003", "C003",
     "Book arrived with water damage on pages 50–80. Pages are stuck together and unreadable.",
     "Refunded",  "2026-02-22", 18.99,
     "Refund of $18.99 issued to original Visa card ending 4242"),

    ("R002", "B1007", "C002",
     "Received hardcover edition but ordered the paperback. Wrong format shipped.",
     "Approved",  "2026-02-17", 13.99,
     "Refund of $13.99 pending — awaiting return shipment from customer"),

    # ── 5 new returns ─────────────────────────────────────────────────────────
    ("R003", "B1013", "C008",
     "Ordered paperback bundle but received hardcover copy of Meditations. Wrong edition.",
     "Approved",  "2026-02-19", 28.98,
     "Prepaid return label emailed. Refund of $28.98 will be issued once item is received"),

    ("R004", "B1017", "C012",
     "Accidentally placed a duplicate order — already own this book.",
     "Refunded",  "2026-02-28", 11.99,
     "Refund of $11.99 issued to Mastercard ending 7891 on 2026-03-02"),

    ("R005", "B1020", "C015",
     "Book spine cracked and pages falling out on arrival. Item arrived in unusable condition.",
     "Refunded",  "2026-02-23", 26.99,
     "Refund of $26.99 issued to PayPal account on 2026-02-25. No return required for damaged item"),

    ("R006", "B1026", "C006",
     "Changed mind after reading the first chapter — not what I expected from the description.",
     "In Transit", "2026-03-02", 11.99,
     "Return shipment scanned by USPS. Refund of $11.99 will be issued within 3–5 days of receipt"),

    ("R007", "B1024", "C004",
     "Received Spanish-language edition instead of English. Incorrect fulfillment.",
     "Refunded",  "2026-02-06", 19.99,
     "Refund of $19.99 issued to original payment method. Replacement English edition shipped free of charge"),
]

_INTERACTIONS = [
    # ── Original 5 ───────────────────────────────────────────────────────────
    ("I001", "C003", "2026-02-22", "return",  "Reported water damage on B1003 (Thinking, Fast and Slow). Return approved, refund issued."),
    ("I002", "C002", "2026-02-17", "return",  "Wrong edition for B1007 (Man's Search for Meaning). Return label sent, refund pending."),
    ("I003", "C001", "2026-03-02", "support", "Asked about delivery estimate for B1001. Informed order shipped via UPS."),
    ("I004", "C005", "2026-02-26", "support", "Password reset requested for priya.s@outlook.com. Reset link sent."),
    ("I005", "C004", "2026-03-05", "order",   "Placed order B1004 for Meditations. Standard shipping selected."),
    # ── 15 new interactions ───────────────────────────────────────────────────
    ("I006", "C008", "2026-02-19", "return",  "Wrong edition in B1013 bundle. Return label emailed, refund pending receipt."),
    ("I007", "C012", "2026-02-28", "return",  "Duplicate order B1017 refunded. Customer confirmed receipt of refund."),
    ("I008", "C015", "2026-02-23", "return",  "Damaged item B1020 (Secrets of Sand Hill Road). Refund issued, no return needed."),
    ("I009", "C006", "2026-03-02", "return",  "Change-of-mind return B1026. Return label sent, item in transit."),
    ("I010", "C004", "2026-02-06", "return",  "Wrong language edition B1024. Refunded and sent replacement English copy."),
    ("I011", "C007", "2026-03-03", "support", "Asked when B1012 would arrive. Provided UPS tracking 1Z999AA10191226794."),
    ("I012", "C014", "2026-03-07", "order",   "Placed bundle order B1019 (Superintelligence + Beginning of Infinity)."),
    ("I013", "C009", "2026-03-04", "support", "Enquired about express upgrade for B1014. Advised too late to change shipping."),
    ("I014", "C013", "2026-03-03", "support", "Asked about BookClub points balance. Directed to My Account > Rewards."),
    ("I015", "C011", "2026-03-06", "order",   "Placed order B1016 for Einstein biography. Confirmed email with estimated delivery."),
    ("I016", "C010", "2026-03-05", "support", "Enquired about B1015 (out for delivery). Confirmed USPS tracking active."),
    ("I017", "C001", "2026-02-12", "support", "Confirmed delivery of B1021 (Zero to One). Customer happy with purchase."),
    ("I018", "C002", "2026-03-04", "order",   "Placed order B1022 (Innovator's Dilemma). Chose standard shipping."),
    ("I019", "C005", "2026-03-05", "support", "Asked about return window for B1010 (Sapiens). Advised 30-day policy still active."),
    ("I020", "C003", "2026-03-07", "order",   "Placed order B1023 (Blitzscaling). Used BookClub Silver discount."),
]


def _seed(con: sqlite3.Connection):
    """Upsert all seed rows — INSERT OR IGNORE means existing rows are untouched,
    new rows are added on every restart, so expanding the lists above just works."""
    con.executemany("INSERT OR IGNORE INTO customers VALUES (?,?,?,?,?,?)",       _CUSTOMERS)
    con.executemany("INSERT OR IGNORE INTO orders    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", _ORDERS)
    con.executemany("INSERT OR IGNORE INTO returns   VALUES (?,?,?,?,?,?,?,?)",   _RETURNS)
    con.executemany("INSERT OR IGNORE INTO customer_interactions VALUES (?,?,?,?,?)", _INTERACTIONS)
    # Backfill columns added after initial seed
    for row in _ORDERS:
        con.execute(
            "UPDATE orders SET confirmation_number = ? WHERE order_id = ? AND confirmation_number IS NULL",
            (row[11], row[0]),
        )
    for row in _CUSTOMERS:
        con.execute(
            "UPDATE customers SET zip_code = ? WHERE customer_id = ? AND zip_code IS NULL",
            (row[5], row[0]),
        )


def init_db():
    with _conn() as con:
        con.executescript(_SCHEMA)
        # Migrations: add columns introduced after initial schema
        for ddl in [
            "ALTER TABLE orders    ADD COLUMN confirmation_number TEXT",
            "ALTER TABLE customers ADD COLUMN zip_code TEXT",
        ]:
            try:
                con.execute(ddl)
            except Exception:
                pass  # column already exists
        _seed(con)


# Run on import
init_db()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_order(order_id: str) -> dict | None:
    """Return full order row as dict, or None if not found."""
    with _conn() as con:
        row = con.execute(
            "SELECT o.*, c.name AS customer_name, c.email AS customer_email, c.zip_code AS customer_zip "
            "FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
            "WHERE o.order_id = ?",
            (order_id.upper(),),
        ).fetchone()
    return dict(row) if row else None


def get_order_by_confirmation(confirmation_number: str) -> dict | None:
    """Return full order row by confirmation number, or None if not found."""
    with _conn() as con:
        row = con.execute(
            "SELECT o.*, c.name AS customer_name, c.email AS customer_email, c.zip_code AS customer_zip "
            "FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
            "WHERE UPPER(o.confirmation_number) = ?",
            (confirmation_number.strip().upper(),),
        ).fetchone()
    return dict(row) if row else None


def get_order_by_reference(reference: str) -> dict | None:
    """Look up an order by either order ID (e.g. B1015) or confirmation number (e.g. CF-A7K2M)."""
    ref = reference.strip().upper()
    # Confirmation numbers start with CF-
    if ref.startswith("CF-"):
        return get_order_by_confirmation(ref)
    # Otherwise treat as order ID
    return get_order(ref)


def get_return_for_order(order_id: str) -> dict | None:
    """Return the return record for an order, if any."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM returns WHERE order_id = ?", (order_id.upper(),)
        ).fetchone()
    return dict(row) if row else None


def create_return(order_id: str, customer_id: str, reason: str, refund_amount: float) -> dict:
    """Insert a new return record and return confirmation details."""
    import hashlib, datetime
    return_id = "R" + hashlib.md5(order_id.encode()).hexdigest()[:5].upper()
    today = datetime.date.today().isoformat()
    refund_status = f"Refund of ${refund_amount:.2f} will be issued to original payment method within 3–5 business days"
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO returns VALUES (?,?,?,?,?,?,?,?)",
            (return_id, order_id.upper(), customer_id, reason,
             "Approved", today, refund_amount, refund_status),
        )
        # Log interaction
        iid = "I" + hashlib.md5((order_id + today).encode()).hexdigest()[:5].upper()
        con.execute(
            "INSERT OR IGNORE INTO customer_interactions VALUES (?,?,?,?,?)",
            (iid, customer_id, today, "return",
             f"Return initiated for order {order_id}. Reason: {reason}."),
        )
    return {
        "return_id": return_id,
        "order_id": order_id.upper(),
        "status": "Approved",
        "refund_amount": f"${refund_amount:.2f}",
        "refund_status": refund_status,
        "return_date": today,
    }


def cancel_order(order_id: str, customer_name: str) -> dict:
    """
    Cancel a Processing order after verifying the customer's full name.
    Returns a result dict with success/failure details.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT o.*, c.name AS customer_name, c.email AS customer_email "
            "FROM orders o JOIN customers c ON o.customer_id = c.customer_id "
            "WHERE o.order_id = ?",
            (order_id.upper(),),
        ).fetchone()

    if not row:
        return {"success": False, "reason": "order_not_found"}

    order = dict(row)

    if order["customer_name"].lower() != customer_name.strip().lower():
        return {"success": False, "reason": "name_mismatch"}

    if order["status"] != "Processing":
        return {"success": False, "reason": "not_cancellable", "status": order["status"]}

    with _conn() as con:
        con.execute(
            "UPDATE orders SET status = 'Cancelled' WHERE order_id = ?",
            (order_id.upper(),),
        )

    return {
        "success": True,
        "order_id": order_id.upper(),
        "book_title": order["book_title"],
        "customer_id": order["customer_id"],
        "customer_name": order["customer_name"],
        "customer_email": order["customer_email"],
        "total_amount": order["total_amount"],
        "refund_note": "A full refund will be issued to your original payment method within 3–5 business days.",
    }


def log_interaction(customer_id: str, interaction_type: str, summary: str) -> str:
    """Insert a timestamped interaction record. Returns the new interaction ID."""
    import hashlib, datetime
    ts = datetime.datetime.now().isoformat()
    iid = "I" + hashlib.md5((customer_id + ts).encode()).hexdigest()[:7].upper()
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO customer_interactions VALUES (?,?,?,?,?)",
            (iid, customer_id, ts[:10], interaction_type, summary),
        )
    return iid


def get_customer_by_email(email: str) -> dict | None:
    """Return customer row by email, or None."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM customers WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone()
    return dict(row) if row else None


def get_orders_for_customer(email: str) -> list[dict]:
    """Return all orders for a customer identified by email."""
    with _conn() as con:
        rows = con.execute(
            "SELECT o.* FROM orders o "
            "JOIN customers c ON o.customer_id = c.customer_id "
            "WHERE LOWER(c.email) = LOWER(?)",
            (email,),
        ).fetchall()
    return [dict(r) for r in rows]
