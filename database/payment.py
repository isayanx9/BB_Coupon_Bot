import requests

from config import (
    CASHFREE_CLIENT_ID,
    CASHFREE_CLIENT_SECRET
)


def create_cashfree_payment_link(
    order_id,
    amount,
    customer_id
):

    url = "https://api.cashfree.com/pg/orders"

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": CASHFREE_CLIENT_ID,
        "x-client-secret": CASHFREE_CLIENT_SECRET,
        "x-api-version": "2023-08-01"
    }

    payload = {
        "order_id": order_id,
        "order_amount": amount,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": str(customer_id),
            "customer_phone": "9999999999"
        }
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers
    )

    data = response.json()

    print(data)

    return data