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
    add_feedback,
    add_wallet_credit,
    add_wallet_credit_once,
    create_order,
    create_referral,
    create_support_ticket,
    delete_bot_setting,
    get_bot_setting,
    get_coupon_by_id,
    get_coupon_stock,
    get_coupon_type_options,
    get_active_flash_sales,
    get_active_flash_sale_for_coupon,
    get_order_by_id,
    get_referral_count,
    get_user_orders,
    get_wallet_balance,
    get_wallet_transactions,
    is_user_banned,
    refund_order_wallet_if_needed,
    reward_referral_if_needed,
    save_order_coupon_code,
    save_payment_session,
    set_bot_setting,
    subscribe_stock_alert,
    track_user,
    update_delivery_status,
    update_order_status,
    update_user_login_streak,
    get_eligible_coupons,
    claim_coupon_for_user,
    mark_milestone_claimed,
    get_user_by_telegram_id,
)
from database.db import initialize_database
from database.models import Base
from database.payment import create_cashfree_payment_link, get_cashfree_order_status
from handlers.admin import router as admin_router
from keyboards.shop import coupon_list_keyboard, payment_keyboard
from keyboards.user import admin_main_menu, join_keyboard, terms_keyboard, user_main_menu
from services.ai_assistant import get_ai_answer
from services.coupon_service import deliver_coupon
from services.stock_alerts import notify_stock_alerts, should_send_stock_alert
from states.order_states import AIAssist, FeedbackState, SupportTicketState, WalletTopUpState
from texts import (
    BOT_USERNAME,
    BTN_ACCESS_LOG,
    BTN_AI_ASSIST,
    BTN_DEAL_VAULT,
    BTN_PROFILE,
    BTN_RAISE_TICKET,
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


async def send_progress_messages(message: Message, frames, delay=0.3):
    for text in frames:
        try:
            await message.answer(text)
        except Exception:
            pass
        await asyncio.sleep(delay)


def feedback_keyboard(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data=f"feedback_{order_id}_1"),
                InlineKeyboardButton(text="2", callback_data=f"feedback_{order_id}_2"),
                InlineKeyboardButton(text="3", callback_data=f"feedback_{order_id}_3"),
                InlineKeyboardButton(text="4", callback_data=f"feedback_{order_id}_4"),
                InlineKeyboardButton(text="5", callback_data=f"feedback_{order_id}_5"),
            ],
            [InlineKeyboardButton(text="Skip", callback_data=f"feedback_{order_id}_0")],
        ]
    )


async def flash_effect(callback: CallbackQuery, text: str):
    try:
        await callback.message.edit_text(text)
    except Exception:
        pass


async def payment_energy_effect(callback: CallbackQuery):
    frames = [
        "🚀 <b>Payment Ready</b>\n\n<blockquote>⚡ Charging...</blockquote>",
        "🚀 <b>Payment Ready</b>\n\n<blockquote>💥 Core energy active</blockquote>",
        "🚀 <b>Payment Ready</b>\n\n<blockquote>⭐ Secure checkout ready</blockquote>",
    ]
    for text in frames:
        try:
            await callback.message.edit_text(text)
        except Exception:
            pass
        await asyncio.sleep(0.3)


async def energy_collecting_effect(callback: CallbackQuery):
    frames = [
        "⚡ <b>Energy Collecting</b>\n\n<blockquote>🔢 Core syncing...</blockquote>",
        "⚡ <b>Energy Collecting</b>\n\n<blockquote>🔣 Power rising...</blockquote>",
        "⚡ <b>Energy Collecting</b>\n\n<blockquote>✅ Core fully charged</blockquote>",
    ]
    for text in frames:
        try:
            await callback.message.edit_text(text)
        except Exception:
            pass
        await asyncio.sleep(0.3)


async def coupon_reveal_effect(message: Message):
    frames = [
        "💨 <b>Vault Unlocking</b>\n\n<blockquote>🔍 Scanning stock...</blockquote>",
        "💨 <b>Vault Unlocking</b>\n\n<blockquote>🌟 Loading deals...</blockquote>",
        "💬 <b>Deal Vault Ready</b>\n\n<blockquote>🌟 Fresh stock unlocked</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def ai_typing_effect(message: Message):
    frames = [
        "🤖 <b>Cutie Thinking</b>\n\n<blockquote>📧 Analyzing question...</blockquote>",
        "🤖 <b>Cutie Thinking</b>\n\n<blockquote>📚 Searching knowledge...</blockquote>",
        "🤖 <b>Cutie Ready</b>\n\n<blockquote>✅ Answer prepared</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def ticket_beam_effect(message: Message):
    frames = [
        "🎨 <b>Creating Ticket</b>\n\n<blockquote>🚀 Sending to admin...</blockquote>",
        "🎨 <b>Creating Ticket</b>\n\n<blockquote>🔔 Notifying support...</blockquote>",
        "🎨 <b>Ticket Created</b>\n\n<blockquote>✅ Admin will respond soon</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def referral_success_effect(message: Message):
    frames = [
        "🎆 <b>Referral Linked</b>\n\n<blockquote>🔗 Validating link...</blockquote>",
        "🎆 <b>Referral Linked</b>\n\n<blockquote>💢 Tracking referrer...</blockquote>",
        "🎉 <b>Referral Complete</b>\n\n<blockquote>🌟 Reward unlocks after purchase</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def order_delivery_effect(message: Message):
    frames = [
        "🚀 <b>Processing Order</b>\n\n<blockquote>📦 Preparing coupon...</blockquote>",
        "🚀 <b>Processing Order</b>\n\n<blockquote>📫 Encoding code...</blockquote>",
        "🌟 <b>Order Ready</b>\n\n<blockquote>✅ Your coupon is here!</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def premium_boot_effect(message: Message):
    frames = [
        "🔐 <b>FlashX Initializing</b>\n\n<blockquote>🔍 Loading interface...</blockquote>",
        "🔐 <b>FlashX Initializing</b>\n\n<blockquote>📊 Syncing data...</blockquote>",
        "✨ <b>FlashX Ready</b>\n\n<blockquote>📄 Premium interface active</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def vault_sync_effect(message: Message):
    frames = [
        "💫 <b>Vault Syncing</b>\n\n<blockquote>⚡ Connecting...</blockquote>",
        "💫 <b>Vault Syncing</b>\n\n<blockquote>📦 Loading inventory...</blockquote>",
        "🌟 <b>Vault Ready</b>\n\n<blockquote>📄 Premium coupons available</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def wallet_charge_effect(message: Message):
    frames = [
        "💰 <b>Wallet Loading</b>\n\n<blockquote>⚡ Reading balance...</blockquote>",
        "💰 <b>Wallet Loading</b>\n\n<blockquote>💸 Verifying credits...</blockquote>",
        "💲 <b>Wallet Ready</b>\n\n<blockquote>✅ Credits confirmed</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def referral_orbit_effect(message: Message):
    frames = [
        "🌙 <b>Referral Orbiting</b>\n\n<blockquote>😁 Spinning link...</blockquote>",
        "🌛 <b>Referral Orbiting</b>\n\n<blockquote>🌟 Collecting data...</blockquote>",
        "🌜 <b>Referral Complete</b>\n\n<blockquote>✅ Referral tracked successfully</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def user_ai_effect(message: Message):
    frames = [
        "🤖 <b>Cutie AI</b>\n\n<blockquote>🔍 Analyzing...</blockquote>",
        "🤖 <b>Cutie AI</b>\n\n<blockquote>🌟 Processing...</blockquote>",
        "🤗 <b>Cutie Ready</b>\n\n<blockquote>✅ Response prepared</blockquote>",
    ]
    await send_progress_messages(message, frames)


async def referral_link_effect(message: Message):
    frames = [
        "🔗 <b>Referral Link</b>\n\n<blockquote>🔍 Generating invite...</blockquote>",
        "🔗 <b>Referral Link</b>\n\n<blockquote>📋 Encoding data...</blockquote>",
        "🎁 <b>Referral Saved</b>\n\n<blockquote>✅ Invite unlocks after purchase</blockquote>",
    ]
    await send_progress_messages(message, frames)


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
        referrer_id = int(parts[1])
        if referrer_id != message.from_user.id:
            set_bot_setting(
                f"pending_referral:{message.from_user.id}",
                str(referrer_id),
            )
            await referral_link_effect(message)

    if await reject_if_banned(message):
        return

    await premium_boot_effect(message)
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

    pending_referral = get_bot_setting(f"pending_referral:{callback.from_user.id}", "")
    if pending_referral and pending_referral.isdigit():
        created = create_referral(
            int(pending_referral),
            callback.from_user.id,
            0,
        )
        delete_bot_setting(f"pending_referral:{callback.from_user.id}")
        if created:
            await callback.message.answer(
                "🎁 <b>Referral saved</b>\n\n"
                "<blockquote>Your referrer will receive credit after you make your first purchase.</blockquote>"
            )

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


@dp.callback_query(F.data.startswith("claim_reward_"))
async def claim_reward_callback(callback: CallbackQuery):
    if await reject_if_banned(callback.message):
        await callback.answer()
        return

    parts = callback.data.split("_")
    milestone = int(parts[-1]) if parts[-1].isdigit() else None
    if milestone not in (15, 30):
        await callback.answer("Invalid reward.")
        return

    # list eligible coupons
    max_price = 10 if milestone == 30 else None
    if max_price is not None:
        eligible = get_eligible_coupons(max_price=max_price)
    else:
        eligible = get_eligible_coupons()

    if not eligible:
        await callback.message.answer("😔 <b>No eligible coupons available right now.</b>")
        await callback.answer()
        return

    keyboard = []
    for c in eligible:
        keyboard.append([InlineKeyboardButton(text=f"{c.coupon_name} • Rs {c.selling_price}", callback_data=f"claim_coupon_{c.id}_{milestone}")])

    await callback.message.answer("🎟 <b>Select your reward coupon</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@dp.callback_query(F.data.startswith("claim_coupon_"))
async def claim_coupon_callback(callback: CallbackQuery):
    if await reject_if_banned(callback.message):
        await callback.answer()
        return

    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Invalid selection.")
        return

    try:
        coupon_id = int(parts[2])
        milestone = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
    except Exception:
        await callback.answer("Invalid selection.")
        return

    code = claim_coupon_for_user(coupon_id, callback.from_user.id)
    if not code:
        await callback.message.answer("⚠️ <b>Could not claim that coupon. It may have been taken.</b>")
        await callback.answer()
        return

    # mark milestone claimed
    mark_milestone_claimed(callback.from_user.id, milestone)

    await callback.message.answer(
        f"🎉 <b>Coupon claimed!</b>\n\n<blockquote>Your code: <code>{escape(code)}</code></blockquote>"
    )
    await callback.answer()


@dp.message(F.text == BTN_DEAL_VAULT)
async def buy_coupons(message: Message):
    if await reject_if_banned(message):
        return

    await vault_sync_effect(message)
    await coupon_reveal_effect(message)
    options = get_coupon_type_options()
    flash_sales = get_active_flash_sales()
    sales_by_coupon = {sale.coupon_name: sale for sale in flash_sales}

    if not options:
        await message.answer(
            "😔 <b>No active coupons right now.</b>\n\n"
            "<blockquote>Cutie will show deals here as soon as admin uploads stock.</blockquote>"
        )
        return

    lines = []

    for option in options[:12]:
        sale = sales_by_coupon.get(option["coupon_name"])
        option["flash_sale"] = bool(sale)
        sale_line = (
            f"\nSALE: <b>{escape(sale.title)}</b> - <i>{escape(sale.discount_text)}</i>"
            if sale
            else ""
        )
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


    if flash_sales:
        sale_lines = [
            f"SALE: <b>{escape(sale.title)}</b> - <code>{escape(sale.coupon_name)}</code> - <i>{escape(sale.discount_text)}</i>"
            for sale in flash_sales
        ]
        await message.answer(
            "<b>FlashX Sale</b>\n\n"
            f"<blockquote>{chr(10).join(sale_lines)}</blockquote>\n\n"
            "<i>Choose the matching coupon above to use this sale stock.</i>"
        )


@dp.callback_query(F.data.startswith("buy_type_"))
async def buy_coupon_type(callback: CallbackQuery, bot: Bot):
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

    order_id = create_order(callback.from_user.id, coupon.coupon_name, coupon.selling_price, use_wallet=True)

    if not order_id:
        await callback.message.answer(
            "💔 <b>Order creation failed.</b>\n\n"
            "<blockquote>Please try again or contact support.</blockquote>"
        )
        await callback.answer()
        return

    order = get_order_by_id(order_id)
    payable_amount = order.payable_amount if order else coupon.selling_price
    wallet_used = order.wallet_used if order else 0

    if payable_amount == 0:
        delivered, detail = await finalize_paid_order(order_id, bot)
        if not delivered:
            await callback.message.answer(
                "⚠️ <b>Wallet purchase needs admin support.</b>\n\n"
                f"<blockquote>{escape(detail)}</blockquote>"
            )
        else:
            await callback.message.answer(
                "✅ <b>Coupon paid from wallet credits.</b>"
            )
        await callback.answer()
        return

    await callback.message.answer(
        "✨ <b>Order Created</b>\n\n"
        f"<blockquote>🆔 Order ID: <code>{order_id}</code>\n"
        f"🎟 Coupon: <code>{escape(coupon.coupon_name)}</code>\n"
        f"💰 Amount: <b>Rs {coupon.selling_price}</b>\n"
        f"💎 Wallet Used: <b>Rs {wallet_used}</b>\n"
        f"⏳ Pay Now: <i>Rs {payable_amount}</i></blockquote>",
        reply_markup=payment_keyboard(order_id),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("pay_"))
async def pay_order(callback: CallbackQuery):
    order_id = callback.data.replace("pay_", "")
    await flash_effect(callback, FLASH_PAYMENT_TEXT)
    await energy_collecting_effect(callback)
    await payment_energy_effect(callback)
    order = get_order_by_id(order_id)

    if not order:
        await callback.message.answer("💔 <b>Order not found.</b>")
        await callback.answer()
        return

    data = create_cashfree_payment_link(
        order_id=order_id,
        amount=order.payable_amount or order.amount,
        customer_id=callback.from_user.id,
    )

    if "payment_session_id" not in data:
        refunded = refund_order_wallet_if_needed(order_id, "Payment setup refund")
        update_order_status(order_id, "FAILED")
        await callback.message.answer(
            "💔 <b>Payment Error</b>\n\n"
            f"<blockquote>{format_payment_error(data)}</blockquote>\n\n"
            "<i>Admin should check Cashfree credentials, PUBLIC_BASE_URL, and webhook URL.</i>"
            + ("\n\n<b>Wallet credits were returned.</b>" if refunded else "")
        )
        await callback.answer()
        return

    save_payment_session(order_id, data["payment_session_id"])
    await flash_effect(
        callback,
        "✅ <b>Payment Link Ready</b>\n\n<blockquote>🟡 🟠 🔵 🟣 🟢 Cutie prepared secure checkout</blockquote>",
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
        f"💰 Amount Due: <b>Rs {order.payable_amount or order.amount}</b>\n"
        f"💎 Wallet Used: <b>Rs {order.wallet_used or 0}</b></blockquote>\n\n"
        "<i>Cutie prepared your secure checkout.</i>",
        reply_markup=markup,
    )
    await callback.answer()


async def finalize_paid_order(order_id, bot: Bot):
    order = get_order_by_id(order_id)

    if not order:
        return False, "Order not found."

    if order.delivery_status == "DELIVERED":
        return True, "Already delivered."

    if order.coupon_name == "WALLET_TOPUP":
        add_wallet_credit_once(order.user_id, order.amount, f"Wallet top up for {order.order_id}")
        update_order_status(order_id, "SUCCESS")
        update_delivery_status(order_id, "DELIVERED")

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
        return True, "Wallet topped up"

    coupon_code, remaining_stock = deliver_coupon(order.coupon_name)

    if not coupon_code:
        refund_order_wallet_if_needed(order_id, "Delivery refund")
        return False, "No unsold coupon stock available for this order."

    update_order_status(order_id, "SUCCESS")
    update_delivery_status(order_id, "DELIVERED")
    save_order_coupon_code(order_id, coupon_code)
    reward_referral_if_needed(order.user_id, 1)

    if should_send_stock_alert(remaining_stock):
        await notify_stock_alerts(
            bot,
            order.coupon_name,
            remaining_stock,
            reason="low_stock" if remaining_stock > 0 else "sold_out",
        )

    delivery_intro = await bot.send_message(
        chat_id=order.user_id,
        text="📦 <b>Finalizing delivery</b>\n\n<blockquote>Cutie is unlocking your coupon now...</blockquote>",
    )
    await order_delivery_effect(delivery_intro)

    await bot.send_message(
        chat_id=order.user_id,
        text=(
            "🎉 <b>Payment Successful</b>\n\n"
            f"<blockquote>🆔 Order: <code>{order.order_id}</code>\n"
            f"🎟 Coupon Code:\n<code>{coupon_code}</code></blockquote>\n\n"
            "<i>Cutie delivered it for you.</i>"
        ),
    )
    await bot.send_message(
        chat_id=order.user_id,
        text=(
            "<b>How was this purchase?</b>\n\n"
            "<blockquote>Your feedback becomes Cutie AI memory so the bot can improve future support.</blockquote>"
        ),
        reply_markup=feedback_keyboard(order.order_id),
    )
    return True, coupon_code


@dp.callback_query(F.data.startswith("recheck_"))
async def recheck_payment(callback: CallbackQuery, bot: Bot):
    order_id = callback.data.replace("recheck_", "")
    order = get_order_by_id(order_id)
    
    if not order:
        await callback.message.answer("⚠️ <b>Order not found.</b>")
        await callback.answer()
        return
    
    if order.delivery_status == "DELIVERED":
        await callback.message.answer(
            "✅ <b>Order already delivered.</b>\n\n"
            f"<blockquote>Order ID: <code>{order_id}</code></blockquote>"
        )
        await callback.answer()
        return
    
    if order.payment_status == "SUCCESS":
        await callback.message.answer(
            "✅ <b>Payment already verified.</b>\n\n"
            f"<blockquote>Your coupon is being prepared.</blockquote>"
        )
        await callback.answer()
        return
    
    data = get_cashfree_order_status(order_id)
    
    if "error" in data:
        await callback.message.answer(
            "⚠️ <b>Cannot verify payment status.</b>\n\n"
            f"<blockquote>Please try again later or contact support.</blockquote>"
        )
        await callback.answer()
        return
    
    status = (
        data.get("order_status")
        or data.get("payment_status")
        or data.get("status")
        or ""
    ).upper()

    if status == "PAID":
        delivered, detail = await finalize_paid_order(order_id, bot)
        if delivered:
            await callback.message.answer("✅ <b>Payment verified & coupon delivered.</b>")
        else:
            await callback.message.answer(
                "⚠️ <b>Payment verified, but delivery needs admin support.</b>\n\n"
                f"<blockquote>{escape(detail)}</blockquote>"
            )
    else:
        await callback.message.answer(
            "⏳ <b>Payment not confirmed yet.</b>\n\n"
            f"<blockquote>Status: <code>{escape(str(status or 'Unknown'))}</code>\n\n"
            "Please complete the payment through the link and try again.</blockquote>"
        )

    await callback.answer()


@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_order(callback: CallbackQuery):
    order_id = callback.data.replace("cancel_", "")
    await flash_effect(callback, FLASH_CANCEL_TEXT)
    order = get_order_by_id(order_id)

    if order and (
        order.payment_status == "SUCCESS"
        or order.delivery_status == "DELIVERED"
    ):
        await callback.message.answer(
            "⚠️ <b>This order is already completed.</b>\n\n"
            f"Order ID: <code>{order_id}</code>"
        )
        await callback.answer()
        return

    refunded = refund_order_wallet_if_needed(order_id, "Order cancel refund")
    update_order_status(order_id, "CANCELLED")
    await callback.message.answer(
        f"🚫 <b>Order cancelled.</b>\n\n"
        f"Order ID: <code>{order_id}</code>"
        + ("\n\n<b>Wallet credits were returned.</b>" if refunded else "")
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("feedback_"))
async def feedback_rating(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Invalid feedback.")
        return

    order_id = parts[1]
    try:
        rating = int(parts[2])
    except ValueError:
        rating = 0

    order = get_order_by_id(order_id)
    if not order or str(order.user_id) != str(callback.from_user.id):
        await callback.answer("Feedback does not match your order.", show_alert=True)
        return

    if rating <= 0:
        add_feedback(callback.from_user.id, order_id, 0, "Skipped written feedback")
        await callback.message.answer(
            "<b>Feedback skipped.</b>\n\n"
            "<blockquote>Cutie still remembers that this order completed.</blockquote>"
        )
        await callback.answer()
        return

    await state.update_data(order_id=order_id, rating=rating)
    await state.set_state(FeedbackState.waiting_for_message)
    await callback.message.answer(
        "<b>Tell Cutie one line</b>\n\n"
        f"<blockquote>Rating saved: <b>{rating}/5</b>\n"
        "Send what felt good or what should improve.</blockquote>"
    )
    await callback.answer()


@dp.message(FeedbackState.waiting_for_message)
async def feedback_message(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    rating = int(data.get("rating") or 0)
    feedback_text = (message.text or "").strip()

    feedback_id = add_feedback(message.from_user.id, order_id, rating, feedback_text)
    if feedback_id:
        await message.answer(
            "<b>Feedback saved.</b>\n\n"
            "<blockquote>Cutie AI added this to bot memory for future support and improvements.</blockquote>"
        )
    else:
        await message.answer(
            "<b>Feedback could not be saved.</b>\n\n"
            "<blockquote>Your order is still completed. Please try feedback again later.</blockquote>"
        )

    await state.clear()


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

    await wallet_charge_effect(message)
    balance = get_wallet_balance(message.from_user.id)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Top Up Wallet", callback_data="wallet_topup")],
            [InlineKeyboardButton(text="Wallet History", callback_data="wallet_history")],
        ]
    )
    await message.answer(
        "<b>FLASHX ATM</b>\n\n"
        f"<blockquote>Card Status: <b>ACTIVE</b>\n"
        f"Available Credits: <b>Rs {balance}</b>\n"
        f"Cash-out Value: <b>{balance} credits</b>\n"
        "Wallet credits can pay for coupons, refunds, referral rewards, and premium perks.</blockquote>\n\n"
        "<i>Top up any positive amount. No minimum balance required.</i>",
        reply_markup=markup,
    )


@dp.callback_query(F.data == "wallet_history")
async def wallet_history(callback: CallbackQuery):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Access blocked.", show_alert=True)
        return

    balance = get_wallet_balance(callback.from_user.id)
    transactions = get_wallet_transactions(callback.from_user.id, limit=10)

    if not transactions:
        await callback.message.answer(
            "📜 <b>Wallet History</b>\n\n"
            f"<blockquote>Balance: <b>Rs {balance}</b>\n"
            "No wallet transactions yet.</blockquote>"
        )
        await callback.answer()
        return

    lines = []
    for tx in transactions:
        sign = "+" if tx.amount >= 0 else "-"
        amount = abs(tx.amount)
        lines.append(
            f"{sign} <b>Rs {amount}</b> • {escape(tx.reason or 'Wallet update')}"
        )

    await callback.message.answer(
        "📜 <b>Wallet History</b>\n\n"
        f"<blockquote>Balance: <b>Rs {balance}</b>\n\n"
        f"{chr(10).join(lines)}</blockquote>\n\n"
        "<i>Top ups, referral rewards, and coupon spends appear here.</i>"
    )
    await callback.answer()


@dp.callback_query(F.data == "wallet_topup")
async def wallet_topup_start(callback: CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Access blocked.", show_alert=True)
        return

    await state.set_state(WalletTopUpState.waiting_for_amount)
    await callback.message.answer(
        "<b>Wallet Top Up</b>\n\n"
        "<blockquote>Send any positive amount you want to add to your wallet.\n"
        "Example: <code>1</code> or <code>250</code></blockquote>\n\n"
        "<i>No minimum balance. The wallet accepts small and large top ups.</i>"
    )
    await callback.answer()


@dp.message(WalletTopUpState.waiting_for_amount)
async def wallet_topup_amount(message: Message, state: FSMContext, bot: Bot):
    if await reject_if_banned(message):
        return

    try:
        amount = int((message.text or "").strip())
    except ValueError:
        await message.answer("Send a numeric amount only, example: <code>100</code>")
        return

    if amount <= 0:
        await message.answer("Top up amount must be more than <b>0</b>.")
        return

    order_id = create_order(
        message.from_user.id,
        "WALLET_TOPUP",
        amount,
        use_wallet=False,
    )

    if not order_id:
        await message.answer(
            "💔 <b>Could not create wallet top up order.</b>\n\n"
            "<blockquote>Please try again.</blockquote>"
        )
        await state.clear()
        return

    order = get_order_by_id(order_id)
    data = create_cashfree_payment_link(
        order_id=order_id,
        amount=amount,
        customer_id=message.from_user.id,
    )

    if "payment_session_id" not in data:
        update_order_status(order_id, "FAILED")
        await message.answer(
            "💔 <b>Wallet top up payment failed.</b>\n\n"
            f"<blockquote>{format_payment_error(data)}</blockquote>"
        )
        await state.clear()
        return

    save_payment_session(order_id, data["payment_session_id"])
    payment_url = (
        data.get("payment_link")
        or data.get("payment_url")
        or f"{PUBLIC_BASE_URL}/pay/{order_id}"
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Pay Wallet Top Up", url=payment_url)],
            [InlineKeyboardButton(text="🔁 I Paid, Recheck", callback_data=f"recheck_{order_id}")],
        ]
    )

    await message.answer(
        "💎 <b>Wallet Top Up Ready</b>\n\n"
        f"<blockquote>🆔 Order: <code>{order_id}</code>\n"
        f"💰 Amount: <b>Rs {order.amount}</b></blockquote>\n\n"
        "<i>Once payment is confirmed, your wallet balance will increase.</i>",
        reply_markup=markup,
    )
    await state.clear()


@dp.message(F.text == BTN_REFERRAL)
async def referral(message: Message):
    if await reject_if_banned(message):
        return

    await referral_orbit_effect(message)
    count = get_referral_count(message.from_user.id)
    await message.answer(
        "🎁 <b>Referral Program</b>\n\n"
        f"<blockquote>Your referrals: <b>{count}</b>\n"
        "Reward per valid referral: <b>Rs 1</b>\n"
        "1 credit = 1 Rs, and you can use it to redeem coupon orders.</blockquote>\n\n"
        "<i>Your referral link:</i>\n"
        f"<code>https://t.me/{BOT_USERNAME}?start={message.from_user.id}</code>"
    )


@dp.message(F.text == BTN_SUPPORT)
@dp.message(F.text == BTN_RAISE_TICKET)
async def support(message: Message, state: FSMContext):
    if await reject_if_banned(message):
        return

    await ticket_beam_effect(message)
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

    await user_ai_effect(message)
    await state.set_state(AIAssist.waiting_for_question)
    await message.answer(
        "💖 <b>Cutie AI</b>\n\n"
        "<blockquote>Ask me anything about this bot: orders, payments, wallet, referrals, tickets, "
        "admin tools, alerts, crashes, or how to use features.</blockquote>\n\n"
        "<i>Send your question now.</i>"
    )


@dp.message(AIAssist.waiting_for_question)
async def ai_assist_answer(message: Message, state: FSMContext):
    await ai_typing_effect(message)
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
