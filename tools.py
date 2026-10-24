"""Dewey's fictional bookstore data and deterministic return rules."""

from copy import deepcopy
from datetime import date


# A fixed clock makes the demo and its 30-day policy reproducible next month, too.
DEMO_DATE = date(2026, 10, 24)
RETURN_WINDOW_DAYS = 30

ORDERS = {
    "BK-1001": {
        "order_id": "BK-1001",
        "status": "shipped",
        "estimated_delivery": "2026-10-28",
        "delivered_on": None,
        "items": [
            {"item_id": "BK-1001-1", "title": "A Psalm for the Wild-Built"},
            {"item_id": "BK-1001-2", "title": "The Bookshop on the Corner"},
        ],
    },
    "BK-1002": {
        "order_id": "BK-1002",
        "status": "delivered",
        "estimated_delivery": None,
        "delivered_on": "2026-10-18",
        "items": [
            {"item_id": "BK-1002-1", "title": "The Hobbit"},
            {"item_id": "BK-1002-2", "title": "Piranesi"},
        ],
    },
    "BK-1003": {
        "order_id": "BK-1003",
        "status": "delivered",
        "estimated_delivery": None,
        "delivered_on": "2026-09-10",
        "items": [{"item_id": "BK-1003-1", "title": "The Secret History"}],
    },
}


def failure(code: str, message: str) -> dict:
    """Return a predictable failure that the agent and UI can explain honestly."""
    return {"ok": False, "error": code, "message": message}


def clean_id(value: str) -> str:
    """Normalize identifiers without accepting non-text or excessively long inputs."""
    return value.strip().upper() if isinstance(value, str) and len(value) <= 100 else ""


def get_order(order_id: str) -> dict:
    """Look up a fictional order and return a copy of its authoritative details."""
    order = ORDERS.get(clean_id(order_id))
    if order is None:
        return failure("order_not_found", "Order not found. Please check the order number.")
    return {"ok": True, "order": deepcopy(order)}


def check_return_eligibility(order_id: str, item_id: str, created_returns: list) -> dict:
    """Check item membership, delivery, return window, and previously created returns."""
    result = get_order(order_id)
    if not result["ok"]:
        return result
    order = result["order"]
    item = next((book for book in order["items"] if book["item_id"] == clean_id(item_id)), None)
    if item is None:
        return failure("item_not_found", "That book is not part of this order.")

    details = {
        "ok": True,
        "order_id": order["order_id"],
        "item_id": item["item_id"],
        "title": item["title"],
        "demo_date": DEMO_DATE.isoformat(),
    }
    if any(record["order_id"] == order["order_id"] and record["item_id"] == item["item_id"]
           for record in created_returns):
        return {**details, "eligible": False, "message": "A return request already exists for this book."}
    if order["status"] != "delivered" or not order["delivered_on"]:
        return {**details, "eligible": False, "message": "Only delivered books can be returned."}

    days_since_delivery = (DEMO_DATE - date.fromisoformat(order["delivered_on"])).days
    if not 0 <= days_since_delivery <= RETURN_WINDOW_DAYS:
        return {
            **details,
            "eligible": False,
            "message": "This book is outside the 30-day return window or has a future delivery date.",
        }
    return {**details, "eligible": True, "message": "This delivered book is within the 30-day return window."}


def prepare_return(order_id: str, item_id: str, reason: str, state: dict) -> dict:
    """Validate a return proposal and store the exact details awaiting a button click."""
    state["pending_return"] = None
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        return failure("invalid_reason", "Please give a return reason of 1 to 1,000 characters.")
    eligibility = check_return_eligibility(order_id, item_id, state["created_returns"])
    if not eligibility["ok"]:
        return eligibility
    if not eligibility["eligible"]:
        return failure("not_eligible", eligibility["message"])

    # Store canonical tool data separately: conversation text must never authorize a return.
    pending = {
        "order_id": eligibility["order_id"],
        "item_id": eligibility["item_id"],
        "title": eligibility["title"],
        "reason": reason.strip(),
    }
    state["pending_return"] = pending
    return {"ok": True, "pending_return": deepcopy(pending), "message": "Awaiting confirmation in the UI. No return has been created."}


def create_return(state: dict) -> dict:
    """Create one return from application-managed state after a customer button click."""
    pending = state["pending_return"]
    if pending is None:
        return failure("no_pending_return", "There is no return awaiting confirmation.")

    # Revalidate at execution time, rather than trusting an earlier eligibility result.
    eligibility = check_return_eligibility(pending["order_id"], pending["item_id"], state["created_returns"])
    state["pending_return"] = None
    if not eligibility["ok"]:
        return eligibility
    if not eligibility["eligible"]:
        return failure("not_eligible", eligibility["message"])

    record = {
        **pending,
        "title": eligibility["title"],
        "reference": f"RET-{len(state['created_returns']) + 1:04d}",
        "created_on": DEMO_DATE.isoformat(),
    }
    state["created_returns"].append(record)
    return {"ok": True, "return_request": deepcopy(record), "message": "Return request created. No refund has been issued and no shipping label has been generated."}
