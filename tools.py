"""
tools.py — Bookly support tools backed by the SQLite database (db.py).
"""

from db import (
    get_order_by_reference,
    get_return_for_order,
    create_return,
    cancel_order as db_cancel_order,
    log_interaction,
)
from email_utils import send_email


def _not_found() -> dict:
    return {
        "found": False,
        "message": (
            "No order was found matching that reference. "
            "Please double-check your order ID (e.g. B1015) or confirmation number (e.g. CF-A7K2M)."
        ),
    }


def _credential_error(field: str) -> dict:
    return {
        "found": False,
        "message": (
            f"The {field} you provided doesn't match our records for that order. "
            "Please double-check and try again."
        ),
    }


def get_order_status(order_reference: str, full_name: str, zip_code: str) -> dict:
    """Return order status, carrier, and tracking from the database."""
    order = get_order_by_reference(order_reference)
    if not order:
        return _not_found()

    if order.get("customer_name", "").strip().lower() != full_name.strip().lower():
        return _credential_error("full name")
    if (order.get("customer_zip") or "").strip() != zip_code.strip():
        return _credential_error("zip code")

    order_id = order["order_id"]
    log_interaction(
        customer_id=order["customer_id"],
        interaction_type="support",
        summary=f"Customer checked status of order {order_id} ({order['book_title']}). Status: {order['status']}.",
    )

    result = {
        "found": True,
        "order_id": order_id,
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

    ret = get_return_for_order(order_id)
    if ret:
        result["return"] = {
            "return_id": ret["return_id"],
            "status": ret["status"],
            "refund_status": ret["refund_status"],
        }

    return result


def initiate_refund(order_reference: str, full_name: str, zip_code: str) -> dict:
    """
    Initiate a return/refund for an order.
    Returns error dict if not found, credentials don't match, or a return already exists.
    """
    order = get_order_by_reference(order_reference)
    if not order:
        return {"success": False, "message": _not_found()["message"]}

    if order.get("customer_name", "").strip().lower() != full_name.strip().lower():
        return {"success": False, "message": "The full name doesn't match our records for that order."}
    if (order.get("customer_zip") or "").strip() != zip_code.strip():
        return {"success": False, "message": "The zip code doesn't match our records for that order."}

    order_id = order["order_id"]

    if order["status"] != "Delivered":
        return {
            "success": False,
            "message": (
                f"Order {order_id} has status '{order['status']}' and is not yet eligible for a return. "
                "Returns can only be requested after the order has been delivered."
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


def cancel_order(order_reference: str, full_name: str, zip_code: str) -> dict:
    """
    Cancel a Processing order after verifying order reference, full name, and zip code.
    Logs the interaction and sends a confirmation email.
    """
    order = get_order_by_reference(order_reference)
    if not order:
        return {"success": False, "message": _not_found()["message"]}

    if order.get("customer_name", "").strip().lower() != full_name.strip().lower():
        return {"success": False, "message": "The full name doesn't match our records for that order."}
    if (order.get("customer_zip") or "").strip() != zip_code.strip():
        return {"success": False, "message": "The zip code doesn't match our records for that order."}

    order_id = order["order_id"]
    result = db_cancel_order(order_id=order_id, customer_name=full_name)

    if not result["success"]:
        reason = result["reason"]
        if reason == "not_cancellable":
            status = result.get("status", "unknown")
            tip = (
                "You can request a return after it's delivered."
                if status in ("Shipped", "Out for Delivery", "Delivered")
                else "Please contact support for further assistance."
            )
            return {
                "success": False,
                "message": f"Order {order_id} is currently '{status}' and can no longer be cancelled. {tip}",
            }
        return {"success": False, "message": "Unable to cancel the order. Please contact support."}

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
        "order_id": order_id,
        "book_title": result["book_title"],
        "message": (
            f"Order {order_id} for '{result['book_title']}' has been cancelled. "
            f"A full refund of ${result['total_amount']:.2f} will be issued within 3–5 business days."
        ),
        "email_sent": email_result.get("sent", False),
    }
