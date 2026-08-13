"""Small regression tests for the safe payment and delivery entry points."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

import mini_app
from services.coupon_service import deliver_coupon


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


class CheckoutSafetyTests(unittest.TestCase):
    def test_delivery_service_is_importable(self):
        self.assertTrue(callable(deliver_coupon))

    def test_gateway_setup_failure_fails_order_and_refunds_wallet(self):
        coupon = SimpleNamespace(coupon_name="Test coupon", selling_price=10, sold=False)
        order = SimpleNamespace(payable_amount=7)
        request = FakeRequest({"coupon_id": 1, "quantity": 1, "customer_phone": "9876543210"})

        with (
            patch.object(mini_app, "telegram_user", new=AsyncMock(return_value={"id": 10})),
            patch.object(mini_app, "get_coupon_by_id", return_value=coupon),
            patch.object(mini_app, "get_coupon_stock", return_value=1),
            patch.object(mini_app, "get_bulk_buyer_price", return_value=None),
            patch.object(mini_app, "create_order", return_value="BBTEST"),
            patch.object(mini_app, "get_order_by_id", return_value=order),
            patch.object(mini_app, "create_cashfree_payment_link", return_value={"error": "Gateway unavailable"}),
            patch.object(mini_app, "refund_order_wallet_if_needed", return_value=True) as refund,
            patch.object(mini_app, "update_order_status") as update,
        ):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(mini_app.checkout(request))

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("wallet credit was returned", raised.exception.detail)
        refund.assert_called_once_with("BBTEST", "Payment setup refund")
        update.assert_called_once_with("BBTEST", "FAILED")
