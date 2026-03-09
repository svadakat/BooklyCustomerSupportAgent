"""
kb.py — Chroma vector knowledge base for Bookly support policies.
Six policy documents covering shipping, returns, account security,
membership, digital purchases, and payment.
"""
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ---------------------------------------------------------------------------
# Policy documents
# ---------------------------------------------------------------------------

DOCUMENTS = [
    {
        "id": "shipping_policy",
        "text": """Bookly Shipping Policy:
Standard shipping takes 3–5 business days and costs $4.99.
Express shipping takes 1–2 business days and costs $9.99.
Overnight shipping (order by noon EST) costs $19.99.
Free standard shipping is available on all orders over $35.
We ship to all 50 US states and US territories.
International shipping is available to Canada, UK, Australia, and select EU countries for $19.99; delivery takes 7–14 business days.
International orders may be subject to customs duties paid by the recipient.
Orders placed before 2 PM EST on weekdays ship the same day.
Weekend and holiday orders ship on the next business day.
A tracking number is emailed within 24 hours of shipment.
Carriers used: UPS, FedEx, and USPS depending on destination and service level.
Bookly is not responsible for carrier delays, weather events, or customs holds.
If your tracking shows delivered but you haven't received the package, please wait 24 hours then contact support.""",
    },
    {
        "id": "return_and_refund_policy",
        "text": """Bookly Return and Refund Policy:
Physical books may be returned within 30 days of the purchase date for a full refund.
Items must be in original, unread condition — no damage, highlighting, writing, or broken spines.
Digital purchases (eBooks and audiobooks) are non-refundable once the file has been downloaded.
To start a return, contact Bookly support and provide your order ID.
For defective, damaged, or incorrectly shipped items, Bookly provides a prepaid return shipping label at no cost.
For all other returns (change of mind, duplicate order), the customer covers return shipping costs.
Refunds are processed within 3–5 business days of receiving the returned item.
Refunds are issued to the original payment method only; credit card refunds may take an additional 3–5 banking days to appear.
Gift purchases returned without a receipt receive store credit at the item's current listed price.
Bundle orders must be returned as a complete set; partial bundle returns are not accepted.
Items purchased during a sale or with a promotional code are refunded at the discounted price paid, not the full price.""",
    },
    {
        "id": "account_and_password_security",
        "text": """Bookly Account and Password Security:
To reset your password: visit bookly.com, click 'Sign In', then 'Forgot Password'.
Enter the email address on your account and click 'Send Reset Link'.
A password reset email arrives within 5 minutes; check spam/junk if not seen.
Reset links expire after 24 hours — request a new one if it has expired.
If you no longer have access to your registered email, contact support with your name, order history, and billing address to verify identity.
Bookly will NEVER ask for your password via email, chat, phone, or social media.
We recommend passwords of at least 12 characters mixing uppercase, lowercase, numbers, and symbols.
Two-factor authentication (2FA) is available in Account Settings — strongly recommended.
Your account locks after 5 consecutive failed login attempts; wait 15 minutes or use the reset flow.
To close your account permanently, contact support — account closure is irreversible and order history will be deleted after 90 days.""",
    },
    {
        "id": "bookclub_membership_rewards",
        "text": """Bookly BookClub Membership and Rewards Program:
BookClub is free to join — sign up in your account settings.
Earn 1 point for every $1 spent on physical books; 0.5 points per $1 on eBooks.
100 points = $1 in store credit redeemable on any future order.
Bonus points: 200 points for signing up, 50 points on your birthday month.
Points expire after 12 months of account inactivity.
BookClub Silver (500+ lifetime points): 10% discount on all orders, free standard shipping on orders over $25.
BookClub Gold (2000+ lifetime points): 15% discount, free express shipping, advance access to new releases.
Points cannot be transferred between accounts or redeemed for cash.
Promotional orders and discounted purchases earn reduced points based on amount actually paid.
To check your points balance, log in and visit My Account > BookClub Rewards.""",
    },
    {
        "id": "ebook_and_digital_policy",
        "text": """Bookly eBook and Digital Purchase Policy:
eBooks and audiobooks are delivered as DRM-protected files compatible with the Bookly app (iOS, Android, Web).
You may access your digital library on up to 5 devices simultaneously.
Digital purchases are non-refundable once the file has been downloaded or streamed.
If a file is corrupted or fails to download, contact support within 7 days for a replacement.
eBooks can be gifted — the recipient receives a redemption code by email.
Your digital library is tied to your account email; changing your email requires contacting support.
Bookly does not sell or transfer eBook licenses; purchases are for personal use only.
Pre-orders for upcoming eBook releases are charged on the release date.
If an eBook price drops within 7 days of purchase, contact support for a price-match credit.""",
    },
    {
        "id": "order_cancellation_and_changes",
        "text": """Bookly Order Cancellation and Changes Policy:
Orders can be cancelled or changed only while their status is 'Processing' (not yet shipped).
To cancel or change an order, contact Bookly support and provide your order ID and full name as on the order.
Once an order has shipped, it cannot be cancelled — start a return after delivery instead.
Eligible changes while in Processing: shipping method upgrade, shipping address correction, or quantity adjustment (subject to availability).
Cancelled orders receive a full refund to the original payment method within 3–5 business days.
Pre-orders can be cancelled any time before the release date.
Bundle orders must be cancelled as a complete set; individual items within a bundle cannot be cancelled separately.
Bookly cannot guarantee changes will be applied if the order is being prepared for shipment — contact support as soon as possible.""",
    },
    {
        "id": "payment_and_billing",
        "text": """Bookly Payment and Billing Policy:
Accepted payment methods: Visa, Mastercard, American Express, Discover, PayPal, Apple Pay, Google Pay, and Bookly Gift Cards.
All prices are in USD and include applicable sales tax at checkout.
Bookly does not store full credit card numbers; payment data is handled by PCI-compliant processors.
Gift cards are available in denominations of $10, $25, $50, and $100.
Gift cards do not expire and cannot be exchanged for cash.
Split payments (e.g., part gift card, part credit card) are supported at checkout.
If a charge appears on your statement that you don't recognise, contact support within 60 days.
Pre-orders are not charged until the item ships.
Subscription products (if applicable) renew automatically; cancel anytime in Account Settings before the renewal date.""",
    },
]

# ---------------------------------------------------------------------------
# Singleton collection
# ---------------------------------------------------------------------------

_collection = None


def _build_collection():
    client = chromadb.EphemeralClient()
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = client.create_collection(
        name="bookly_kb",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    collection.add(
        ids=[doc["id"] for doc in DOCUMENTS],
        documents=[doc["text"] for doc in DOCUMENTS],
        metadatas=[{"source": doc["id"]} for doc in DOCUMENTS],
    )
    return collection


def get_collection():
    global _collection
    if _collection is None:
        _collection = _build_collection()
    return _collection


# ---------------------------------------------------------------------------
# Public search interface
# ---------------------------------------------------------------------------

def search(query: str, n_results: int = 2) -> list[dict]:
    """Semantic search — returns up to n_results docs sorted by relevance."""
    collection = get_collection()
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, len(DOCUMENTS)),
    )
    return [
        {
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "distance": results["distances"][0][i],
        }
        for i in range(len(results["ids"][0]))
    ]
