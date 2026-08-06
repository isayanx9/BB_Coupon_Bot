"""Telegram Mini App storefront and authenticated API.

The browser is intentionally never trusted with a Telegram user id, prices,
stock, or payment status.  Every API call validates Telegram WebApp initData.
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import BOT_TOKEN, CASHFREE_ENV
from database.crud import (
    add_wallet_credit,
    create_order,
    create_support_ticket,
    claim_order_delivery,
    get_bulk_buyer_price,
    get_coupon_by_id,
    get_coupon_stock,
    get_coupon_type_options,
    get_referral_count,
    get_user_orders,
    get_wallet_balance,
    get_wallet_transactions,
    is_user_banned,
    save_payment_session,
    save_order_coupon_code,
    release_order_delivery_claim,
    track_user,
    update_delivery_status,
    update_order_status,
)
from database.payment import create_cashfree_payment_link
from services.coupon_service import deliver_coupons

ROOT = Path(__file__).parent / "mini_app"
router = APIRouter()
router.mount("/mini/static", StaticFiles(directory=ROOT), name="mini-static")


def telegram_user(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        raise HTTPException(401, "Open this shop from Telegram.")

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash or not BOT_TOKEN:
        raise HTTPException(401, "Invalid Telegram session.")

    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(401, "Telegram session could not be verified.")

    try:
        user = json.loads(values["user"])
    except (KeyError, json.JSONDecodeError) as error:
        raise HTTPException(401, "Telegram user is missing.") from error

    user_id = int(user["id"])
    if is_user_banned(user_id):
        raise HTTPException(403, "This account is restricted.")
    track_user(user_id, user.get("username"))
    return user


def serialize_order(order):
    expiry = order.payment_expires_at
    return {
        "id": order.order_id,
        "coupon_name": order.coupon_name,
        "amount": order.amount,
        "wallet_used": order.wallet_used or 0,
        "payable_amount": order.payable_amount or 0,
        "quantity": order.quantity or 1,
        "payment_status": order.payment_status,
        "delivery_status": order.delivery_status,
        "coupon_code": order.coupon_code if order.delivery_status == "DELIVERED" else None,
        "expires_at": expiry.replace(tzinfo=timezone.utc).isoformat() if expiry else None,
        "created_at": order.created_at.replace(tzinfo=timezone.utc).isoformat() if order.created_at else None,
    }


@router.get("/mini")
async def mini_app_home():
    return FileResponse(ROOT / "index.html", media_type="text/html")


@router.get("/api/mini/bootstrap")
async def bootstrap(request: Request):
    user = telegram_user(request)
    user_id = int(user["id"])
    coupons = get_coupon_type_options()
    for coupon in coupons:
        special_price = get_bulk_buyer_price(user_id, coupon["coupon_name"])
        if special_price is not None:
            coupon["price"] = special_price
    return {
        "user": {"first_name": user.get("first_name", "Friend"), "username": user.get("username")},
        "coupons": coupons,
        "wallet_balance": get_wallet_balance(user_id),
        "referrals": get_referral_count(user_id),
        "orders": [serialize_order(order) for order in get_user_orders(user_id)[:20]],
        "cashfree_mode": CASHFREE_ENV,
    }


@router.post("/api/mini/checkout")
async def checkout(request: Request):
    user = telegram_user(request)
    body = await request.json()
    try:
        coupon_id = int(body["coupon_id"])
        quantity = max(1, min(20, int(body.get("quantity", 1))))
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(422, "Choose a valid coupon and quantity.") from error

    coupon = get_coupon_by_id(coupon_id)
    if not coupon or coupon.sold or get_coupon_stock(coupon.coupon_name) < quantity:
        raise HTTPException(409, "This coupon is no longer available in that quantity.")

    user_id = int(user["id"])
    unit_price = get_bulk_buyer_price(user_id, coupon.coupon_name)
    unit_price = unit_price if unit_price is not None else coupon.selling_price
    order_id = create_order(
        user_id, coupon.coupon_name, int(unit_price) * quantity, use_wallet=True, quantity=quantity
    )
    if not order_id:
        raise HTTPException(500, "Could not create your order. Please try again.")

    from database.crud import get_order_by_id
    order = get_order_by_id(order_id)
    if order.payable_amount == 0:
        # A fully wallet-funded order does not need a gateway callback.  It is
        # still delivered only on the server, with the same stock claim pattern.
        if not claim_order_delivery(order_id):
            raise HTTPException(409, "This order is already being delivered.")
        codes, _ = deliver_coupons(order.coupon_name, quantity)
        if len(codes) != quantity:
            release_order_delivery_claim(order_id)
            add_wallet_credit(user_id, order.wallet_used, f"Wallet refund for {order_id}")
            update_order_status(order_id, "FAILED")
            raise HTTPException(409, "Stock changed while completing your order. Contact support.")
        save_order_coupon_code(order_id, ", ".join(codes))
        update_order_status(order_id, "SUCCESS")
        update_delivery_status(order_id, "DELIVERED")
        return {"order": serialize_order(get_order_by_id(order_id)), "delivered": True}

    payment = create_cashfree_payment_link(order_id, order.payable_amount, user_id)
    session_id = payment.get("payment_session_id")
    if not session_id:
        raise HTTPException(502, payment.get("error") or payment.get("message") or "Cashfree checkout is unavailable.")
    save_payment_session(order_id, session_id)
    return {"order": serialize_order(order), "payment_session_id": session_id}


@router.post("/api/mini/tickets")
async def create_ticket(request: Request):
    user = telegram_user(request)
    body = await request.json()
    subject = str(body.get("subject", "Support request")).strip()
    message = str(body.get("message", "")).strip()
    if len(subject) < 3 or len(message) < 5:
        raise HTTPException(422, "Please add a subject and a short description.")
    ticket_id = create_support_ticket(int(user["id"]), subject, message)
    if not ticket_id:
        raise HTTPException(500, "Could not create the ticket.")
    return {"ok": True, "ticket_id": ticket_id}


@router.get("/api/mini/wallet")
async def wallet(request: Request):
    user = telegram_user(request)
    user_id = int(user["id"])
    return {
        "balance": get_wallet_balance(user_id),
        "transactions": [
            {"amount": tx.amount, "reason": tx.reason, "created_at": tx.created_at.isoformat()}
            for tx in get_wallet_transactions(user_id, limit=20)
        ],
    }
