"""
tools.py — Bookly support tools backed by the SQLite database (db.py).
"""

from db import (
    get_order,
    get_return_for_order,
    create_return,
    cancel_order as db_cancel_order,
    get_customer_by_email,
    log_interaction,
)
from email_utils import send_email


def get_order_status(order_id: str) -> dict:
    """Return order status, carrier, and tracking from the database."""
    order = get_order(order_id)
    if not order:
        return {
            "found": False,
            "message": (
                f"No order with ID '{order_id}' was found. "
                "Please double-check the order ID — it should look like B1001. "
                "You can find it in your confirmation email."
            ),
        }

    log_interaction(
        customer_id=order["customer_id"],
        interaction_type="support",
        summary=f"Customer checked status of order {order_id} ({order['book_title']}). Status: {order['status']}.",
    )

    result = {
        "found": True,
        "order_id": order["order_id"],
        "book_title": order["book_title"],
        "book_author": order["book_author"],
        "quantity": order["quantity"],
        "total_amount": f"${order['total_amount']:.2f}",
        "status": order["status"],
        "order_date": order["order_date"],
        "delivery_estimate": order["delivery_estimate"] or "To be confirmed",
        "carrier": order["carrier"] or "Not yet assigned",
        "tracking_number": order["tracking_number"] or "Not yet assigned",
        "customer_name": order["customer_name"],
    }

    # Include active return info if one exists
    ret = get_return_for_order(order_id)
    if ret:
        result["return"] = {
            "return_id": ret["return_id"],
            "status": ret["status"],
            "refund_status": ret["refund_status"],
        }

    return result


def initiate_refund(order_id: str) -> dict:
    """
    Initiate a return/refund for an order.
    Returns error dict if the order is not found or already has a return.
    """
    order = get_order(order_id)
    if not order:
        return {
            "success": False,
            "message": (
                f"Order '{order_id}' not found. "
                "Please verify the order ID and try again."
            ),
        }

    if order["status"] not in ("Delivered", "Shipped", "Out for Delivery"):
        return {
            "success": False,
            "message": (
                f"Order {order_id} has status '{order['status']}' and is not yet eligible for a return. "
                "Returns can be requested once an order has shipped."
            ),
        }

    existing = get_return_for_order(order_id)
    if existing:
        return {
            "success": False,
            "already_exists": True,
            "return_id": existing["return_id"],
            "status": existing["status"],
            "message": (
                f"A return for order {order_id} already exists "
                f"(Return ID: {existing['return_id']}, Status: {existing['status']}). "
                f"{existing['refund_status']}."
            ),
        }

    confirmation = create_return(
        order_id=order_id,
        customer_id=order["customer_id"],
        reason="Customer-requested return via support chat",
        refund_amount=order["total_amount"],
    )
    confirmation["success"] = True
    confirmation["book_title"] = order["book_title"]
    confirmation["message"] = (
        f"Your return for '{order['book_title']}' (Order {order_id}) has been approved. "
        f"A refund of ${order['total_amount']:.2f} will be issued to your original payment method "
        f"within 3–5 business days. Return ID: {confirmation['return_id']}."
    )

    # Send confirmation email to customer
    email_result = send_email(
        to_email=order["customer_email"],
        subject=f"Bookly Return Confirmed — Order {order_id}",
        body=(
            f"Hi {order['customer_name']},\n\n"
            f"Your return request for '{order['book_title']}' (Order {order_id}) has been approved.\n\n"
            f"Return ID:       {confirmation['return_id']}\n"
            f"Refund Amount:   ${order['total_amount']:.2f}\n"
            f"Refund Timeline: 3–5 business days to your original payment method\n\n"
            f"No further action is needed from you. "
            f"If you have questions, visit bookly.com/support.\n\n"
            f"Thank you for shopping with Bookly!\n"
            f"— The Bookly Team"
        ),
    )
    confirmation["email_sent"] = email_result.get("sent", False)

    return confirmation


def cancel_order(order_id: str, customer_name: str) -> dict:
    """
    Cancel a Processing order after verifying customer name.
    Logs the interaction and sends a confirmation email.
    """
    result = db_cancel_order(order_id=order_id, customer_name=customer_name)

    if not result["success"]:
        reason = result["reason"]
        if reason == "order_not_found":
            return {
                "success": False,
                "message": (
                    f"No order '{order_id}' was found. "
                    "Please double-check the order ID — it should look like B1001."
                ),
            }
        if reason == "name_mismatch":
            return {
                "success": False,
                "message": (
                    "The name provided doesn't match what's on the order. "
                    "Please use the full name exactly as it appears on your confirmation email."
                ),
            }
        if reason == "not_cancellable":
            status = result.get("status", "unknown")
            tip = (
                "You can request a return after it's delivered."
                if status in ("Shipped", "Out for Delivery", "Delivered")
                else "Please contact support for further assistance."
            )
            return {
                "success": False,
                "message": (
                    f"Order {order_id} is currently '{status}' and can no longer be cancelled. {tip}"
                ),
            }

    log_interaction(
        customer_id=result["customer_id"],
        interaction_type="cancellation",
        summary=f"Order {order_id} ({result['book_title']}) cancelled by customer request.",
    )

    email_result = send_email(
        to_email=result["customer_email"],
        subject=f"Bookly Order Cancelled — Order {order_id}",
        body=(
            f"Hi {result['customer_name']},\n\n"
            f"Your order {order_id} for '{result['book_title']}' has been successfully cancelled.\n\n"
            f"Refund: ${result['total_amount']:.2f} will be returned to your original payment method "
            f"within 3–5 business days.\n\n"
            f"If you change your mind, you're welcome to place a new order at bookly.com.\n\n"
            f"— The Bookly Team"
        ),
    )

    return {
        "success": True,
        "order_id": order_id.upper(),
        "book_title": result["book_title"],
        "message": (
            f"Order {order_id} for '{result['book_title']}' has been cancelled. "
            f"A full refund of ${result['total_amount']:.2f} will be issued within 3–5 business days."
        ),
        "email_sent": email_result.get("sent", False),
    }


def reset_password(email: str) -> dict:
    """Send a password reset link. Works whether or not the account exists (security best practice)."""
    customer = get_customer_by_email(email)
    base = {
        "email": email,
        "status": "Reset link sent",
        "expires_in": "24 hours",
        "message": (
            f"If an account exists for {email}, a password reset link has been sent. "
            "Please check your inbox and spam folder. The link expires in 24 hours."
        ),
    }
    if customer:
        base["account_found"] = True
        base["customer_name"] = customer["name"]

        log_interaction(
            customer_id=customer["customer_id"],
            interaction_type="support",
            summary=f"Password reset requested for {email}.",
        )

        email_result = send_email(
            to_email=email,
            subject="Bookly — Password Reset Request",
            body=(
                f"Hi {customer['name']},\n\n"
                f"We received a request to reset your Bookly account password.\n\n"
                f"Click the link below to set a new password (expires in 24 hours):\n"
                f"https://bookly.com/reset-password?token=<secure-token>\n\n"
                f"If you didn't request this, you can safely ignore this email — "
                f"your password will not change.\n\n"
                f"— The Bookly Team"
            ),
        )
        base["email_sent"] = email_result.get("sent", False)

    return base
