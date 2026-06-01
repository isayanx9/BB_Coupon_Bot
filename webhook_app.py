from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

from aiogram import Bot

from config import BOT_TOKEN

from database.crud import (
    get_order_by_id,
    update_order_status,
    update_delivery_status,
    get_payment_session
)

from services.coupon_service import (
    deliver_coupon
)

app = FastAPI()


@app.get("/")
async def home():

    return {
        "status": "running",
        "service": "BB Coupon Bot Webhook"
    }

@app.get("/pay/{order_id}")
async def pay_page(order_id: str):

    session_id = get_payment_session(
        order_id
    )

    if not session_id:

        return HTMLResponse(
            "<h1>Invalid Order</h1>",
            status_code=404
        )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>BB Coupon Payment</title>

        <script src="https://sdk.cashfree.com/js/v3/cashfree.js"></script>
    </head>

    <body>

        <h2>Redirecting to Payment...</h2>

        <script>

        const cashfree = Cashfree({{
            mode: "production"
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

    print("CASHFREE WEBHOOK:")
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

        if (
            payment_status == "SUCCESS"
            and order_id
        ):

            update_order_status(
                order_id,
                "SUCCESS"
            )

            order = get_order_by_id(
                order_id
            )

            if order:

                coupon_code = deliver_coupon(
                    order.coupon_name
                )

                if coupon_code:

                    update_delivery_status(
                        order_id,
                        "DELIVERED"
                    )

                    bot = Bot(
                        token=BOT_TOKEN
                    )

                    await bot.send_message(
                        chat_id=order.user_id,
                        text=
                        f"🎉 Payment Successful!\n\n"
                        f"🆔 Order: {order.order_id}\n\n"
                        f"🎟 Coupon Code:\n"
                        f"`{coupon_code}`\n\n"
                        f"Thank you for purchasing."
                    )

                    await bot.session.close()

                    print(
                        f"COUPON DELIVERED: {coupon_code}"
                    )

        return JSONResponse(
            {"success": True}
        )

    except Exception as e:

        print("WEBHOOK ERROR:")
        print(e)

        return JSONResponse(
            {"success": False}
        )