"""Telegram Mini App storefront and authenticated API.

The browser is intentionally never trusted with a Telegram user id, prices,
stock, or payment status.  Every API call validates Telegram WebApp initData.
"""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import ADMIN_ID, BOT_TOKEN, CASHFREE_ENV, CHANNEL_USERNAME, GROUP_USERNAME
from database.crud import (
    add_wallet_credit,
    add_ticket_reply,
    audit_admin_action,
    create_order,
    create_support_ticket,
    claim_order_delivery,
    expire_order_if_needed,
    get_bulk_buyer_price,
    get_analytics_snapshot,
    get_coupon_by_id,
    get_coupon_stock,
    get_coupon_type_options,
    get_coupon_summary,
    get_order_by_id,
    get_recent_orders,
    get_delivery_reconciliation,
    get_referral_count,
    get_active_flash_sales,
    get_ticket_by_id,
    get_open_tickets,
    get_bot_setting,
    get_user_orders,
    get_user_tickets,
    get_wallet_balance,
    get_wallet_transactions,
    is_user_banned,
    save_payment_session,
    save_order_coupon_code,
    set_bot_setting,
    subscribe_stock_alert,
    release_order_delivery_claim,
    refund_order_wallet_if_needed,
    track_user,
    update_delivery_status,
    update_order_status,
    close_ticket,
)
from database.payment import create_cashfree_payment_link, get_cashfree_order_status
from services.coupon_service import deliver_coupons
from texts import BOT_USERNAME

ROOT = Path(__file__).parent / "mini_app"
router = APIRouter()
router.mount("/mini/static", StaticFiles(directory=ROOT), name="mini-static")
MEMBERSHIP_CACHE_SECONDS = 300
_membership_cache = {}


async def telegram_user(request: Request):
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
    # The configured owner must retain access to repair maintenance, stock, or
    # payment issues even if an old ban record exists.
    if str(user_id) != str(ADMIN_ID) and is_user_banned(user_id):
        raise HTTPException(403, "This account is restricted.")
    if (
        str(user_id) != str(ADMIN_ID)
        and get_bot_setting("maintenance_mode", "off").lower() == "on"
    ):
        raise HTTPException(503, "Shop maintenance is active. Please return after the upgrade.")
    # The configured owner never needs to join gates while repairing the shop.
    if str(user_id) == str(ADMIN_ID):
        track_user(user_id, user.get("username"))
        return user
    cached_until = _membership_cache.get(user_id)
    if cached_until and cached_until > datetime.now(timezone.utc).timestamp():
        track_user(user_id, user.get("username"))
        return user
    bot = Bot(token=BOT_TOKEN)
    try:
        channel_member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        group_member = await bot.get_chat_member(GROUP_USERNAME, user_id)
    except Exception as error:
        raise HTTPException(403, "Join our required channel and support group, then tap Verify in the bot.") from error
    finally:
        await bot.session.close()
    valid_statuses = {"member", "administrator", "creator", "owner"}
    if channel_member.status not in valid_statuses or group_member.status not in valid_statuses:
        raise HTTPException(403, "Join our required channel and support group, then tap Verify in the bot.")
    _membership_cache[user_id] = datetime.now(timezone.utc).timestamp() + MEMBERSHIP_CACHE_SECONDS
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


async def deliver_confirmed_order(order):
    """Claim and deliver exactly once after Cashfree confirms a Mini App order."""
    if order.delivery_status == "DELIVERED":
        return get_order_by_id(order.order_id)
    if not claim_order_delivery(order.order_id):
        return get_order_by_id(order.order_id)

    codes, _ = deliver_coupons(order.coupon_name, order.quantity or 1)
    if len(codes) != (order.quantity or 1):
        release_order_delivery_claim(order.order_id)
        if order.payable_amount == 0 and order.wallet_used:
            add_wallet_credit(
                order.user_id,
                order.wallet_used,
                f"Wallet refund for {order.order_id}",
            )
            update_order_status(order.order_id, "FAILED")
        raise HTTPException(409, "Payment received, but stock changed. Support has been notified.")

    save_order_coupon_code(order.order_id, ", ".join(codes))
    update_order_status(order.order_id, "SUCCESS")
    update_delivery_status(order.order_id, "DELIVERED")
    delivered = get_order_by_id(order.order_id)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.send_message(
            order.user_id,
            "🎉 <b>Payment successful — coupon delivered</b>\n\n"
            f"<blockquote>🆔 Order: <code>{order.order_id}</code>\n"
            f"🎟 Code:\n<code>{delivered.coupon_code}</code></blockquote>",
        )
    finally:
        await bot.session.close()
    return delivered


@router.get("/mini")
async def mini_app_home():
    return FileResponse(ROOT / "index.html", media_type="text/html")


@router.get("/api/mini/bootstrap")
async def bootstrap(request: Request):
    user = await telegram_user(request)
    user_id = int(user["id"])
    coupons = get_coupon_type_options()
    for coupon in coupons:
        coupon["description"] = get_bot_setting(
            f"coupon_description:{coupon['coupon_name']}", ""
        )
        special_price = get_bulk_buyer_price(user_id, coupon["coupon_name"])
        if special_price is not None:
            coupon["price"] = special_price
    orders = get_user_orders(user_id)[:20]
    for order in orders:
        if order.payment_status == "PENDING" and expire_order_if_needed(order.order_id):
            refund_order_wallet_if_needed(order.order_id, "Payment expiry refund")
    orders = get_user_orders(user_id)[:20]
    return {
        "user": {"id": user_id, "first_name": user.get("first_name", "Friend"), "username": user.get("username")},
        "bot_username": BOT_USERNAME,
        "is_admin": str(user_id) == str(ADMIN_ID),
        "coupons": coupons,
        "wallet_balance": get_wallet_balance(user_id),
        "referrals": get_referral_count(user_id),
        "orders": [serialize_order(order) for order in orders],
        "flash_sales": [
            {
                "id": sale.id,
                "coupon_name": sale.coupon_name,
                "title": sale.title,
                "discount_text": sale.discount_text,
                "expires_at": sale.expires_at.replace(tzinfo=timezone.utc).isoformat()
                if sale.expires_at else None,
            }
            for sale in get_active_flash_sales(limit=3)
        ],
        "cashfree_mode": CASHFREE_ENV,
    }


@router.get("/api/mini/admin/overview")
async def admin_overview(request: Request):
    """Protected, read-only Mini App dashboard for the configured admin."""
    user = await telegram_user(request)
    if str(user["id"]) != str(ADMIN_ID):
        raise HTTPException(403, "Admin access only.")
    return {
        "analytics": get_analytics_snapshot(),
        "coupons": get_coupon_summary(limit=8),
        "tickets": [
            {"id": ticket.id, "subject": ticket.subject, "status": ticket.status}
            for ticket in get_open_tickets(limit=8)
        ],
        "delivery_recovery_count": len(get_delivery_reconciliation(limit=100)),
        "maintenance_mode": get_bot_setting("maintenance_mode", "off").lower(),
        "backup": {
            "provider": "Railway Postgres",
            "status": get_bot_setting("railway_backup_status", "Verify backup schedule in Railway dashboard"),
        },
    }


@router.post("/api/mini/admin/maintenance")
async def admin_maintenance(request: Request):
    """Only the configured Telegram admin can change customer availability."""
    user = await telegram_user(request)
    if str(user["id"]) != str(ADMIN_ID):
        raise HTTPException(403, "Admin access only.")
    body = await request.json()
    enabled = bool(body.get("enabled"))
    value = "on" if enabled else "off"
    set_bot_setting("maintenance_mode", value)
    audit_admin_action(int(user["id"]), "maintenance_mode", value)
    return {"maintenance_mode": value}


@router.get("/api/mini/service-status")
async def service_status(request: Request):
    await telegram_user(request)
    return {
        "shop": "online",
        "cashfree": "online",
        "instant_delivery": "active",
        "maintenance_mode": get_bot_setting("maintenance_mode", "off").lower(),
    }


@router.get("/api/mini/tickets")
async def user_tickets(request: Request):
    user = await telegram_user(request)
    return {"tickets": [{"id": t.id, "subject": t.subject, "status": t.status, "messages": t.messages, "created_at": t.created_at.isoformat()} for t in get_user_tickets(int(user["id"]))]}


@router.post("/api/mini/stock-watch")
async def stock_watch(request: Request):
    user = await telegram_user(request)
    body = await request.json()
    coupon_name = str(body.get("coupon_name", "ALL")).strip()[:255] or "ALL"
    if not subscribe_stock_alert(int(user["id"]), coupon_name):
        raise HTTPException(500, "Could not save your stock alert.")
    return {"ok": True, "coupon_name": coupon_name}


@router.post("/api/mini/coupon-validate")
async def coupon_validate(request: Request):
    user = await telegram_user(request)
    code = str((await request.json()).get("code", "")).strip()
    if len(code) < 3:
        raise HTTPException(422, "Enter a valid coupon code.")
    orders = get_user_orders(int(user["id"]))
    matched = next((order for order in orders if order.delivery_status == "DELIVERED" and code in (order.coupon_code or "").split(", ")), None)
    return {
        "valid": bool(matched),
        "order_id": matched.order_id if matched else None,
        "coupon_name": matched.coupon_name if matched else None,
    }


@router.get("/api/mini/receipts/{order_id}")
async def receipt(order_id: str, request: Request):
    user = await telegram_user(request)
    order = get_order_by_id(order_id)
    if not order or order.user_id != int(user["id"]):
        raise HTTPException(404, "Order not found.")
    return {"receipt": serialize_order(order), "shop": "BB Coupon Shop"}


@router.get("/api/mini/preferences")
async def preferences(request: Request):
    user = await telegram_user(request)
    enabled = get_bot_setting(f"notifications:{user['id']}", "on").lower() == "on"
    return {"stock_alerts": enabled}


@router.post("/api/mini/preferences")
async def save_preferences(request: Request):
    user = await telegram_user(request)
    enabled = bool((await request.json()).get("stock_alerts", True))
    set_bot_setting(f"notifications:{user['id']}", "on" if enabled else "off")
    return {"stock_alerts": enabled}


@router.get("/api/mini/admin/orders/search")
async def admin_order_search(request: Request, query: str = ""):
    user = await telegram_user(request)
    if str(user["id"]) != str(ADMIN_ID):
        raise HTTPException(403, "Admin access only.")
    query = query.strip().lower()
    orders = get_recent_orders(limit=100)
    if query:
        orders = [o for o in orders if query in o.order_id.lower() or query in str(o.user_id) or query in (o.coupon_code or "").lower()]
    return {"orders": [serialize_order(order) | {"user_id": order.user_id} for order in orders[:30]]}


@router.post("/api/mini/admin/tickets/{ticket_id}/reply")
async def admin_ticket_reply(ticket_id: int, request: Request):
    user = await telegram_user(request)
    if str(user["id"]) != str(ADMIN_ID):
        raise HTTPException(403, "Admin access only.")
    body = await request.json()
    reply = str(body.get("message", "")).strip()
    ticket = get_ticket_by_id(ticket_id)
    if not ticket or len(reply) < 2:
        raise HTTPException(422, "A valid ticket and reply are required.")
    if not add_ticket_reply(ticket_id, "admin", reply):
        raise HTTPException(500, "Could not save reply.")
    close_ticket(ticket_id)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.send_message(ticket.user_id, f"💬 <b>Admin replied to ticket #{ticket_id}</b>\n\n<blockquote>{reply}</blockquote>")
    finally:
        await bot.session.close()
    audit_admin_action(int(user["id"]), "mini_ticket_reply", str(ticket_id))
    return {"ok": True}


@router.post("/api/mini/checkout")
async def checkout(request: Request):
    user = await telegram_user(request)
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
    customer_phone = "".join(character for character in str(body.get("customer_phone", "")) if character.isdigit())
    if len(customer_phone) == 12 and customer_phone.startswith("91"):
        customer_phone = customer_phone[2:]
    if len(customer_phone) != 10 or customer_phone[0] not in "6789":
        raise HTTPException(422, "Enter your own valid 10-digit Indian mobile number for UPI checkout.")
    unit_price = get_bulk_buyer_price(user_id, coupon.coupon_name)
    unit_price = unit_price if unit_price is not None else coupon.selling_price
    order_id = create_order(
        user_id, coupon.coupon_name, int(unit_price) * quantity, use_wallet=True, quantity=quantity
    )
    if not order_id:
        raise HTTPException(500, "Could not create your order. Please try again.")

    order = get_order_by_id(order_id)
    if order.payable_amount == 0:
        # A fully wallet-funded order is still claimed and delivered by the
        # same exactly-once server-side path as a gateway-paid order.
        delivered = await deliver_confirmed_order(order)
        return {"order": serialize_order(delivered), "delivered": True}

    payment = create_cashfree_payment_link(order_id, order.payable_amount, user_id, customer_phone)
    session_id = payment.get("payment_session_id")
    if not session_id:
        reason = payment.get("error") or payment.get("message") or "Cashfree checkout is unavailable."
        status_code = int(payment.get("status_code") or 502)
        print(f"Cashfree order creation failed: status={status_code}, reason={str(reason)[:160]}")
        raise HTTPException(502, f"Cashfree checkout could not start: {reason}")
    save_payment_session(order_id, session_id)
    return {"order": serialize_order(order), "payment_session_id": session_id}


@router.get("/api/mini/orders/{order_id}/status")
async def mini_order_status(order_id: str, request: Request):
    user = await telegram_user(request)
    order = get_order_by_id(order_id)
    if not order or order.user_id != int(user["id"]):
        raise HTTPException(404, "Order not found.")

    if order.payment_status == "PENDING" and expire_order_if_needed(order_id):
        refund_order_wallet_if_needed(order_id, "Payment expiry refund")
        return {"order": serialize_order(get_order_by_id(order_id))}

    if order.payment_status == "PENDING":
        # requests is synchronous in the Cashfree client; keep it off the
        # FastAPI event loop while the Mini App polls for confirmation.
        payment = await asyncio.to_thread(get_cashfree_order_status, order_id)
        status = str(
            payment.get("order_status") or payment.get("payment_status") or payment.get("status") or ""
        ).upper()
        if status in {"PAID", "SUCCESS"}:
            update_order_status(order_id, "SUCCESS")
            order = await deliver_confirmed_order(get_order_by_id(order_id))
    elif order.payment_status == "SUCCESS" and order.delivery_status != "DELIVERED":
        order = await deliver_confirmed_order(order)

    return {"order": serialize_order(get_order_by_id(order_id))}


@router.post("/api/mini/tickets")
async def create_ticket(request: Request):
    user = await telegram_user(request)
    body = await request.json()
    subject = str(body.get("subject", "Support request")).strip()
    message = str(body.get("message", "")).strip()
    if len(subject) < 3 or len(message) < 5:
        raise HTTPException(422, "Please add a subject and a short description.")
    ticket_id = create_support_ticket(int(user["id"]), subject, message)
    if not ticket_id:
        raise HTTPException(500, "Could not create the ticket.")
    if ADMIN_ID:
        bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            await bot.send_message(
                int(ADMIN_ID),
                "🎫 <b>New support ticket</b>\n\n"
                f"<blockquote>Ticket: <code>#{ticket_id}</code>\n"
                f"User: <code>{user['id']}</code>\n"
                f"Subject: <b>{subject}</b>\n\n{message}</blockquote>\n\n"
                "Open Control Center → Reply Ticket to respond.",
            )
        finally:
            await bot.session.close()
    return {"ok": True, "ticket_id": ticket_id}


@router.get("/api/mini/wallet")
async def wallet(request: Request):
    user = await telegram_user(request)
    user_id = int(user["id"])
    return {
        "balance": get_wallet_balance(user_id),
        "transactions": [
            {"amount": tx.amount, "reason": tx.reason, "created_at": tx.created_at.isoformat()}
            for tx in get_wallet_transactions(user_id, limit=20)
        ],
    }
