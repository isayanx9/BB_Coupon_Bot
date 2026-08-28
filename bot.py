import asyncio
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import (
    ADMIN_ID,
    BOT_TOKEN,
    CHANNEL_USERNAME,
    GROUP_USERNAME,
    PAYMENT_EXPIRY_MINUTES,
    PUBLIC_BASE_URL,
    require_env,
    RUN_BOT_POLLING,
)
from database.crud import (
    add_feedback,
    add_wallet_credit,
    create_order,
    create_referral,
    create_support_ticket,
    claim_order_delivery,
    delete_bot_setting,
    expire_order_if_needed,
    get_bot_setting,
    get_bulk_buyer_price,
    get_coupon_by_id,
    get_coupon_stock,
    get_coupon_type_options,
    get_order_by_id,
    get_referral_count,
    get_user_orders,
    get_wallet_balance,
    get_wallet_transactions,
    is_user_banned,
    refund_order_wallet_if_needed,
    release_order_delivery_claim,
    reward_referral_if_needed,
    save_order_coupon_code,
    save_payment_session,
    set_bot_setting,
    subscribe_stock_alert,
    track_user,
    update_delivery_status,
    update_order_status,
)
from database.db import initialize_database
from database.models import Base
from database.payment import create_cashfree_payment_link, get_cashfree_order_status
from handlers.admin import router as admin_router
from keyboards.admin import developer_menu
from keyboards.shop import coupon_list_keyboard, payment_keyboard
from keyboards.user import admin_main_menu, join_keyboard, launch_shop_keyboard, terms_keyboard, user_main_menu
from services.ai_assistant import get_ai_answer
from services.coupon_service import deliver_coupon, deliver_coupons
from services.stock_alerts import notify_stock_alerts, should_send_stock_alert
from states.order_states import AIAssist, FeedbackState, PurchaseQuantityState, SupportTicketState, WalletTopUpState
from texts import (
    BOT_USERNAME,
    BTN_ACCESS_LOG,
    BTN_AI_ASSIST,
    BTN_CONTROL_CENTER,
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


def is_configured_admin(user_id) -> bool:
    """The configured owner must always retain recovery access."""
    return bool(ADMIN_ID) and str(user_id) == str(ADMIN_ID)


@dp.message.outer_middleware()
async def restrict_user_messages(handler, event, data):
    """Keep the bot private-chat only, then apply availability checks.

    Admin traffic is deliberately excluded so the owner can turn maintenance
    off, inspect orders, and repair inventory even while users are paused.
    """
    if event.chat.type != ChatType.PRIVATE:
        # The shop, admin tools, and customer data must never be exposed in
        # groups.  Ignore all group messages without sending any response.
        return
    user = event.from_user
    if not user or is_configured_admin(user.id):
        return await handler(event, data)
    if is_user_banned(user.id):
        await event.answer("🚫 <b>Access blocked.</b>")
        return
    if get_bot_setting("maintenance_mode", "off").lower() == "on":
        await event.answer(
            "🛠 <b>Maintenance mode</b>\n\n"
            f"<blockquote>{escape(get_bot_setting('maintenance_text', 'Cutie is upgrading the bot. Please try again soon.'))}</blockquote>"
        )
        return
    return await handler(event, data)


@dp.callback_query.outer_middleware()
async def restrict_user_callbacks(handler, event, data):
    """Ignore group callbacks, then check private-chat button access."""
    if not event.message or event.message.chat.type != ChatType.PRIVATE:
        # Answering removes Telegram's loading spinner but sends no message.
        await event.answer()
        return
    if not is_configured_admin(event.from_user.id):
        if is_user_banned(event.from_user.id):
            await event.answer("Access blocked.", show_alert=True)
            return
        if get_bot_setting("maintenance_mode", "off").lower() == "on":
            await event.answer("The bot is under maintenance. Please try again soon.", show_alert=True)
            return
    return await handler(event, data)


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
    reveal = None
    for text in frames:
        if reveal:
            try:
                await reveal.edit_text(text)
            except Exception:
                pass
        else:
            reveal = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if reveal:
        await asyncio.sleep(0.5)
        try:
            await reveal.delete()
        except Exception:
            pass


async def ai_typing_effect(message: Message):
    frames = [
        "🤖 <b>Cutie Thinking</b>\n\n<blockquote>📧 Analyzing question...</blockquote>",
        "🤖 <b>Cutie Thinking</b>\n\n<blockquote>📚 Searching knowledge...</blockquote>",
        "🤖 <b>Cutie Ready</b>\n\n<blockquote>✅ Answer prepared</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def ticket_beam_effect(message: Message):
    frames = [
        "🎨 <b>Creating Ticket</b>\n\n<blockquote>🚀 Sending to admin...</blockquote>",
        "🎨 <b>Creating Ticket</b>\n\n<blockquote>🔔 Notifying support...</blockquote>",
        "🎨 <b>Ticket Created</b>\n\n<blockquote>✅ Admin will respond soon</blockquote>",
    ]
    beam = None
    for text in frames:
        if beam:
            try:
                await beam.edit_text(text)
            except Exception:
                pass
        else:
            beam = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if beam:
        await asyncio.sleep(0.5)
        try:
            await beam.delete()
        except Exception:
            pass


async def referral_success_effect(message: Message):
    frames = [
        "🎆 <b>Referral Linked</b>\n\n<blockquote>🔗 Validating link...</blockquote>",
        "🎆 <b>Referral Linked</b>\n\n<blockquote>💢 Tracking referrer...</blockquote>",
        "🎉 <b>Referral Complete</b>\n\n<blockquote>🌟 Reward unlocks after purchase</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def order_delivery_effect(message: Message):
    frames = [
        "🚀 <b>Processing Order</b>\n\n<blockquote>📦 Preparing coupon...</blockquote>",
        "🚀 <b>Processing Order</b>\n\n<blockquote>📫 Encoding code...</blockquote>",
        "🌟 <b>Order Ready</b>\n\n<blockquote>✅ Your coupon is here!</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def premium_boot_effect(message: Message):
    frames = [
        "🔐 <b>FlashX Initializing</b>\n\n<blockquote>🔍 Loading interface...</blockquote>",
        "🔐 <b>FlashX Initializing</b>\n\n<blockquote>📊 Syncing data...</blockquote>",
        "✨ <b>FlashX Ready</b>\n\n<blockquote>📄 Premium interface active</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def vault_sync_effect(message: Message):
    frames = [
        "💫 <b>Vault Syncing</b>\n\n<blockquote>⚡ Connecting...</blockquote>",
        "💫 <b>Vault Syncing</b>\n\n<blockquote>📦 Loading inventory...</blockquote>",
        "🌟 <b>Vault Ready</b>\n\n<blockquote>📄 Premium coupons available</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def wallet_charge_effect(message: Message):
    frames = [
        "💰 <b>Wallet Loading</b>\n\n<blockquote>⚡ Reading balance...</blockquote>",
        "💰 <b>Wallet Loading</b>\n\n<blockquote>💸 Verifying credits...</blockquote>",
        "💲 <b>Wallet Ready</b>\n\n<blockquote>✅ Credits confirmed</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def referral_orbit_effect(message: Message):
    frames = [
        "🌙 <b>Referral Orbiting</b>\n\n<blockquote>😁 Spinning link...</blockquote>",
        "🌛 <b>Referral Orbiting</b>\n\n<blockquote>🌟 Collecting data...</blockquote>",
        "🌜 <b>Referral Complete</b>\n\n<blockquote>✅ Referral tracked successfully</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def user_ai_effect(message: Message):
    frames = [
        "🤖 <b>Cutie AI</b>\n\n<blockquote>🔍 Analyzing...</blockquote>",
        "🤖 <b>Cutie AI</b>\n\n<blockquote>🌟 Processing...</blockquote>",
        "🤗 <b>Cutie Ready</b>\n\n<blockquote>✅ Response prepared</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def referral_link_effect(message: Message):
    frames = [
        "🔗 <b>Referral Link</b>\n\n<blockquote>🔍 Generating invite...</blockquote>",
        "🔗 <b>Referral Link</b>\n\n<blockquote>📋 Encoding data...</blockquote>",
        "🎁 <b>Referral Saved</b>\n\n<blockquote>✅ Invite unlocks after purchase</blockquote>",
    ]
    frame = None
    for text in frames:
        if frame:
            try:
                await frame.edit_text(text)
            except Exception:
                pass
        else:
            frame = await message.answer(text)
        await asyncio.sleep(0.3)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def reject_if_banned(message: Message):
    if is_configured_admin(message.from_user.id):
        return False
    track_user(message.from_user.id, message.from_user.username)

    if is_user_banned(message.from_user.id):
        await message.answer(
            "🚫 <b>Access blocked.</b>\n\n"
            "<blockquote>Your account is restricted. Contact support if this is a mistake.</blockquote>"
        )
        return True

    if (
        str(message.from_user.id) != str(ADMIN_ID)
        and get_bot_setting("maintenance_mode", "off").lower() == "on"
    ):
        await message.answer(
            "🛠 <b>Maintenance mode</b>\n\n"
            f"<blockquote>{escape(get_bot_setting('maintenance_text', 'Cutie is upgrading the bot. Please try again soon.'))}</blockquote>"
        )
        return True

    return False


@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.clear()
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
    await callback.message.answer(
        "✨ <b>BB Coupon Shop is ready</b>\n\n"
        "<blockquote>Browse live stock, pay securely, and view delivered codes in one place.</blockquote>",
        reply_markup=launch_shop_keyboard(),
    )
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
    await message.answer(
        "🛍️ <b>Buy Coupons</b>\n\n"
        "<blockquote>Open the secure shop to choose a coupon and quantity. "
        "Cashfree opens inside Telegram after one checkout tap—no payment link or recheck button.</blockquote>",
        reply_markup=launch_shop_keyboard(),
    )


@dp.callback_query(F.data.startswith("buy_type_"))
async def buy_coupon_type(callback: CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("Access blocked.", show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        "<b>Secure checkout has moved to the BB Coupon Shop.</b>\n\n"
        "<blockquote>It opens Cashfree inside Telegram and delivers automatically after confirmation.</blockquote>",
        reply_markup=launch_shop_keyboard(),
    )
    await callback.answer()
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

    stock = get_coupon_stock(coupon.coupon_name)
    special_price = get_bulk_buyer_price(callback.from_user.id, coupon.coupon_name)
    unit_price = special_price if special_price is not None else coupon.selling_price

    await state.update_data(
        coupon_id=coupon.id,
        unit_price=unit_price,
    )
    await state.set_state(PurchaseQuantityState.waiting_for_quantity)
    await callback.message.answer(
        "🛒 <b>Select Quantity</b>\n\n"
        f"<blockquote>Coupon: <code>{escape(coupon.coupon_name)}</code>\n"
        f"Available Stock: <b>{stock}</b>\n"
        f"Your Price: <b>Rs {unit_price}</b>"
        f"{' ⭐ special buyer price' if special_price is not None else ''}</blockquote>\n\n"
        "Send how many coupons you want to buy."
    )
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


@dp.message(PurchaseQuantityState.waiting_for_quantity)
async def purchase_quantity(message: Message, state: FSMContext, bot: Bot):
    if await reject_if_banned(message):
        return

    await state.clear()
    await message.answer(
        "<b>Secure checkout has moved to the BB Coupon Shop.</b>\n\n"
        "<blockquote>Choose the coupon and quantity there to pay inside Telegram.</blockquote>",
        reply_markup=launch_shop_keyboard(),
    )
    return

    try:
        quantity = int((message.text or "").strip())
    except ValueError:
        await message.answer("Send a number only, example: <code>3</code>")
        return

    data = await state.get_data()
    coupon = get_coupon_by_id(int(data.get("coupon_id")))

    if quantity <= 0:
        await message.answer("Quantity must be a positive number.")
        return

    if not coupon or coupon.sold:
        await message.answer("😔 <b>This coupon is no longer available. Open Deal Vault again.</b>")
        await state.clear()
        return

    live_stock = get_coupon_stock(coupon.coupon_name)
    if live_stock < quantity:
        await message.answer(
            "😔 <b>Stock changed.</b>\n\n"
            f"<blockquote>Available now: <b>{live_stock}</b>. Send a lower quantity.</blockquote>"
        )
        return

    unit_price = int(data.get("unit_price") or coupon.selling_price)
    total_amount = unit_price * quantity
    order_id = create_order(
        message.from_user.id,
        coupon.coupon_name,
        total_amount,
        use_wallet=True,
        quantity=quantity,
    )

    if not order_id:
        await message.answer(
            "💔 <b>Order creation failed.</b>\n\n"
            "<blockquote>Please try again or contact support.</blockquote>"
        )
        await state.clear()
        return

    set_bot_setting(f"order_quantity:{order_id}", str(quantity))
    set_bot_setting(f"order_unit_price:{order_id}", str(unit_price))

    order = get_order_by_id(order_id)
    payable_amount = order.payable_amount if order else total_amount
    wallet_used = order.wallet_used if order else 0

    if payable_amount == 0:
        delivered, detail = await finalize_paid_order(order_id, bot)
        if not delivered:
            await message.answer(
                "⚠️ <b>Wallet purchase needs admin support.</b>\n\n"
                f"<blockquote>{escape(detail)}</blockquote>"
            )
        else:
            await message.answer("✅ <b>Coupons paid from wallet credits.</b>")
        await state.clear()
        return

    await message.answer(
        "✨ <b>Order Created</b>\n\n"
        f"<blockquote>🆔 Order ID: <code>{order_id}</code>\n"
        f"🎟 Coupon: <code>{escape(coupon.coupon_name)}</code>\n"
        f"Quantity: <b>{quantity}</b>\n"
        f"Unit Price: <b>Rs {unit_price}</b>\n"
        f"💰 Amount: <b>Rs {total_amount}</b>\n"
        f"💎 Wallet Used: <b>Rs {wallet_used}</b>\n"
        f"⏳ Pay Now: <i>Rs {payable_amount}</i></blockquote>",
        reply_markup=payment_keyboard(order_id),
    )
    await state.clear()


@dp.callback_query(F.data.startswith("pay_"))
async def pay_order(callback: CallbackQuery):
    order = get_order_by_id(callback.data.replace("pay_", ""))
    if not order or order.user_id != callback.from_user.id:
        await callback.answer("Order not found.", show_alert=True)
        return
    await callback.message.answer(
        "<b>This older order uses the retired link checkout.</b>\n\n"
        "<blockquote>Open the BB Coupon Shop to create a secure in-app checkout. "
        "Do not pay through a previous link.</blockquote>",
        reply_markup=launch_shop_keyboard(),
    )
    await callback.answer()
    return

    order_id = callback.data.replace("pay_", "")
    await flash_effect(callback, FLASH_PAYMENT_TEXT)
    await energy_collecting_effect(callback)
    await payment_energy_effect(callback)
    order = get_order_by_id(order_id)

    if not order:
        await callback.message.answer("💔 <b>Order not found.</b>")
        await callback.answer()
        return

    if order.user_id != callback.from_user.id:
        await callback.answer("This payment link belongs to another user.", show_alert=True)
        return

    if expire_order_if_needed(order_id) or order.payment_status != "PENDING":
        refunded = refund_order_wallet_if_needed(order_id, "Payment expiry refund")
        await callback.message.answer(
            "<b>Payment window expired.</b>\n\n"
            f"<blockquote>This order was marked failed after {PAYMENT_EXPIRY_MINUTES} minutes. Create a new order to pay.</blockquote>"
            + ("\n\n<b>Wallet credits were returned.</b>" if refunded else "")
        )
        await callback.answer()
        return

    data = await asyncio.to_thread(
        create_cashfree_payment_link,
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
            [InlineKeyboardButton(text="💳 Pay Securely", url=payment_url, style="success")],
            [InlineKeyboardButton(text="🔁 I Paid, Recheck", callback_data=f"recheck_{order_id}", style="primary")],
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

    if order.delivery_status == "PROCESSING" or not claim_order_delivery(order_id):
        return False, "This order is already being delivered."

    if order.coupon_name == "WALLET_TOPUP":
        add_wallet_credit(order.user_id, order.amount, f"Wallet top up for {order.order_id}")
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

    quantity = get_order_quantity(order_id)
    coupon_codes, remaining_stock = deliver_coupons(order.coupon_name, quantity)

    if len(coupon_codes) < quantity:
        refund_order_wallet_if_needed(order_id, "Delivery refund")
        release_order_delivery_claim(order_id)
        return False, "Not enough unsold coupon stock available for this order."

    delivered_codes = "\n".join(coupon_codes)
    coupon_code = delivered_codes
    save_order_coupon_code(order_id, ", ".join(coupon_codes))

    update_order_status(order_id, "SUCCESS")
    update_delivery_status(order_id, "DELIVERED")
    reward_referral_if_needed(order.user_id, 1)

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
    return True, ", ".join(coupon_codes)


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
    
    if order.user_id != callback.from_user.id:
        await callback.answer("This order belongs to another user.", show_alert=True)
        return

    if expire_order_if_needed(order_id):
        refunded = refund_order_wallet_if_needed(order_id, "Payment expiry refund")
        await callback.message.answer(
            "<b>Payment window expired.</b>\n\n"
            "<blockquote>The order is now marked failed. Please create a fresh order.</blockquote>"
            + ("\n\n<b>Wallet credits were returned.</b>" if refunded else "")
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

    if not order or order.user_id != callback.from_user.id:
        await callback.answer("This order belongs to another user.", show_alert=True)
        return

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
        await callback.message.answer("<b>Feedback skipped.</b>")
        await callback.answer()
        return

    await state.update_data(order_id=order_id, rating=rating)
    await state.set_state(FeedbackState.waiting_for_message)
    await callback.message.answer(
        "<b>Send one line feedback</b>\n\n"
        f"<blockquote>Rating saved: <b>{rating}/5</b>. Tell Cutie what was good or what to improve.</blockquote>"
    )
    await callback.answer()


@dp.message(FeedbackState.waiting_for_message)
async def feedback_message(message: Message, state: FSMContext):
    if message.text == BTN_CONTROL_CENTER and str(message.from_user.id) == str(ADMIN_ID):
        await state.clear()
        await message.answer(
            "Developer Panel\n\n<blockquote>Admin mode is active.</blockquote>",
            reply_markup=developer_menu(),
        )
        return

    data = await state.get_data()
    feedback_id = add_feedback(
        message.from_user.id,
        data.get("order_id"),
        int(data.get("rating") or 0),
        (message.text or "").strip(),
    )

    if feedback_id:
        await message.answer(
            "<b>Feedback saved.</b>\n\n"
            "<blockquote>Cutie AI can use this memory to improve future help.</blockquote>"
        )
    else:
        await message.answer("<b>Feedback could not be saved. Please try later.</b>")

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

    for order in orders[:10]:
        text += (
            f"<blockquote>Quantity: <b>{order.quantity or 1}</b> | "
            f"Wallet used: <b>Rs {order.wallet_used or 0}</b>\n"
            f"Coupon codes: <code>{escape(order.coupon_code or 'Not delivered')}</code></blockquote>\n"
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
            [InlineKeyboardButton(text="💳 Top Up Wallet", callback_data="wallet_topup", style="success")],
            [InlineKeyboardButton(text="📜 Wallet History", callback_data="wallet_history", style="primary")],
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
    data = await asyncio.to_thread(
        create_cashfree_payment_link,
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
            [InlineKeyboardButton(text="💳 Pay Wallet Top Up", url=payment_url, style="success")],
            [InlineKeyboardButton(text="🔁 I Paid, Recheck", callback_data=f"recheck_{order_id}", style="primary")],
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
    answer = await asyncio.to_thread(get_ai_answer, message.text or "")
    await message.answer(answer if "<" in answer else escape(answer))
    await state.clear()


async def main():
    if not RUN_BOT_POLLING:
        raise RuntimeError(
            "Polling is disabled. Use launcher.py for webhook deployment, or set "
            "RUN_BOT_POLLING=true for a deliberate local polling session."
        )

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
