import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Update, WebAppInfo
from sqlalchemy import text

from config import (
    ADMIN_WEB_TOKEN,
    BOT_TOKEN,
    CASHFREE_CLIENT_ID,
    CASHFREE_CLIENT_SECRET,
    CASHFREE_ENV,
    PUBLIC_BASE_URL,
    PAYMENT_EXPIRY_MINUTES,
    require_env,
)
from database.crud import (
    add_wallet_credit,
    claim_order_delivery,
    get_analytics_snapshot,
    get_coupon_summary,
    get_open_tickets,
    get_order_by_id,
    get_bot_setting,
    set_bot_setting,
    get_active_flash_sales,
    audit_admin_action,
    expire_order_if_needed,
    get_payment_session,
    expire_due_orders,
    get_recent_audit_logs,
    get_wallet_balance,
    refund_order_wallet_if_needed,
    release_order_delivery_claim,
    save_order_coupon_code,
    update_delivery_status,
    update_order_status,
)
import database.db as database_db
from database.db import initialize_database
from database.models import Base
from database.payment import verify_cashfree_webhook_signature
from bot import dp
from handlers.admin import router as admin_router
from mini_app import router as mini_app_router
from services.coupon_service import deliver_coupon, deliver_coupons
from services.stock_alerts import notify_stock_alerts, should_send_stock_alert
from services.ai_assistant import get_ai_health
from texts import BOT_USERNAME

app = FastAPI()
app.include_router(mini_app_router)
# Static files mounted on an APIRouter are not included by FastAPI when the
# router is attached to the application.  Mount them directly so the Mini App
# can load its JavaScript and CSS in production.
app.mount("/mini/static", StaticFiles(directory=Path(__file__).parent / "mini_app"), name="mini-static")
telegram_bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
telegram_router_included = False
payment_expiry_task = None
flash_sale_expiry_task = None
service_started_at = time.time()


async def payment_expiry_worker():
    """Keep pending orders from remaining payable after their Cashfree window."""
    while True:
        try:
            for order_id in expire_due_orders():
                refund_order_wallet_if_needed(order_id, "Payment expiry refund")
            set_bot_setting("worker:payment_expiry", datetime.now(timezone.utc).isoformat())
        except Exception as error:
            print(f"Payment expiry worker error: {error}")
        await asyncio.sleep(30)


async def flash_sale_expiry_worker():
    """Restore timed sale prices even if no customer opens the Mini App."""
    while True:
        try:
            # This database operation expires due sales and restores their
            # saved normal price atomically before returning active sales.
            get_active_flash_sales(limit=1)
            set_bot_setting("worker:flash_sale_expiry", datetime.now(timezone.utc).isoformat())
        except Exception as error:
            print(f"Flash sale expiry worker error: {error}")
        await asyncio.sleep(30)


def get_order_quantity(order_id):
    order = get_order_by_id(order_id)
    return max(1, int(order.quantity or 1)) if order else 1


def feedback_keyboard(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data=f"feedback_{order_id}_1", style="danger"),
                InlineKeyboardButton(text="2", callback_data=f"feedback_{order_id}_2", style="danger"),
                InlineKeyboardButton(text="3", callback_data=f"feedback_{order_id}_3", style="primary"),
                InlineKeyboardButton(text="4", callback_data=f"feedback_{order_id}_4", style="success"),
                InlineKeyboardButton(text="5", callback_data=f"feedback_{order_id}_5", style="success"),
            ],
            [InlineKeyboardButton(text="Skip", callback_data=f"feedback_{order_id}_0", style="primary")],
        ]
    )


def web_admin_allowed(token):
    return bool(ADMIN_WEB_TOKEN and token == ADMIN_WEB_TOKEN)


@app.on_event("startup")
async def startup():
    global telegram_router_included, payment_expiry_task, flash_sale_expiry_task

    require_env()
    initialize_database(Base)

    if not telegram_router_included:
        dp.include_router(admin_router)
        telegram_router_included = True

    await telegram_bot.set_webhook(
        f"{PUBLIC_BASE_URL}/webhook/telegram",
        drop_pending_updates=False,
    )
    await telegram_bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Open Shop",
            web_app=WebAppInfo(url=f"{PUBLIC_BASE_URL}/mini"),
        )
    )
    if payment_expiry_task is None or payment_expiry_task.done():
        payment_expiry_task = asyncio.create_task(payment_expiry_worker())
    if flash_sale_expiry_task is None or flash_sale_expiry_task.done():
        flash_sale_expiry_task = asyncio.create_task(flash_sale_expiry_worker())


@app.on_event("shutdown")
async def shutdown():
    if payment_expiry_task:
        payment_expiry_task.cancel()
    if flash_sale_expiry_task:
        flash_sale_expiry_task.cancel()
    await telegram_bot.session.close()


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    set_bot_setting("webhook:telegram_last_seen", datetime.now(timezone.utc).isoformat())
    update = Update.model_validate(data, context={"bot": telegram_bot})
    await dp.feed_update(telegram_bot, update)
    return JSONResponse({"ok": True})


@app.get("/")
async def home():
    return {
        "status": "running",
        "service": "BB Coupon Bot",
        "ai_assist": "Cutie enabled",
        "public_base_url": PUBLIC_BASE_URL,
        "cashfree_env": CASHFREE_ENV,
    }


@app.get("/health")
async def health():
    db = database_db.SessionLocal()

    try:
        db.execute(text("SELECT 1"))
        database_ok = True
        database_error = None
    except Exception as error:
        database_ok = False
        database_error = str(error)
    finally:
        db.close()

    cashfree_ok = bool(CASHFREE_CLIENT_ID and CASHFREE_CLIENT_SECRET)

    return {
        "ok": database_ok and cashfree_ok,
        "database_ok": database_ok,
        "database_error": "unavailable" if database_error else None,
        "cashfree_ok": cashfree_ok,
        "cashfree_env": CASHFREE_ENV,
        "public_base_url": PUBLIC_BASE_URL,
        "cutie_ai": get_ai_health(),
        "uptime_seconds": int(time.time() - service_started_at),
        "workers": {
            "payment_expiry": get_bot_setting("worker:payment_expiry", "starting"),
            "flash_sale_expiry": get_bot_setting("worker:flash_sale_expiry", "starting"),
        },
        "webhooks": {
            "telegram_last_seen": get_bot_setting("webhook:telegram_last_seen", "waiting"),
            "cashfree_last_seen": get_bot_setting("webhook:cashfree_last_seen", "waiting"),
        },
    }


@app.get("/admin")
async def admin_dashboard(token: str = ""):
    if not web_admin_allowed(token):
        return HTMLResponse("<h1>403</h1><p>Admin token required.</p>", status_code=403)

    analytics = get_analytics_snapshot()
    coupons = get_coupon_summary()
    tickets = get_open_tickets()
    logs = get_recent_audit_logs()

    coupon_rows = "".join(
        f"<tr><td>{item['name']}</td><td>{item['available']}</td><td>{item['sold']}</td><td>Rs {item['price']}</td></tr>"
        for item in coupons
    )
    ticket_rows = "".join(
        f"<tr><td>{ticket.id}</td><td>{ticket.user_id}</td><td>{ticket.subject}</td><td>{ticket.status}</td></tr>"
        for ticket in tickets
    )
    log_rows = "".join(
        f"<tr><td>{log.created_at}</td><td>{log.admin_id}</td><td>{log.action}</td><td>{log.details}</td></tr>"
        for log in logs
    )

    html = f"""
    <!doctype html>
    <html>
    <head>
        <title>BB Coupon Admin</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
            header {{ background: #0f172a; color: white; padding: 24px; }}
            main {{ padding: 24px; display: grid; gap: 18px; }}
            section {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; }}
            .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }}
            .metric {{ background: #ecfeff; border-left: 4px solid #0891b2; padding: 12px; border-radius: 6px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border-bottom: 1px solid #e2e8f0; padding: 8px; text-align: left; }}
        </style>
    </head>
    <body>
        <header><h1>⚡ BB Coupon Admin</h1><p>Cutie control dashboard</p></header>
        <main>
            <section class="metrics">
                <div class="metric"><b>Revenue</b><br>Rs {analytics['revenue']}</div>
                <div class="metric"><b>Orders</b><br>{analytics['total_orders']}</div>
                <div class="metric"><b>Conversion</b><br>{analytics['conversion']}%</div>
                <div class="metric"><b>Users</b><br>{analytics['total_users']}</div>
            </section>
            <section><h2>Inventory</h2><table><tr><th>Coupon</th><th>Available</th><th>Sold</th><th>Price</th></tr>{coupon_rows}</table></section>
            <section><h2>Tickets</h2><table><tr><th>ID</th><th>User</th><th>Subject</th><th>Status</th></tr>{ticket_rows}</table></section>
            <section><h2>Audit</h2><table><tr><th>Time</th><th>Admin</th><th>Action</th><th>Details</th></tr>{log_rows}</table></section>
        </main>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/pay/{order_id}")
async def pay_page(order_id: str):
    if expire_order_if_needed(order_id):
        refund_order_wallet_if_needed(order_id, "Payment expiry refund")

    order = get_order_by_id(order_id)
    if not order or order.payment_status != "PENDING":
        return HTMLResponse(
            "<html><body><h1>Payment link expired</h1>"
            "<p>This order is no longer payable. Return to Telegram and create a fresh order.</p>"
            "</body></html>",
            status_code=410,
        )

    expires_at = (order.payment_expires_at or datetime.utcnow()).replace(
        tzinfo=timezone.utc
    ).isoformat()

    session_id = get_payment_session(order_id)

    if not session_id:
        return HTMLResponse(
            """
            <!doctype html>
            <html>
            <head>
                <title>Invalid Order</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        background: #fff7ed;
                    color: #9a3412;
                        display: grid;
                        min-height: 100vh;
                        place-items: center;
                    }
                    main {
                        max-width: 520px;
                        padding: 32px;
                        border: 1px solid #fed7aa;
                        border-radius: 8px;
                        background: white;
                    }
                    code {
                        color: #7c2d12;
                        font-weight: 700;
                    }
                </style>
            </head>
            <body>
                <main>
                    <h1>Cutie paused this checkout</h1>
                    <p><strong>This payment link is not active.</strong></p>
                    <p><em>Please return to Telegram and create a fresh order.</em></p>
                </main>
            </body>
            </html>
            """,
            status_code=404,
        )

    mode = "sandbox" if CASHFREE_ENV == "sandbox" else "production"

    html = f"""
    <!doctype html>
    <html>
    <head>
        <title>BB Coupon Payment</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://sdk.cashfree.com/js/v3/cashfree.js"></script>
        <style>
            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                background: radial-gradient(circle at top, #fef3c7 0, #ecfeff 35%, #ffffff 100%);
                color: #164e63;
                display: grid;
                min-height: 100vh;
                place-items: center;
            }}
            main {{
                width: min(92vw, 560px);
                padding: 32px;
                border: 1px solid #a5f3fc;
                border-radius: 8px;
                background: #ffffff;
                box-shadow: 0 20px 60px rgba(8, 47, 73, 0.14);
                animation: flashIn 700ms ease-out;
            }}
            h1 {{
                margin-top: 0;
                color: #0f766e;
            }}
            blockquote {{
                margin: 20px 0;
                padding: 16px;
                border-left: 4px solid #0891b2;
                background: #f0fdfa;
            }}
            code {{
                color: #be123c;
                font-weight: 700;
            }}
            .status {{
                color: #0369a1;
                font-weight: 700;
            }}
            button {{
                width: 100%; border: 0; border-radius: 10px; padding: 15px;
                background: #0f766e; color: white; font-size: 16px; font-weight: 700;
            }}
            @keyframes flashIn {{
                0% {{ transform: scale(0.97); box-shadow: 0 0 0 rgba(14, 165, 233, 0); }}
                45% {{ transform: scale(1.01); box-shadow: 0 0 38px rgba(14, 165, 233, 0.32); }}
                100% {{ transform: scale(1); box-shadow: 0 20px 60px rgba(8, 47, 73, 0.14); }}
            }}
        </style>
    </head>
    <body>
        <main>
            <h1>⚡ BB Coupon Payment</h1>
            <blockquote>
                <strong>Cutie prepared your secure checkout.</strong><br>
                <em>Order ID:</em> <code>{order_id}</code>
            </blockquote>
            <p class="status">Flash redirect is starting. Please do not close this page.</p>
            <p class="status">Payment window: <span id="paymentTimer">{PAYMENT_EXPIRY_MINUTES}:00</span></p>
            <button type="button" id="retryCheckout">Open secure checkout</button>
        </main>

        <script>
            const cashfree = Cashfree({{
                mode: "{mode}"
            }});

            const checkoutOptions = {{
                paymentSessionId: "{session_id}",
                redirectTarget: "_top"
            }};
            const openCheckout = () => cashfree.checkout(checkoutOptions);
            document.getElementById("retryCheckout").addEventListener("click", openCheckout);
            const expiresAt = new Date("{expires_at}").getTime();
            const timer = document.getElementById("paymentTimer");
            const updateTimer = () => {{
                const remaining = Math.max(0, expiresAt - Date.now());
                const minutes = Math.floor(remaining / 60000);
                const seconds = Math.floor((remaining % 60000) / 1000);
                timer.textContent = `${{String(minutes).padStart(2, "0")}}:${{String(seconds).padStart(2, "0")}}`;
                if (!remaining) window.location.reload();
            }};
            updateTimer();
            window.setInterval(updateTimer, 1000);
            window.setTimeout(openCheckout, 150);
        </script>
    </body>
    </html>
    """

    return HTMLResponse(html)


@app.get("/payment-result/{order_id}")
async def payment_result(order_id: str, status: str = ""):
    safe_status = (status or "CHECKING").upper()
    telegram_return = f"https://t.me/{BOT_USERNAME}?startapp=order-{order_id}"
    return HTMLResponse(
        f"""
        <!doctype html>
        <html>
        <head>
            <title>Payment Result</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background: #020617;
                    color: #f8fafc;
                    min-height: 100vh;
                    display: grid;
                    place-items: center;
                }}
                main {{
                    width: min(92vw, 560px);
                    border: 1px solid #facc15;
                    border-radius: 8px;
                    padding: 28px;
                    background: #111827;
                    box-shadow: 0 0 40px rgba(250, 204, 21, 0.22);
                }}
                code {{ color: #fde047; font-weight: 700; }}
                blockquote {{
                    margin: 18px 0;
                    padding: 14px;
                    border-left: 4px solid #22c55e;
                    background: #0f172a;
                }}
            </style>
        </head>
        <body>
            <main>
                <h1>⚡ Payment Status</h1>
                <blockquote>
                    Order: <code>{order_id}</code><br>
                    Status: <code>{safe_status}</code>
                </blockquote>
                <p>Returning you to BB Coupon Shop in Telegram…</p>
                <p>Payment confirmation and coupon delivery run automatically.</p>
            </main>
            <script>
                // Browsers cannot reliably close themselves after a payment.
                // Opening Telegram after three seconds returns to the Mini App.
                window.setTimeout(() => window.location.replace("{telegram_return}"), 3000);
            </script>
        </body>
        </html>
        """
    )


@app.get("/webhook/cashfree")
async def cashfree_webhook_health():
    return JSONResponse({"success": True, "provider": "cashfree", "service": "BB Coupon Bot"})


@app.post("/webhook/cashfree")
async def cashfree_webhook(request: Request):
    raw_body = await request.body()
    if not verify_cashfree_webhook_signature(
        raw_body,
        request.headers.get("x-webhook-signature"),
        request.headers.get("x-webhook-timestamp"),
    ):
        return JSONResponse({"success": False, "detail": "Invalid webhook signature"}, status_code=401)

    try:
        data = json.loads(raw_body)
    except Exception:
        data = {}

    # Do not print full Cashfree payloads: they may contain customer/payment
    # metadata. The safe audit record below keeps only order ID and status.
    set_bot_setting("webhook:cashfree_last_seen", datetime.now(timezone.utc).isoformat())

    try:
        order_id = (
            data
            .get("data", {})
            .get("order", {})
            .get("order_id")
        )
        payment_status = (
            data
            .get("data", {})
            .get("payment", {})
            .get("payment_status")
        )
        payment_status = (
            payment_status
            or data.get("order_status")
            or data.get("payment_status")
            or data.get("status")
            or ""
        ).upper()

        if not order_id:
            audit_admin_action(0, "cashfree_webhook", "received_without_order")
            return JSONResponse({"success": True, "received": True})

        audit_admin_action(0, "cashfree_webhook", f"{order_id}:{payment_status or 'UNKNOWN'}")

        if payment_status in {"FAILED", "USER_DROPPED"}:
            update_order_status(order_id, "FAILED")
            refund_order_wallet_if_needed(order_id, "Cashfree payment failure refund")
            return JSONResponse({"success": True, "payment_failed": True})

        if payment_status == "SUCCESS" and order_id:
            if expire_order_if_needed(order_id):
                refund_order_wallet_if_needed(order_id, "Payment expiry refund")
                return JSONResponse({"success": True, "expired": True})
            update_order_status(order_id, "SUCCESS")
            order = get_order_by_id(order_id)

            if order:
                if order.delivery_status == "DELIVERED":
                    return JSONResponse({"success": True, "already_delivered": True})

                if not claim_order_delivery(order_id):
                    return JSONResponse({"success": True, "already_processing": True})

                if order.coupon_name == "WALLET_TOPUP":
                    add_wallet_credit(order.user_id, order.amount, f"Wallet top up for {order.order_id}")
                    update_delivery_status(order_id, "DELIVERED")

                    bot = Bot(
                        token=BOT_TOKEN,
                        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                    )

                    balance = get_wallet_balance(order.user_id)
                    await bot.send_message(
                        chat_id=order.user_id,
                        text=(
                            "💎 <b>Wallet Top Up Successful</b>\n\n"
                            f"<blockquote>🆔 Order: <code>{order.order_id}</code>\n"
                            f"💰 Added: <b>Rs {order.amount}</b>\n"
                            f"💳 Wallet Balance: <b>Rs {balance}</b></blockquote>\n\n"
                            "<i>You can now use this balance to buy coupons.</i>"
                        ),
                    )
                    await bot.session.close()
                    return JSONResponse({"success": True, "wallet_topup": True})

                quantity = get_order_quantity(order_id)
                coupon_codes, remaining_stock = deliver_coupons(order.coupon_name, quantity)
                coupon_code = "\n".join(coupon_codes)

                if len(coupon_codes) == quantity:
                    update_delivery_status(order_id, "DELIVERED")
                    save_order_coupon_code(order_id, ", ".join(coupon_codes))

                    bot = Bot(
                        token=BOT_TOKEN,
                        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
                    )

                    await bot.send_message(
                        chat_id=order.user_id,
                        text=(
                            "🎉 <b>Payment Successful</b>\n\n"
                            f"<blockquote>🆔 Order: <code>{order.order_id}</code>\n"
                            "🎟 Coupon Code:\n"
                            f"<code>{coupon_code}</code></blockquote>\n\n"
                            "<i>Cutie delivered it for you. Thank you for purchasing.</i>"
                        ),
                    )
                    await bot.send_message(
                        chat_id=order.user_id,
                        text=(
                            "<b>How was this purchase?</b>\n\n"
                            "<blockquote>Your feedback helps train and improve Cutie AI support.</blockquote>"
                        ),
                        reply_markup=feedback_keyboard(order.order_id),
                    )
                    if should_send_stock_alert(remaining_stock, order.coupon_name):
                        await notify_stock_alerts(
                            bot,
                            order.coupon_name,
                            remaining_stock,
                            reason="low_stock" if remaining_stock > 0 else "sold_out",
                        )

                    await bot.session.close()
                    print(f"Coupon delivered: {coupon_code}")
                else:
                    refund_order_wallet_if_needed(order_id, "Delivery refund")
                    release_order_delivery_claim(order_id)

        return JSONResponse({"success": True})

    except Exception as error:
        if "order_id" in locals() and order_id:
            release_order_delivery_claim(order_id)
        print("Webhook error:")
        print(error)
        return JSONResponse({"success": False})
