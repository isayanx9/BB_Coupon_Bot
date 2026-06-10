import asyncio
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import (
    ADMIN_ID,
    BOT_TOKEN,
    CHANNEL_USERNAME,
    GROUP_USERNAME,
    PUBLIC_BASE_URL,
    require_env,
)
from database.crud import (
    create_order,
    get_coupon_price,
    get_coupon_stock,
    get_user_orders,
    save_payment_session,
    update_order_status,
)
from database.db import engine
from database.models import Base
from database.payment import create_cashfree_payment_link
from handlers.admin import router as admin_router
from keyboards.shop import (
    buy_coupon_keyboard,
    payment_keyboard,
)
from keyboards.user import (
    admin_main_menu,
    join_keyboard,
    terms_keyboard,
    user_main_menu,
)
from services.ai_assistant import get_ai_answer
from states.order_states import AIAssist
from texts import (
    BOT_USERNAME,
    BTN_ACCESS_LOG,
    BTN_AI_ASSIST,
    BTN_DEAL_VAULT,
    BTN_PROFILE,
    BTN_SUPPORT,
    COUPON_NAME,
    TERMS_TEXT,
    WELCOME_TEXT,
)

dp = Dispatcher()


@dp.message(CommandStart())
async def start_command(message: Message):
    await message.answer(
        WELCOME_TEXT,
        reply_markup=join_keyboard(),
    )


@dp.callback_query(F.data == "verify_user")
async def verify_user(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    try:
        channel_member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        group_member = await bot.get_chat_member(GROUP_USERNAME, user_id)
        valid_status = ["member", "administrator", "creator"]

        if (
            channel_member.status in valid_status
            and group_member.status in valid_status
        ):
            await callback.message.edit_text(
                TERMS_TEXT,
                reply_markup=terms_keyboard(),
            )
        else:
            await callback.answer(
                "Join both the channel and support group first.",
                show_alert=True,
            )

    except Exception as error:
        print(f"Verification error: {error}")
        await callback.answer(
            "Please join the channel and support group first.",
            show_alert=True,
        )


@dp.callback_query(F.data == "accept_terms")
async def accept_terms(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>Terms accepted.</b>\n\n<i>Welcome to BB Coupon Bot.</i>"
    )

    menu = (
        admin_main_menu()
        if str(callback.from_user.id) == str(ADMIN_ID)
        else user_main_menu()
    )

    await callback.message.answer(
        "<b>Main Menu</b>",
        reply_markup=menu,
    )
    await callback.answer()


@dp.callback_query(F.data == "decline_terms")
async def decline_terms(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>You must accept the Terms and Conditions to use this bot.</b>"
    )
    await callback.answer()


@dp.message(F.text == BTN_DEAL_VAULT)
async def buy_coupons(message: Message):
    stock = get_coupon_stock(COUPON_NAME)
    price = get_coupon_price(COUPON_NAME)

    await message.answer(
        "<b>Available Coupon</b>\n\n"
        f"<blockquote><code>{COUPON_NAME}</code>\n"
        "Rs 100 OFF\n"
        "Minimum Order: Rs 100+\n"
        f"Stock Available: <b>{stock}</b>\n"
        f"Price: <b>Rs {price}</b></blockquote>\n\n"
        "<i>Tap Buy Now to create an order.</i>",
        reply_markup=buy_coupon_keyboard(),
    )


@dp.callback_query(F.data == "buy_bb_coupon")
async def buy_bb_coupon(callback: CallbackQuery):
    stock = get_coupon_stock(COUPON_NAME)

    if stock <= 0:
        await callback.message.answer("<b>Out of stock.</b>")
        await callback.answer()
        return

    price = get_coupon_price(COUPON_NAME)
    order_id = create_order(
        callback.from_user.id,
        COUPON_NAME,
        price,
    )

    if not order_id:
        await callback.message.answer(
            "<b>Order creation failed.</b>\n\nPlease try again or contact support."
        )
        await callback.answer()
        return

    await callback.message.answer(
        "<b>Order Created</b>\n\n"
        f"<blockquote>Order ID: <code>{order_id}</code>\n"
        f"Coupon: <code>{COUPON_NAME}</code>\n"
        f"Amount: <b>Rs {price}</b>\n"
        "Status: <i>Pending Payment</i></blockquote>",
        reply_markup=payment_keyboard(order_id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def pay_order(callback: CallbackQuery):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    order_id = callback.data.replace("pay_", "")
    price = get_coupon_price(COUPON_NAME)

    data = create_cashfree_payment_link(
        order_id=order_id,
        amount=price,
        customer_id=callback.from_user.id,
    )

    if "payment_session_id" not in data:
        await callback.message.answer(
            "<b>Payment Error</b>\n\n"
            f"<code>{data}</code>"
        )
        await callback.answer()
        return

    save_payment_session(order_id, data["payment_session_id"])
    payment_url = f"{PUBLIC_BASE_URL}/pay/{order_id}"

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Pay Now",
                    url=payment_url,
                )
            ]
        ]
    )

    await callback.message.answer(
        "<b>Payment Ready</b>\n\n"
        f"<blockquote>Order: <code>{order_id}</code>\n"
        f"Amount: <b>Rs {price}</b></blockquote>\n\n"
        "<i>Click the button below to complete payment securely.</i>",
        reply_markup=markup,
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_order(callback: CallbackQuery):
    order_id = callback.data.replace("cancel_", "")
    update_order_status(order_id, "CANCELLED")

    await callback.message.answer(
        f"<b>Order cancelled.</b>\n\nOrder ID: <code>{order_id}</code>"
    )
    await callback.answer()


@dp.message(F.text == BTN_ACCESS_LOG)
async def my_orders(message: Message):
    orders = get_user_orders(message.from_user.id)

    if not orders:
        await message.answer("<b>No orders found.</b>")
        return

    text = "<b>Your Orders</b>\n\n"

    for order in orders[:10]:
        text += (
            f"<blockquote>Order: <code>{order.order_id}</code>\n"
            f"Coupon: <code>{order.coupon_name}</code>\n"
            f"Amount: <b>Rs {order.amount}</b>\n"
            f"Payment: <i>{order.payment_status}</i>\n"
            f"Delivery: <i>{order.delivery_status}</i></blockquote>\n"
        )

    await message.answer(text)


@dp.message(F.text == BTN_PROFILE)
async def profile(message: Message):
    user = message.from_user

    await message.answer(
        "<b>Profile</b>\n\n"
        f"<blockquote>ID: <code>{user.id}</code>\n"
        f"Name: <b>{user.first_name}</b></blockquote>"
    )


@dp.message(F.text == "Referral")
async def referral(message: Message):
    await message.answer(
        "<b>Referral Program</b>\n\n"
        "<i>Your referral link:</i>\n"
        f"<code>https://t.me/{BOT_USERNAME}?start={message.from_user.id}</code>"
    )


@dp.message(F.text == BTN_SUPPORT)
async def support(message: Message):
    await message.answer(
        "<b>Support</b>\n\n"
        f"<blockquote>Contact: <code>{GROUP_USERNAME}</code>\n"
        "Send your Order ID and payment screenshot if delivery failed.</blockquote>"
    )


@dp.message(F.text == BTN_AI_ASSIST)
async def ai_assist_start(message: Message, state: FSMContext):
    await state.set_state(AIAssist.waiting_for_question)
    await message.answer(
        "<b>AI Assist</b>\n\n"
        "<blockquote>Ask about payments, order status, coupon delivery, stock, "
        "bugs, or admin uploads.</blockquote>\n\n"
        "<i>Send your question now.</i>"
    )


@dp.message(AIAssist.waiting_for_question)
async def ai_assist_answer(message: Message, state: FSMContext):
    answer = get_ai_answer(message.text or "")
    await message.answer(answer if "<" in answer else escape(answer))
    await state.clear()


async def main():
    require_env()
    Base.metadata.create_all(bind=engine)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    await bot.delete_webhook(drop_pending_updates=True)
    dp.include_router(admin_router)

    print("BB Coupon Bot started")
    me = await bot.get_me()
    print(f"Bot username: @{me.username}")
    print(f"Bot ID: {me.id}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
