from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, CASHFREE_ENV
from database.crud import (
    get_order_by_id,
    get_payment_session,
    update_delivery_status,
    update_order_status,
)
from services.coupon_service import deliver_coupon

app = FastAPI()


@app.get("/")
async def home():
    return {
        "status": "running",
        "service": "BB Coupon Bot",
        "ai_assist": "Cutie enabled",
    }


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


@app.post("/webhook/cashfree")
async def cashfree_webhook(request: Request):
    data = await request.json()
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

        if payment_status == "SUCCESS" and order_id:
            update_order_status(order_id, "SUCCESS")
            order = get_order_by_id(order_id)

            if order:
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
