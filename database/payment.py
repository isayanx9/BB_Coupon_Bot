import requests
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from config import (
    CASHFREE_CLIENT_ID,
    CASHFREE_CLIENT_SECRET,
    CASHFREE_CUSTOMER_PHONE,
    CASHFREE_ENV,
    PAYMENT_EXPIRY_MINUTES,
    PUBLIC_BASE_URL,
)


def verify_cashfree_webhook_signature(raw_body, signature, timestamp):
    """Validate Cashfree's HMAC-SHA256 signature against the exact raw body."""
    if not raw_body or not signature or not timestamp or not CASHFREE_CLIENT_SECRET:
        return False

    signed_payload = str(timestamp).encode("utf-8") + raw_body
    expected = base64.b64encode(
        hmac.new(
            CASHFREE_CLIENT_SECRET.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def create_cashfree_payment_link(order_id, amount, customer_id, customer_phone=None):
    base_url = (
        "https://sandbox.cashfree.com/pg/orders"
        if CASHFREE_ENV == "sandbox"
        else "https://api.cashfree.com/pg/orders"
    )

    if not CASHFREE_CLIENT_ID or not CASHFREE_CLIENT_SECRET:
        return {
            "error": "Cashfree credentials are missing",
            "hint": "Set CASHFREE_CLIENT_ID and CASHFREE_CLIENT_SECRET in Railway Variables.",
        }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": CASHFREE_CLIENT_ID,
        "x-client-secret": CASHFREE_CLIENT_SECRET,
        "x-api-version": "2023-08-01",
    }

    # A unique verified customer phone prevents Cashfree from treating every
    # buyer as the same profile and reusing previously saved UPI suggestions.
    phone = str(customer_phone or CASHFREE_CUSTOMER_PHONE).strip()
    if not phone.isdigit() or len(phone) != 10 or phone[0] not in "6789":
        return {"error": "A valid 10-digit Indian mobile number is required for secure UPI checkout."}

    payload = {
        "order_id": order_id,
        "order_amount": float(amount),
        "order_currency": "INR",
        "order_expiry_time": (
            datetime.now(timezone.utc)
            + timedelta(minutes=PAYMENT_EXPIRY_MINUTES)
        ).isoformat(),
        "customer_details": {
            "customer_id": str(customer_id),
            "customer_name": f"Telegram {customer_id}",
            "customer_phone": phone,
        },
        "order_meta": {
            # Cashfree's hosted checkout can open any supported UPI/payment
            # app. Its return page moves the buyer back into Telegram, where
            # the authenticated Mini App resumes payment verification.
            "return_url": f"{PUBLIC_BASE_URL}/payment-result/{order_id}?status={{order_status}}",
            "notify_url": f"{PUBLIC_BASE_URL}/webhook/cashfree",
        },
    }

    try:
        response = requests.post(
            base_url,
            json=payload,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as error:
        return {
            "error": "Could not connect to Cashfree",
            "hint": str(error),
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "error": "Invalid response from Cashfree",
            "status_code": response.status_code,
            "body": response.text,
        }

    if response.status_code >= 400:
        # Pass only Cashfree's public validation message to the storefront.
        # Do not include request headers, secrets, or raw customer payloads.
        public_message = data.get("message") or data.get("error_description") or data.get("type")
        data["error"] = str(public_message or "Cashfree rejected the order")[:300]
        data.setdefault("status_code", response.status_code)

    return data


def get_cashfree_order_status(order_id):
    base_url = (
        "https://sandbox.cashfree.com/pg/orders"
        if CASHFREE_ENV == "sandbox"
        else "https://api.cashfree.com/pg/orders"
    )

    if not CASHFREE_CLIENT_ID or not CASHFREE_CLIENT_SECRET:
        return {
            "error": "Cashfree credentials are missing",
        }

    headers = {
        "accept": "application/json",
        "x-client-id": CASHFREE_CLIENT_ID,
        "x-client-secret": CASHFREE_CLIENT_SECRET,
        "x-api-version": "2023-08-01",
    }

    try:
        response = requests.get(
            f"{base_url}/{order_id}",
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as error:
        return {
            "error": "Could not connect to Cashfree",
            "hint": str(error),
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "error": "Invalid response from Cashfree",
            "status_code": response.status_code,
            "body": response.text,
        }

    if response.status_code >= 400:
        data.setdefault("error", "Cashfree status check failed")
        data.setdefault("status_code", response.status_code)

    return data
