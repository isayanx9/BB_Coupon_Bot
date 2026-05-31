import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from config import (
    BOT_TOKEN,
    ADMIN_ID
)

from handlers.admin import router as admin_router

from keyboards.shop import (
    buy_coupon_keyboard,
    payment_keyboard
)

from database.crud import (
    create_order,
    get_coupon_stock,
    get_user_orders,
    get_coupon_price
)

from database.payment import (
    create_cashfree_payment_link
)

from keyboards.user import (
    join_keyboard,
    terms_keyboard,
    user_main_menu,
    admin_main_menu
)

dp = Dispatcher()


# =========================
# START COMMAND
# =========================

@dp.message(CommandStart())
async def start_command(message: Message):

    await message.answer(
        "🎉 Welcome to BB Coupon Bot!\n\n"
        "Before continuing:\n\n"
        "1️⃣ Join our Channel\n"
        "2️⃣ Join our Support Group\n"
        "3️⃣ Press Verify",
        reply_markup=join_keyboard()
    )


# =========================
# VERIFY MEMBERSHIP
# =========================

@dp.callback_query(F.data == "verify_user")
async def verify_user(callback: CallbackQuery, bot: Bot):

    user_id = callback.from_user.id

    try:

        channel_member = await bot.get_chat_member(
            "@FlashXDeal",
            user_id
        )

        group_member = await bot.get_chat_member(
            "@FlashXSupports",
            user_id
        )

        valid_status = [
            "member",
            "administrator",
            "creator"
        ]

        if (
            channel_member.status in valid_status
            and
            group_member.status in valid_status
        ):

            await callback.message.edit_text(
                "📜 Terms & Conditions\n\n"
                "1. Coupons are non-refundable.\n"
                "2. Expired coupons cannot be replaced.\n"
                "3. Payment disputes must be reported within 24 hours.\n"
                "4. By continuing, you agree to our terms.\n\n"
                "Please choose:",
                reply_markup=terms_keyboard()
            )

        else:

            await callback.answer(
                "❌ Join both Channel and Group first.",
                show_alert=True
            )

    except Exception as e:

        print(f"Verification Error: {e}")

        await callback.answer(
            "❌ Please join Channel and Group first.",
            show_alert=True
        )


# =========================
# ACCEPT TERMS
# =========================

@dp.callback_query(F.data == "accept_terms")
async def accept_terms(callback: CallbackQuery):

    await callback.message.edit_text(
        "✅ Terms Accepted!\n\n"
        "Welcome to BB Coupon Bot."
    )

    if str(callback.from_user.id) == str(ADMIN_ID):
        menu = admin_main_menu()
    else:
        menu = user_main_menu()

    await callback.message.answer(
        "🏠 Main Menu",
        reply_markup=menu
    )

    await callback.answer()


# =========================
# DECLINE TERMS
# =========================

@dp.callback_query(F.data == "decline_terms")
async def decline_terms(callback: CallbackQuery):

    await callback.message.edit_text(
        "❌ You must accept the Terms & Conditions to use this bot."
    )

    await callback.answer()


# =========================
# BUY COUPONS
# =========================

@dp.message(F.text == "🛒 Buy Coupons")
async def buy_coupons(message: Message):

    stock = get_coupon_stock(
        "BigBasket Chocolate & Ice Cream"
    )

    price = get_coupon_price(
        "BigBasket Chocolate & Ice Cream"
    )

    await message.answer(
        f"🛒 Available Coupons\n\n"
        f"🍫 BigBasket Chocolate & Ice Cream\n\n"
        f"💰 ₹100 OFF\n"
        f"🛒 Minimum Order ₹100+\n"
        f"📦 Stock Available: {stock}",
        reply_markup=buy_coupon_keyboard()
    )


@dp.callback_query(F.data == "buy_bb_coupon")
async def buy_bb_coupon(callback: CallbackQuery):

    coupon_name = "BigBasket Chocolate & Ice Cream"

    stock = get_coupon_stock(
        coupon_name
    )

    if stock <= 0:

        await callback.message.answer(
            "❌ Out Of Stock"
        )

        await callback.answer()
        return

    price = get_coupon_price(
        coupon_name
    )

    order_id = create_order(
        callback.from_user.id,
        coupon_name,
        price
    )

    await callback.message.answer(
    f"✅ Order Created\n\n"
    f"🆔 Order ID: {order_id}\n\n"
    f"🎟 Coupon:\n"
    f"{coupon_name}\n\n"
    f"💰 Amount: ₹{price}\n\n"
    f"⏳ Status: Pending Payment",
    reply_markup=payment_keyboard(order_id)
)

    await callback.answer()

# =========================
# PAY ORDER
# =========================

@dp.callback_query(F.data.startswith("pay_"))
async def pay_order(callback: CallbackQuery):

    order_id = callback.data.replace(
        "pay_",
        ""
    )

    data = create_cashfree_payment_link(
        order_id=order_id,
        amount=14,
        customer_id=callback.from_user.id
    )

    await callback.message.answer(
        f"💳 Cashfree Response\n\n{data}"
    )

    await callback.answer()

# =========================
# CANCEL ORDER
# =========================

@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_order(callback: CallbackQuery):

    order_id = callback.data.replace("cancel_", "")

    await callback.message.answer(
        f"❌ Order {order_id} cancelled."
    )

    await callback.answer()    


# =========================
# MY ORDERS
# =========================

@dp.message(F.text == "📦 My Orders")
async def my_orders(message: Message):

    orders = get_user_orders(
        message.from_user.id
    )

    if not orders:

        await message.answer(
            "📦 No Orders Found"
        )

        return

    text = "📦 Your Orders\n\n"

    for order in orders[:10]:

        text += (
            f"🆔 {order.order_id}\n"
            f"🎟 {order.coupon_name}\n"
            f"💰 ₹{order.amount}\n"
            f"📊 {order.payment_status}\n\n"
        )

    await message.answer(text)


# =========================
# PROFILE
# =========================

@dp.message(F.text == "👤 Profile")
async def profile(message: Message):

    user = message.from_user

    await message.answer(
        f"👤 Profile\n\n"
        f"ID: {user.id}\n"
        f"Name: {user.first_name}"
    )


# =========================
# REFERRAL
# =========================

@dp.message(F.text == "🎁 Referral")
async def referral(message: Message):

    bot_username = "FlashXBBbot"

    await message.answer(
        "🎁 Referral Program\n\n"
        f"Your Referral Link:\n"
        f"https://t.me/{bot_username}?start={message.from_user.id}"
    )


# =========================
# SUPPORT
# =========================

@dp.message(F.text == "📞 Support")
async def support(message: Message):

    await message.answer(
        "📞 Support\n\n"
        "Contact: @FlashXSupports"
    )


# =========================
# MAIN FUNCTION
# =========================

from database.db import engine
from database.models import Base

async def main():

    Base.metadata.create_all(bind=engine)

    bot = Bot(token=BOT_TOKEN)

    dp.include_router(admin_router)

    print("✅ BB Coupon Bot Started")

    await dp.start_polling(bot)


if __name__ == "__main__":
    pass