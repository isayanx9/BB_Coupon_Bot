import requests
from datetime import datetime, timedelta, timezone

from config import (
    CASHFREE_CLIENT_ID,
    CASHFREE_CLIENT_SECRET,
    CASHFREE_CUSTOMER_PHONE,
    CASHFREE_ENV,
    PUBLIC_BASE_URL,
)


def create_cashfree_payment_link(order_id, amount, customer_id):
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

    payload = {
        "order_id": order_id,
        "order_amount": float(amount),
        "order_currency": "INR",
        "order_expiry_time": (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        ).isoformat(),
        "customer_details": {
            "customer_id": str(customer_id),
            "customer_name": f"Telegram {customer_id}",
            "customer_phone": CASHFREE_CUSTOMER_PHONE,
        },
        "order_meta": {
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
        data.setdefault("error", "Cashfree rejected the order")
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
