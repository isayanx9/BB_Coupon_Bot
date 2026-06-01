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

    url = "https://api.cashfree.com/pg/links"

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": CASHFREE_CLIENT_ID,
        "x-client-secret": CASHFREE_CLIENT_SECRET,
        "x-api-version": "2023-08-01"
    }

    payload = {
        "customer_details": {
            "customer_name": f"User_{customer_id}",
            "customer_phone": "9999999999"
        },
        "link_amount": amount,
        "link_currency": "INR",
        "link_id": order_id,
        "link_purpose": f"Coupon Purchase {order_id}"
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers
    )

    data = response.json()

    print("PAYMENT LINK RESPONSE:")
    print(data)

    return data