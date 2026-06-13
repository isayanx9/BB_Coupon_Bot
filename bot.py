import asyncio
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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
    create_referral,
    create_support_ticket,
    get_bot_setting,
    get_coupon_by_id,
    get_coupon_stock,
    get_coupon_type_options,
    get_order_by_id,
    get_referral_count,
    get_user_orders,
    get_wallet_balance,
    is_user_banned,
    reward_referral_if_needed,
    save_payment_session,
    subscribe_stock_alert,
    track_user,
    update_delivery_status,
    update_order_status,
)
from database.db import initialize_database
from database.models import Base
from database.payment import create_cashfree_payment_link, get_cashfree_order_status
from handlers.admin import router as admin_router
from keyboards.shop import coupon_list_keyboard, payment_keyboard
from keyboards.user import admin_main_menu, join_keyboard, terms_keyboard, user_main_menu
from services.ai_assistant import get_ai_answer
from services.coupon_service import deliver_coupon
from states.order_states import AIAssist, SupportTicketState
from texts import (
    BOT_USERNAME,
    BTN_ACCESS_LOG,
    BTN_AI_ASSIST,
    BTN_DEAL_VAULT,
    BTN_PROFILE,
    BTN_REFERRAL,
    BTN_STOCK_ALERTS,
    BTN_SUPPORT,
    BTN_WALLET,
    FLASH_ACCEPT_TEXT,
    FLASH_CANCEL_TEXT,
    FLASH_ORDER_TEXT,
    FLASH_PAYMENT_TEXT,
    FLASH_VERIFY_TEXT,
    TERMS_TEXT,
    WELCOME_TEXT,
)

dp = Dispatcher()


def format_payment_error(data):
    if not isinstance(data, dict):
        return escape(str(data))

    message = (
        data.get("message")
        or data.get("error")
        or data.get("hint")
        or "Payment gateway rejected this order."
    )
    code = data.get("code") or data.get("status_code") or "unknown"
    return (
        f"Code: <code>{escape(str(code))}</code>\n"
        f"Message: <i>{escape(str(message))}</i>"
    )


async def flash_effect(callback: CallbackQuery, text: str):
    try:
        await callback.message.edit_text(text)
        await asyncio.sleep(0.35)
    except Exception:
        pass


async def payment_energy_effect(callback: CallbackQuery):
    frames = [
        "💳 <b>Payment Core Starting</b>\n\n<blockquote>🟡 Energy ball charging\n███░░░░░░░ 30%</blockquote>",
        "⚡ <b>Gateway Sync</b>\n\n<blockquote>🟡 🟠 Secure route forming\n████░░░░░░ 40%</blockquote>",
        "🔐 <b>Cashfree Shield</b>\n\n<blockquote>🟡 🟠 🔵 Order lock active\n██████░░░░ 60%</blockquote>",
        "🚀 <b>Checkout Boost</b>\n\n<blockquote>🟡 🟠 🔵 🟣 Payment session ready\n████████░░ 80%</blockquote>",
    ]

    for frame in frames:
        await flash_effect(callback, frame)
        await asyncio.sleep(0.15)


async def reject_if_banned(message: Message):
    track_user(message.from_user.id, message.from_user.username)

    if is_user_banned(message.from_user.id):
        await message.answer(
            "🚫 <b>Access blocked.</b>\n\n"
            "<blockquote>Your account is restricted. Contact support if this is a mistake.</blockquote>"
        )
        return True

    if get_bot_setting("maintenance_mode", "off").lower() == "on":
        await message.answer(
            "🛠 <b>Maintenance mode</b>\n\n"
            f"<blockquote>{escape(get_bot_setting('maintenance_text', 'Cutie is upgrading the bot. Please try again soon.'))}</blockquote>"
        )
        return True

    return False


@dp.message(CommandStart())
async def start_command(message: Message):
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) == 2 and parts[1].isdigit():
        create_referral(
            int(parts[1]),
            message.from_user.id,
            int(get_bot_setting("referral_reward", "5")),
        )

    if await reject_if_banned(message):
        return

    await message.answer(WELCOME_TEXT, reply_markup=join_keyboard())


@dp.callback_query(F.data == "verify_user")
async def verify_user(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    try:
        channel_member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        group_member = await bot.get_chat_member(GROUP_USERNAME, user_id)
        valid_status = ["member", "administrator", "creator"]

        if channel_member.status in valid_status and group_member.status in valid_status:
            await flash_effect(callback, FLASH_VERIFY_TEXT)
            await callback.message.edit_text(TERMS_TEXT, reply_markup=terms_keyboard())
        else:
            await callback.answer("Join both the channel and support group first.", show_alert=True)
    except Exception as error:
        print(f"Verification error: {error}")
        await callback.answer("Please join the channel and support group first.", show_alert=True)


@dp.callback_query(F.data == "accept_terms")
async def accept_terms(callback: CallbackQuery):
    track_user(callback.from_user.id, callback.from_user.username)

    if is_user_banned(callback.from_user.id):
        await callback.answer("Access blocked.", show_alert=True)
        return

    await flash_effect(callback, FLASH_ACCEPT_TEXT)
    await callback.message.edit_text(
        "✨ <b>Terms accepted.</b>\n\n"
        "<blockquote>Cutie AI unlocked your premium coupon dashboard.</blockquote>"
    )

    menu = admin_main_menu() if str(callback.from_user.id) == str(ADMIN_ID) else user_main_menu()
    await callback.message.answer("🏠 <b>Main Menu</b>", reply_markup=menu)
    await callback.answer()


@dp.callback_query(F.data == "decline_terms")
async def decline_terms(callback: CallbackQuery):
    await flash_effect(
        callback,
        "🚫 <b>ACCESS PAUSED</b>\n\n<blockquote>Cutie will wait until you are ready.</blockquote>",
    )
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
            f"🎟 <code>{escape(option['coupon_name'])}</code>\n"
            f"💎 Rs {option['discount']} OFF • Min Rs {option['minimum']}\n"
            f"📦 Stock <b>{option['stock']}</b> • 💰 Price <b>Rs {option['price']}</b>"
        )

    await message.answer(
        "⚡ <b>Premium Deal Vault</b>\n\n"
        f"<blockquote>{chr(10).join(lines)}</blockquote>\n\n"
        "<i>Cutie says: tap a deal and I will prepare it fast.</i>",
        reply_markup=coupon_list_keyboard(options[:12]),
    )


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

    if get_coupon_stock(coupon.coupon_name) <= 0:
        await callback.message.answer("😔 <b>Out of stock.</b>")
        await callback.answer()
        return

    order_id = create_order(callback.from_user.id, coupon.coupon_name, coupon.selling_price)

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
        f"🎟 Coupon: <code>{escape(coupon.coupon_name)}</code>\n"
        f"💰 Amount: <b>Rs {coupon.selling_price}</b>\n"
        "⏳ Status: <i>Pending Payment</i></blockquote>",
        reply_markup=payment_keyboard(order_id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def pay_order(callback: CallbackQuery):
    order_id = callback.data.replace("pay_", "")
    await flash_effect(callback, FLASH_PAYMENT_TEXT)
    await payment_energy_effect(callback)
    order = get_order_by_id(order_id)

    if not order:
        await callback.message.answer("💔 <b>Order not found.</b>")
        await callback.answer()
        return

    data = create_cashfree_payment_link(
        order_id=order_id,
        amount=order.amount,
        customer_id=callback.from_user.id,
    )

    if "payment_session_id" not in data:
        await callback.message.answer(
            "💔 <b>Payment Error</b>\n\n"
            f"<blockquote>{format_payment_error(data)}</blockquote>\n\n"
            "<i>Admin should check Cashfree credentials, PUBLIC_BASE_URL, and webhook URL.</i>"
        )
        await callback.answer()
        return

    save_payment_session(order_id, data["payment_session_id"])
    await flash_effect(
        callback,
        "✅ <b>Payment Link Ready</b>\n\n<blockquote>🟡 🟠 🔵 🟣 🟢 Cutie prepared secure checkout\n██████████ 100%</blockquote>",
    )
    payments = data.get("payments") if isinstance(data.get("payments"), dict) else {}
    payment_url = (
        data.get("payment_link")
        or data.get("payment_url")
        or payments.get("url")
        or f"{PUBLIC_BASE_URL}/pay/{order_id}"
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Pay Securely", url=payment_url)],
            [InlineKeyboardButton(text="🔁 I Paid, Recheck", callback_data=f"recheck_{order_id}")],
        ]
    )

    await callback.message.answer(
        "💳 <b>Payment Ready</b>\n\n"
        f"<blockquote>🆔 Order: <code>{order_id}</code>\n"
        f"💰 Amount: <b>Rs {order.amount}</b></blockquote>\n\n"
        "<i>Cutie prepared your secure checkout.</i>",
        reply_markup=markup,
    )
    await callback.answer()


async def deliver_paid_order(order_id, bot: Bot):
    order = get_order_by_id(order_id)

    if not order:
        return False, "Order not found."

    if order.delivery_status == "DELIVERED":
        return True, "Already delivered."

    coupon_code = deliver_coupon(order.coupon_name)

    if not coupon_code:
        return False, "No unsold coupon stock available for this order."

    update_order_status(order_id, "SUCCESS")
    update_delivery_status(order_id, "DELIVERED")
    reward_referral_if_needed(order.user_id, int(get_bot_setting("referral_reward", "5")))

    await bot.send_message(
        chat_id=order.user_id,
        text=(
            "🎉 <b>Payment Successful</b>\n\n"
            f"<blockquote>🆔 Order: <code>{order.order_id}</code>\n"
            f"🎟 Coupon Code:\n<code>{coupon_code}</code></blockquote>\n\n"
            "<i>Cutie delivered it for you.</i>"
        ),
    )
    return True, coupon_code


@dp.callback_query(F.data.startswith("recheck_"))
async def recheck_payment(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.replace("recheck_", "")
    data = get_cashfree_order_status(order_id)
    status = (
        data.get("order_status")
        or data.get("payment_status")
        or data.get("status")
        or ""
    ).upper()

    if status in {"PAID", "SUCCESS", "ACTIVE"}:
        delivered, detail = await deliver_paid_order(order_id, bot)
        if delivered:
            await callback.message.answer("✅ <b>Payment verified and coupon delivered.</b>")
        else:
            await callback.message.answer(
                "⚠️ <b>Payment verified, delivery needs admin.</b>\n\n"
                f"<blockquote>{escape(detail)}</blockquote>"
            )
    else:
        await callback.message.answer(
            "⏳ <b>Payment is not confirmed yet.</b>\n\n"
            f"<blockquote>Status: <code>{escape(str(status or data))}</code></blockquote>"
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


@dp.callback_query(F.data.startswith("stock_alert_"))
async def stock_alert_callback(callback: CallbackQuery):
    coupon_name = callback.data.replace("stock_alert_", "") or "ALL"
    subscribe_stock_alert(callback.from_user.id, coupon_name)
    await callback.message.answer(
        "🔔 <b>Stock alert enabled.</b>\n\n"
        "<blockquote>Cutie will notify you when fresh stock is uploaded.</blockquote>"
    )
    await callback.answer()


@dp.message(F.text == BTN_ACCESS_LOG)
async def my_orders(message: Message):
    if await reject_if_banned(message):
        return

    orders = get_user_orders(message.from_user.id)

    if not orders:
        await message.answer(
            "📂 <b>No orders found.</b>\n\n"
            "<blockquote>Cutie is ready when you make your first deal.</blockquote>"
        )
        return

    text = "📂 <b>Your Orders</b>\n\n"

    for order in orders[:10]:
        text += (
            f"<blockquote>🆔 Order: <code>{order.order_id}</code>\n"
            f"🎟 Coupon: <code>{escape(order.coupon_name)}</code>\n"
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
        f"💖 Name: <b>{escape(user.first_name or 'User')}</b>\n"
        "🤖 Assistant: <b>Cutie AI</b></blockquote>"
    )


@dp.message(F.text == BTN_WALLET)
async def wallet(message: Message):
    if await reject_if_banned(message):
        return

    balance = get_wallet_balance(message.from_user.id)
    await message.answer(
        "💎 <b>Wallet</b>\n\n"
        f"<blockquote>Available credits: <b>Rs {balance}</b>\n"
        "Credits can be used for refunds, referral rewards, and VIP perks.</blockquote>"
    )


@dp.message(F.text == BTN_REFERRAL)
async def referral(message: Message):
    if await reject_if_banned(message):
        return

    count = get_referral_count(message.from_user.id)
    await message.answer(
        "🎁 <b>Referral Program</b>\n\n"
        f"<blockquote>Your referrals: <b>{count}</b>\n"
        f"Reward per valid referral: <b>Rs {get_bot_setting('referral_reward', '5')}</b></blockquote>\n\n"
        "<i>Your referral link:</i>\n"
        f"<code>https://t.me/{BOT_USERNAME}?start={message.from_user.id}</code>"
    )


@dp.message(F.text == BTN_SUPPORT)
async def support(message: Message, state: FSMContext):
    if await reject_if_banned(message):
        return

    await state.set_state(SupportTicketState.waiting_for_message)
    await message.answer(
        "🎫 <b>Raise Ticket</b>\n\n"
        f"<blockquote>Support group: <code>{GROUP_USERNAME}</code>\n"
        "Send your issue in one message. Include Order ID, payment status, and screenshot details if needed.</blockquote>\n\n"
        "<i>Example: Payment debited for order FX123 but coupon not delivered.</i>"
    )


@dp.message(SupportTicketState.waiting_for_message)
async def support_ticket_create(message: Message, state: FSMContext, bot: Bot):
    issue = (message.text or "").strip()
    if not issue:
        await message.answer("Please send the issue as text so admin can understand it.")
        return

    subject = issue.splitlines()[0][:80] or "User support request"
    ticket_id = create_support_ticket(
        message.from_user.id,
        subject,
        issue,
    )

    if not ticket_id:
        await message.answer(
            "⚠️ <b>Ticket could not be created.</b>\n\n"
            "<blockquote>Please try again or contact support group directly.</blockquote>"
        )
        await state.clear()
        return

    await message.answer(
        "✅ <b>Ticket created.</b>\n\n"
        f"<blockquote>Ticket ID: <code>{ticket_id}</code>\n"
        "Status: <b>OPEN</b>\n"
        "Admin can reply from Control Center.</blockquote>\n\n"
        "<i>You will receive the admin reply here in this chat.</i>"
    )

    if ADMIN_ID:
        try:
            await bot.send_message(
                int(ADMIN_ID),
                "🎫 <b>New Support Ticket</b>\n\n"
                f"<blockquote>ID: <code>{ticket_id}</code>\n"
                f"User: <code>{message.from_user.id}</code>\n"
                f"Username: <code>@{escape(message.from_user.username or 'none')}</code>\n"
                f"Subject: <b>{escape(subject)}</b>\n\n"
                f"{escape(issue[:900])}</blockquote>\n\n"
                "Open <b>Control Center</b> -> <b>Reply Ticket</b> to answer.",
            )
        except Exception:
            pass

    await state.clear()


@dp.message(F.text == BTN_STOCK_ALERTS)
async def stock_alerts(message: Message):
    if await reject_if_banned(message):
        return

    subscribe_stock_alert(message.from_user.id, "ALL")
    await message.answer(
        "🔔 <b>Stock alerts enabled.</b>\n\n"
        "<blockquote>Cutie will notify you when admin uploads new coupons.</blockquote>"
    )


@dp.message(F.text == BTN_AI_ASSIST)
async def ai_assist_start(message: Message, state: FSMContext):
    if await reject_if_banned(message):
        return

    await state.set_state(AIAssist.waiting_for_question)
    await message.answer(
        "💖 <b>Cutie AI</b>\n\n"
        "<blockquote>Ask me anything about this bot: orders, payments, wallet, referrals, tickets, "
        "admin tools, alerts, crashes, or how to use features.</blockquote>\n\n"
        "<i>Send your question now.</i>"
    )


@dp.message(AIAssist.waiting_for_question)
async def ai_assist_answer(message: Message, state: FSMContext):
    answer = get_ai_answer(message.text or "")
    await message.answer(answer if "<" in answer else escape(answer))
    await state.clear()


async def main():
    require_env()
    initialize_database(Base)

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
