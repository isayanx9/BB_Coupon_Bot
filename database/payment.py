import requests

from config import (
    CASHFREE_CLIENT_ID,
    CASHFREE_CLIENT_SECRET,
    CASHFREE_ENV,
)


def create_cashfree_payment_link(order_id, amount, customer_id):
    base_url = (
        "https://sandbox.cashfree.com/pg/orders"
        if CASHFREE_ENV == "sandbox"
        else "https://api.cashfree.com/pg/orders"
    )

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": CASHFREE_CLIENT_ID,
        "x-client-secret": CASHFREE_CLIENT_SECRET,
        "x-api-version": "2023-08-01",
    }

    payload = {
        "order_id": order_id,
        "order_amount": amount,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": str(customer_id),
            "customer_phone": "9999999999",
        },
    }

    response = requests.post(
        base_url,
        json=payload,
        headers=headers,
        timeout=20,
    )

    try:
        return response.json()
    except ValueError:
        return {
            "error": "Invalid response from Cashfree",
            "status_code": response.status_code,
            "body": response.text,
        }
