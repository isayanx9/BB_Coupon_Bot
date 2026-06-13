from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import text

from config import (
    ADMIN_WEB_TOKEN,
    BOT_TOKEN,
    CASHFREE_CLIENT_ID,
    CASHFREE_CLIENT_SECRET,
    CASHFREE_ENV,
    PUBLIC_BASE_URL,
)
from database.crud import (
    get_analytics_snapshot,
    get_coupon_summary,
    get_open_tickets,
    get_order_by_id,
    get_payment_session,
    get_recent_audit_logs,
    update_delivery_status,
    update_order_status,
)
import database.db as database_db
from services.coupon_service import deliver_coupon

app = FastAPI()


def web_admin_allowed(token):
    return bool(ADMIN_WEB_TOKEN and token == ADMIN_WEB_TOKEN)


@app.get("/")
async def home():
    return {
        "status": "running",
        "service": "BB Coupon Bot",
        "ai_assist": "Cutie enabled",
        "database": database_db.active_database_url,
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
        "database_url": database_db.active_database_url,
        "database_error": database_error,
        "cashfree_ok": cashfree_ok,
        "cashfree_env": CASHFREE_ENV,
        "public_base_url": PUBLIC_BASE_URL,
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
        </main>

        <script>
            const cashfree = Cashfree({{
                mode: "{mode}"
            }});

            cashfree.checkout({{
                paymentSessionId: "{session_id}",
                redirectTarget: "_self"
            }});
        </script>
    </body>
    </html>
    """

    return HTMLResponse(html)


@app.get("/payment-result/{order_id}")
async def payment_result(order_id: str, status: str = ""):
    safe_status = (status or "CHECKING").upper()
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
                <p>Return to Telegram and tap <b>I Paid, Recheck</b>. Cutie will deliver the coupon after Cashfree confirms payment.</p>
            </main>
        </body>
        </html>
        """
    )


@app.get("/webhook/cashfree")
async def cashfree_webhook_health():
    return JSONResponse({"success": True, "provider": "cashfree", "service": "BB Coupon Bot"})


@app.post("/webhook/cashfree")
async def cashfree_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    print("Cashfree webhook:")
    print(data)

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
            return JSONResponse({"success": True, "received": True})

        if payment_status in {"SUCCESS", "PAID", "ACTIVE"} and order_id:
            update_order_status(order_id, "SUCCESS")
            order = get_order_by_id(order_id)

            if order:
                if order.delivery_status == "DELIVERED":
                    return JSONResponse({"success": True, "already_delivered": True})

                coupon_code = deliver_coupon(order.coupon_name)

                if coupon_code:
                    update_delivery_status(order_id, "DELIVERED")

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

                    await bot.session.close()
                    print(f"Coupon delivered: {coupon_code}")

        return JSONResponse({"success": True})

    except Exception as error:
        print("Webhook error:")
        print(error)
        return JSONResponse({"success": False})
