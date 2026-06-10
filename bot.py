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
    get_bot_setting,
    get_coupon_by_id,
    get_coupon_price,
    get_coupon_stock,
    get_coupon_type_options,
    get_user_orders,
    is_user_banned,
    save_payment_session,
    track_user,
    update_order_status,
)
from database.db import engine
from database.models import Base
from database.payment import create_cashfree_payment_link
from handlers.admin import router as admin_router
from keyboards.shop import (
    buy_coupon_keyboard,
    coupon_list_keyboard,
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
    FLASH_ACCEPT_TEXT,
    FLASH_CANCEL_TEXT,
    FLASH_ORDER_TEXT,
    FLASH_PAYMENT_TEXT,
    FLASH_VERIFY_TEXT,
    TERMS_TEXT,
    WELCOME_TEXT,
)

dp = Dispatcher()


async def flash_effect(callback: CallbackQuery, text: str):
    try:
        await callback.message.edit_text(text)
        await asyncio.sleep(0.35)
    except Exception:
        pass


async def reject_if_banned(message: Message):
    track_user(
        message.from_user.id,
        message.from_user.username
    )

    if is_user_banned(message.from_user.id):
        await message.answer(
            "🚫 <b>Access blocked.</b>\n\n"
            "<blockquote>Your account is restricted. Contact support if this is a mistake.</blockquote>"
        )
        return True

    if get_bot_setting("maintenance_mode", "off").lower() == "on":
        await message.answer(
            "🛠 <b>Maintenance mode</b>\n\n"
            f"<blockquote>{get_bot_setting('maintenance_text', 'Cutie is upgrading the bot. Please try again soon.')}</blockquote>"
        )
        return True

    return False


@dp.message(CommandStart())
async def start_command(message: Message):
    if await reject_if_banned(message):
        return

    await message.answer(
        WELCOME_TEXT,
        reply_markup=join_keyboard(),
    )


@dp.callback_query(F.data == "verify_user")
async def verify_user(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    try:
        print("CHANNEL_USERNAME =", CHANNEL_USERNAME)
        print("GROUP_USERNAME =", GROUP_USERNAME)

        print("Checking channel...")
        channel_member = await bot.get_chat_member(
            CHANNEL_USERNAME,
            user_id
        )
        print("Channel OK")

        print("Checking group...")
        group_member = await bot.get_chat_member(
            GROUP_USERNAME,
            user_id
        )
        print("Group OK")

        valid_status = [
            "member",
            "administrator",
            "creator"
        ]

        if (
            channel_member.status in valid_status
            and group_member.status in valid_status
        ):
            await flash_effect(
                callback,
                FLASH_VERIFY_TEXT
            )

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
        print("========== VERIFY ERROR ==========")
        print(error)
        print("CHANNEL =", CHANNEL_USERNAME)
        print("GROUP =", GROUP_USERNAME)
        print("==================================")

        await callback.answer(
            "Please join the channel and support group first.",
            show_alert=True,
        )


@dp.callback_query(F.data == "accept_terms")
async def accept_terms(callback: CallbackQuery):
    track_user(
        callback.from_user.id,
        callback.from_user.username
    )

    if is_user_banned(callback.from_user.id):
        await callback.answer("Access blocked.", show_alert=True)
        return

    await flash_effect(callback, FLASH_ACCEPT_TEXT)
    await callback.message.edit_text(
        "✨ <b>Terms accepted.</b>\n\n"
        "<blockquote>Cutie AI has unlocked your premium coupon dashboard.</blockquote>"
    )

    menu = (
        admin_main_menu()
        if str(callback.from_user.id) == str(ADMIN_ID)
        else user_main_menu()
    )

    await callback.message.answer(
        "🏠 <b>Main Menu</b>",
        reply_markup=menu,
    )
    await callback.answer()


@dp.callback_query(F.data == "decline_terms")
async def decline_terms(callback: CallbackQuery):
    await flash_effect(callback, "🚫 <b>ACCESS PAUSED</b>\n\n<blockquote>Cutie will wait until you are ready.</blockquote>")
    await callback.message.edit_text(
        "🚫 <b>You must accept the Terms and Conditions to use this bot.</b>"
    )
    await callback.answer()


@dp.message(F.text == BTN_DEAL_VAULT)
async def buy_coupons(message: Message):
    if await reject_if_banned(message):
        return

    options = get_coupon_type_options()

    if not options:
        await message.answer(
            "😔 <b>No active coupons right now.</b>\n\n"
            "<blockquote>Cutie will show deals here as soon as admin uploads stock.</blockquote>"
        )
        return

    lines = []

    for option in options[:12]:
        lines.append(
            f"🎟 <code>{option['coupon_name']}</code>\n"
            f"💎 Rs {option['discount']} OFF • Min Rs {option['minimum']}\n"
            f"📦 Stock <b>{option['stock']}</b> • 💰 Price <b>Rs {option['price']}</b>"
        )

    await message.answer(
        "⚡ <b>Premium Deal Vault</b>\n\n"
        f"<blockquote>{chr(10).join(lines)}</blockquote>\n\n"
        "<i>Cutie says: tap Buy Now and I will prepare it fast.</i>",
        reply_markup=coupon_list_keyboard(options[:12]),
    )


@dp.callback_query(F.data == "buy_bb_coupon")
async def buy_bb_coupon(callback: CallbackQuery):
    await flash_effect(callback, FLASH_ORDER_TEXT)
    stock = get_coupon_stock(COUPON_NAME)

    if stock <= 0:
        await callback.message.answer("😔 <b>Out of stock.</b>\n\n<blockquote>Cutie will watch for the next refill.</blockquote>")
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
            "💔 <b>Order creation failed.</b>\n\n"
            "<blockquote>Please try again or contact support. Cutie saved the error path.</blockquote>"
        )
        await callback.answer()
        return

    await callback.message.answer(
        "✨ <b>Order Created</b>\n\n"
        f"<blockquote>🆔 Order ID: <code>{order_id}</code>\n"
        f"🎟 Coupon: <code>{COUPON_NAME}</code>\n"
        f"💰 Amount: <b>Rs {price}</b>\n"
        "⏳ Status: <i>Pending Payment</i></blockquote>",
        reply_markup=payment_keyboard(order_id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_type_"))
async def buy_coupon_type(callback: CallbackQuery):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Access blocked.", show_alert=True)
        return

    await flash_effect(callback, FLASH_ORDER_TEXT)
    coupon_id = int(callback.data.replace("buy_type_", ""))
    coupon = get_coupon_by_id(coupon_id)

    if not coupon or coupon.sold:
        await callback.message.answer(
            "😔 <b>This coupon just went out of stock.</b>\n\n"
            "<blockquote>Open Deal Vault again for fresh options.</blockquote>"
        )
        await callback.answer()
        return

    stock = get_coupon_stock(coupon.coupon_name)

    if stock <= 0:
        await callback.message.answer("😔 <b>Out of stock.</b>")
        await callback.answer()
        return

    order_id = create_order(
        callback.from_user.id,
        coupon.coupon_name,
        coupon.selling_price,
    )

    if not order_id:
        await callback.message.answer(
            "💔 <b>Order creation failed.</b>\n\n"
            "<blockquote>Please try again or contact support.</blockquote>"
        )
        await callback.answer()
        return

    await callback.message.answer(
        "✨ <b>Order Created</b>\n\n"
        f"<blockquote>🆔 Order ID: <code>{order_id}</code>\n"
        f"🎟 Coupon: <code>{coupon.coupon_name}</code>\n"
        f"💰 Amount: <b>Rs {coupon.selling_price}</b>\n"
        "⏳ Status: <i>Pending Payment</i></blockquote>",
        reply_markup=payment_keyboard(order_id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def pay_order(callback: CallbackQuery):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    order_id = callback.data.replace("pay_", "")
    await flash_effect(callback, FLASH_PAYMENT_TEXT)
    from database.crud import get_order_by_id

    order = get_order_by_id(order_id)

    if not order:
        await callback.message.answer("💔 <b>Order not found.</b>")
        await callback.answer()
        return

    price = order.amount

    data = create_cashfree_payment_link(
        order_id=order_id,
        amount=price,
        customer_id=callback.from_user.id,
    )

    if "payment_session_id" not in data:
        await callback.message.answer(
            "💔 <b>Payment Error</b>\n\n"
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
                    text="💳 Pay Securely",
                    url=payment_url,
                )
            ]
        ]
    )

    await callback.message.answer(
        "💳 <b>Payment Ready</b>\n\n"
        f"<blockquote>🆔 Order: <code>{order_id}</code>\n"
        f"💰 Amount: <b>Rs {price}</b></blockquote>\n\n"
        "<i>Cutie prepared your secure checkout.</i>",
        reply_markup=markup,
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_order(callback: CallbackQuery):
    order_id = callback.data.replace("cancel_", "")
    await flash_effect(callback, FLASH_CANCEL_TEXT)
    update_order_status(order_id, "CANCELLED")

    await callback.message.answer(
        f"🚫 <b>Order cancelled.</b>\n\nOrder ID: <code>{order_id}</code>"
    )
    await callback.answer()


@dp.message(F.text == BTN_ACCESS_LOG)
async def my_orders(message: Message):
    if await reject_if_banned(message):
        return

    orders = get_user_orders(message.from_user.id)

    if not orders:
        await message.answer("📂 <b>No orders found.</b>\n\n<blockquote>Cutie is ready when you make your first deal.</blockquote>")
        return

    text = "📂 <b>Your Orders</b>\n\n"

    for order in orders[:10]:
        text += (
            f"<blockquote>🆔 Order: <code>{order.order_id}</code>\n"
            f"🎟 Coupon: <code>{order.coupon_name}</code>\n"
            f"💰 Amount: <b>Rs {order.amount}</b>\n"
            f"💳 Payment: <i>{order.payment_status}</i>\n"
            f"🚚 Delivery: <i>{order.delivery_status}</i></blockquote>\n"
        )

    await message.answer(text)


@dp.message(F.text == BTN_PROFILE)
async def profile(message: Message):
    if await reject_if_banned(message):
        return

    user = message.from_user

    await message.answer(
        "⚙️ <b>Profile</b>\n\n"
        f"<blockquote>🆔 ID: <code>{user.id}</code>\n"
        f"💖 Name: <b>{user.first_name}</b>\n"
        "🤖 Assistant: <b>Cutie AI</b></blockquote>"
    )


@dp.message(F.text == "Referral")
async def referral(message: Message):
    await message.answer(
        "🎁 <b>Referral Program</b>\n\n"
        "<i>Your referral link:</i>\n"
        f"<code>https://t.me/{BOT_USERNAME}?start={message.from_user.id}</code>"
    )


@dp.message(F.text == BTN_SUPPORT)
async def support(message: Message):
    if await reject_if_banned(message):
        return

    await message.answer(
        "📢 <b>Support</b>\n\n"
        f"<blockquote>💬 Contact: <code>{GROUP_USERNAME}</code>\n"
        "Send your Order ID and payment screenshot if delivery failed.\n"
        "Cutie will help you explain the issue clearly.</blockquote>"
    )


@dp.message(F.text == BTN_AI_ASSIST)
async def ai_assist_start(message: Message, state: FSMContext):
    if await reject_if_banned(message):
        return

    await state.set_state(AIAssist.waiting_for_question)
    await message.answer(
        "💖 <b>Cutie AI</b>\n\n"
        "<blockquote>I can sense worried, confused, excited, or upset messages "
        "and reply with the right support style. Ask me about payments, orders, "
        "coupon delivery, stock, bugs, or admin uploads.</blockquote>\n\n"
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
