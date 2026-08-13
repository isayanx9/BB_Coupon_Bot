import asyncio
import csv
from html import escape
from pathlib import Path
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import ADMIN_ID
from database.crud import (
    add_coupon,
    add_ticket_reply,
    add_wallet_credit,
    audit_admin_action,
    claim_broadcast_message,
    ban_user,
    close_ticket,
    create_flash_sale,
    cancel_flash_sale,
    delete_coupon_group,
    export_backup_rows,
    get_all_bot_settings,
    get_all_user_ids,
    get_analytics_snapshot,
    get_recent_audit_logs,
    get_recent_feedback,
    get_recent_orders,
    get_open_tickets,
    get_ticket_by_id,
    get_order_by_id,
    get_banned_users,
    get_bulk_buyer_prices,
    get_cancelled_orders,
    get_completed_orders,
    get_coupon_summary,
    get_failed_orders,
    get_pending_orders,
    get_total_coupons,
    get_total_orders,
    get_total_revenue,
    get_total_users,
    get_coupon_stock,
    get_active_flash_sales,
    get_active_flash_sale_for_coupon,
    get_delivery_reconciliation,
    coupon_code_exists,
    get_wallet_balance,
    is_user_banned,
    set_bot_setting,
    unban_user,
    update_coupon_price,
    reset_platform_data,
    set_bulk_buyer_price,
)
from services.coupon_service import deliver_coupon
from services.stock_alerts import notify_stock_alerts, should_send_stock_alert
from keyboards.admin import developer_menu
from keyboards.user import admin_main_menu, user_main_menu
from states.order_states import (
    BanState,
    BroadcastState,
    BulkBuyerPriceState,
    CouponUpload,
    DeleteCouponState,
    ExtractCodeState,
    FlashSaleState,
    CancelFlashSaleState,
    PriceState,
    SettingState,
    TicketReplyState,
    UnbanState,
    WalletCreditState,
)
from texts import (
    BTN_ADD_COUPON,
    BTN_ANALYTICS,
    BTN_AUDIT_LOGS,
    BTN_BACKUP,
    BTN_BAN_USER,
    BTN_BROADCAST,
    BTN_BULK_BUYER,
    BTN_CONTROL_CENTER,
    BTN_DELETE_COUPON,
    BTN_EXTRACT_CODE,
    BTN_MAINTENANCE_OFF,
    BTN_MAINTENANCE_ON,
    BTN_EXIT_DEVELOPER,
    BTN_FLASH_SALE,
    BTN_CANCEL_FLASH_SALE,
    BTN_RECONCILE_DELIVERY,
    BTN_INVENTORY,
    BTN_MAIN_MENU,
    BTN_ORDERS,
    BTN_PAYMENTS,
    BTN_REPLY_TICKET,
    BTN_SETTINGS,
    BTN_SET_PRICE,
    BTN_STATISTICS,
    BTN_TICKETS,
    BTN_UNBAN_USER,
    BTN_USERS,
    BTN_WALLET_CREDIT,
    BTN_RESET_ALL,
    COUPON_NAME,
)

router = Router()


async def broadcast_launch_effect(message: Message):
    frames = [
        "📣 <b>Broadcasting</b>\n\n<blockquote>🔴 Starting transmission...</blockquote>",
        "📣 <b>Broadcasting</b>\n\n<blockquote>🟠 Connecting to users...</blockquote>",
        "📣 <b>Broadcasting</b>\n\n<blockquote>🟡 Sending message...</blockquote>",
        "📣 <b>Broadcasting</b>\n\n<blockquote>🟢 Delivered!</blockquote>",
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
        await asyncio.sleep(0.4)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def low_stock_effect(message: Message, count: int):
    frames = [
        f"🚨 <b>Low Stock Alert</b>\n\n<blockquote>⚠️ Scanning inventory...\nCritical items: <b>{count}</b></blockquote>",
        f"🚨 <b>Low Stock Alert</b>\n\n<blockquote>🔴 LOW STOCK DETECTED\nCritical items: <b>{count}</b></blockquote>",
        f"🚨 <b>Low Stock Alert</b>\n\n<blockquote>✅ Alert sent to admin\nCritical items: <b>{count}</b></blockquote>",
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
        await asyncio.sleep(0.4)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def admin_boot_effect(message: Message):
    frames = [
        "🔐 <b>Control Center</b>\n\n<blockquote>🟢 Initializing admin panel...</blockquote>",
        "🔐 <b>Control Center</b>\n\n<blockquote>🟢 Loading dashboard...</blockquote>",
        "🔐 <b>Control Center</b>\n\n<blockquote>✅ Admin mode activated</blockquote>",
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
        await asyncio.sleep(0.4)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def admin_sync_effect(message: Message, title="Admin sync"):
    frames = [
        f"⚡ <b>{title}</b>\n\n<blockquote>⏳ Processing...</blockquote>",
        f"⚡ <b>{title}</b>\n\n<blockquote>⏳ Syncing data...</blockquote>",
        f"✅ <b>{title}</b>\n\n<blockquote>✅ Complete!</blockquote>",
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
        await asyncio.sleep(0.4)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


async def inventory_scan_effect(message: Message):
    frames = [
        "📦 <b>Inventory Scan</b>\n\n<blockquote>🔍 Scanning stock...</blockquote>",
        "📦 <b>Inventory Scan</b>\n\n<blockquote>📊 Analyzing data...</blockquote>",
        "📦 <b>Inventory Scan</b>\n\n<blockquote>✅ Inventory loaded</blockquote>",
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
        await asyncio.sleep(0.4)
    
    if frame:
        await asyncio.sleep(0.5)
        try:
            await frame.delete()
        except Exception:
            pass


def is_admin(message: Message):
    return str(message.from_user.id) == str(ADMIN_ID)


async def admin_only(message: Message):
    if is_admin(message):
        return True

    await message.answer("🚫 <b>Admin only.</b>")
    return False


@router.message(F.text == "/developer")
async def developer_panel(message: Message):
    if not await admin_only(message):
        return

    await admin_boot_effect(message)
    await message.answer(
        "🛠 <b>FLASH-X Control Center</b>\n\n"
        "<blockquote>Cutie can manage coupons, broadcasts, users, bans, settings, payments, and orders.</blockquote>",
        reply_markup=developer_menu(),
    )


@router.message(F.text == BTN_CONTROL_CENTER)
async def developer_button(message: Message):
    if not await admin_only(message):
        return

    await message.answer(
        "🛠 <b>Developer Panel</b>\n\n"
        "<blockquote>Hidden admin mode is active. Normal users cannot access this panel.</blockquote>",
        reply_markup=developer_menu(),
    )


@router.message(F.text == BTN_MAIN_MENU)
async def main_menu_button(message: Message):
    if not is_admin(message):
        return

    await message.answer("🏠 <b>Main Menu</b>", reply_markup=admin_main_menu())


@router.message(F.text == BTN_EXIT_DEVELOPER)
async def exit_developer(message: Message):
    if not is_admin(message):
        return

    await message.answer("✨ <b>Control center closed.</b>", reply_markup=user_main_menu())


@router.message(F.text == BTN_ADD_COUPON)
async def add_coupon_button(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await message.answer(
        "➕ <b>Inventory Import</b>\n\n"
        "<blockquote>Send one or many coupon rows. Cutie will parse them in bulk.</blockquote>\n\n"
        "📌 <b>Format</b>\n"
        "<code>Coupon Name|Coupon Code|Discount|Minimum Order|Price|Description</code>\n\n"
        "✨ <b>Example</b>\n"
        f"<code>{COUPON_NAME}|BB100ICE001|100|100|14|Use on eligible orders</code>"
    )
    await state.set_state(CouponUpload.waiting_for_bulk_coupons)


@router.message(CouponUpload.waiting_for_bulk_coupons, F.text)
async def process_bulk_coupon(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message):
        return

    added = 0
    failed = 0
    added_coupon_names = set()
    errors = []
    submitted_codes = set()

    for line_number, line in enumerate(message.text.splitlines(), start=1):
        if not line.strip():
            continue

        try:
            parts = [part.strip() for part in line.split("|")]
            if len(parts) not in {5, 6}:
                raise ValueError("use 5 fields, or add a sixth Description field")
            name, code, discount, minimum, price = parts[:5]
            description = parts[5] if len(parts) == 6 else ""
            if not name or not code:
                raise ValueError("coupon name and code are required")
            if code in submitted_codes:
                raise ValueError("duplicate coupon code in this upload")
            if coupon_code_exists(code):
                raise ValueError("coupon code already exists; every coupon needs a unique code")

            discount = int(discount.strip())
            minimum = int(minimum.strip())
            price = int(price.strip())
            if discount < 0 or minimum < 0 or price < 0:
                raise ValueError("discount, minimum order, and price must be zero or greater")
            success = add_coupon(
                name,
                code,
                discount,
                minimum,
                price,
            )

            if success:
                added += 1
                added_coupon_names.add(name)
                submitted_codes.add(code)
                if description:
                    set_bot_setting(f"coupon_description:{name}", description)
            else:
                failed += 1
                errors.append(f"Line {line_number}: coupon code already exists or could not be saved")
        except (TypeError, ValueError) as error:
            failed += 1
            errors.append(f"Line {line_number}: {escape(str(error))}")

    if added == 0:
        details = "\n".join(errors[:3]) or "No coupon rows were found."
        await message.answer(
            "<b>No coupons were added.</b>\n\n"
            f"<blockquote>{details}</blockquote>\n\n"
            "Try again using:\n"
            "<code>Coupon Name|Coupon Code|Discount|Minimum Order|Price|Description</code>"
        )
        return

    await message.answer(
        "✨ <b>Upload Complete</b>\n\n"
        f"<blockquote>✅ Added: <b>{added}</b>\n"
        f"⚠️ Failed: <b>{failed}</b></blockquote>"
    )
    if errors:
        await message.answer(
            "<b>Rows that were not added</b>\n"
            f"<blockquote>{chr(10).join(errors[:3])}</blockquote>"
        )
    audit_admin_action(message.from_user.id, "bulk_coupon_upload", f"added={added}, failed={failed}")

    if added:
        sent = 0
        broadcast_sent = 0
        for coupon_name in sorted(added_coupon_names):
            stock_count = get_coupon_stock(coupon_name)
            notified = await notify_stock_alerts(
                bot,
                coupon_name,
                stock_count,
                reason="restock",
            )
            sent += notified
            announcement = (
                "📦 <b>New coupon stock is live</b>\n\n"
                f"<blockquote>Coupon: <code>{escape(coupon_name)}</code>\n"
                f"Available: <b>{stock_count}</b></blockquote>\n\n"
                "Open BB Coupon Shop to view the deal."
            )
            for user_id in get_all_user_ids():
                if is_user_banned(user_id):
                    continue
                try:
                    await bot.send_message(user_id, announcement)
                    broadcast_sent += 1
                except Exception:
                    pass

        await message.answer(
            f"🔔 Stock-watch alerts sent: <b>{sent}</b>\n"
            f"📣 New-stock broadcast sent: <b>{broadcast_sent}</b>"
        )

    await state.clear()


@router.message(CouponUpload.waiting_for_bulk_coupons)
async def process_bulk_coupon_non_text(message: Message):
    if not is_admin(message):
        return

    await message.answer(
        "Send coupon rows as a text message:\n"
        "<code>Coupon Name|Coupon Code|Discount|Minimum Order|Price|Description</code>"
    )


@router.message(F.text == BTN_INVENTORY)
async def inventory(message: Message):
    if not is_admin(message):
        return

    await inventory_scan_effect(message)
    summary = get_coupon_summary()
    low_stock = [item for item in summary if int(item["available"]) <= 5]
    if low_stock:
        await low_stock_effect(message, len(low_stock))

    lines = []

    for item in summary:
        lines.append(
            f"🎟 <code>{item['name']}</code>\n"
            f"Available <b>{item['available']}</b> • Sold <b>{item['sold']}</b> • Rs <b>{item['price']}</b>"
        )

    details = "\n\n".join(lines) if lines else "No coupons uploaded yet."

    await message.answer(
        "📦 <b>Inventory</b>\n\n"
        f"<blockquote>🎟 Total Coupons: <b>{get_total_coupons()}</b>\n\n{details}</blockquote>"
    )


@router.message(F.text == BTN_STATISTICS)
async def statistics(message: Message):
    if not is_admin(message):
        return

    await message.answer(
        "📊 <b>Statistics</b>\n\n"
        f"<blockquote>🎟 Total Coupons: <b>{get_total_coupons()}</b>\n"
        f"📋 Total Orders: <b>{get_total_orders()}</b>\n"
        f"👥 Known Users: <b>{get_total_users()}</b>\n"
        f"💰 Revenue: <b>Rs {get_total_revenue()}</b></blockquote>"
    )


@router.message(F.text == BTN_ANALYTICS)
async def analytics(message: Message):
    if not is_admin(message):
        return

    await admin_sync_effect(message, "Analytics sync")
    data = get_analytics_snapshot()
    await message.answer(
        "📈 <b>Analytics</b>\n\n"
        f"<blockquote>Revenue: <b>Rs {data['revenue']}</b>\n"
        f"Orders: <b>{data['total_orders']}</b>\n"
        f"Success: <b>{data['success_orders']}</b>\n"
        f"Pending: <b>{data['pending_orders']}</b>\n"
        f"Conversion: <b>{data['conversion']}%</b>\n"
        f"Users: <b>{data['total_users']}</b>\n"
        f"Available Coupons: <b>{data['available_coupons']}</b></blockquote>"
    )


@router.message(F.text == BTN_USERS)
async def users(message: Message):
    if not is_admin(message):
        return

    banned = get_banned_users()
    banned_text = "\n".join(
        f"🚫 <code>{user.telegram_id}</code> • {user.reason}"
        for user in banned
    )

    if not banned_text:
        banned_text = "No banned users."

    await message.answer(
        "👥 <b>User Management</b>\n\n"
        f"<blockquote>Known Users: <b>{get_total_users()}</b>\n"
        f"Banned Listed: <b>{len(banned)}</b></blockquote>\n\n"
        f"<blockquote>{banned_text}</blockquote>\n\n"
        "<i>Use Ban User or Unban User from Control Center.</i>"
    )


@router.message(F.text == BTN_PAYMENTS)
async def payments(message: Message):
    if not is_admin(message):
        return

    await message.answer(
        "💳 <b>Payment Dashboard</b>\n\n"
        f"<blockquote>✅ Successful: <b>{get_completed_orders()}</b>\n"
        f"⏳ Pending: <b>{get_pending_orders()}</b>\n"
        f"❌ Failed: <b>{get_failed_orders()}</b>\n"
        f"🚫 Cancelled: <b>{get_cancelled_orders()}</b>\n\n"
        f"💰 Revenue: <b>Rs {get_total_revenue()}</b></blockquote>"
    )


@router.message(F.text == BTN_ORDERS)
async def orders(message: Message):
    if not is_admin(message):
        return

    await message.answer(
        "📋 <b>Orders Dashboard</b>\n\n"
        f"<blockquote>📋 Total Orders: <b>{get_total_orders()}</b>\n"
        f"⏳ Pending: <b>{get_pending_orders()}</b>\n"
        f"✅ Completed: <b>{get_completed_orders()}</b>\n"
        f"❌ Failed: <b>{get_failed_orders()}</b>\n"
        f"🚫 Cancelled: <b>{get_cancelled_orders()}</b></blockquote>"
    )


    recent_orders = get_recent_orders(limit=20)
    lines = []
    for order, username in recent_orders:
        handle = f"@{escape(username)}" if username else "No username"
        lines.append(
            f"<b>{handle}</b> | <code>{order.user_id}</code>\n"
            f"<code>{order.order_id}</code> | {escape(order.coupon_name)} x <b>{order.quantity or 1}</b>\n"
            f"Total: <b>Rs {order.amount}</b> | Wallet: <b>Rs {order.wallet_used or 0}</b>\n"
            f"Payment: <i>{escape(order.payment_status)}</i> | Delivery: <i>{escape(order.delivery_status)}</i>"
        )
    await message.answer(
        "<b>Recent Order History</b>\n\n"
        f"<blockquote>{chr(10).join(lines) if lines else 'No orders yet.'}</blockquote>"
    )


@router.message(F.text == BTN_MAINTENANCE_ON)
async def maintenance_on(message: Message):
    if not await admin_only(message):
        return

    set_bot_setting("maintenance_mode", "on")
    audit_admin_action(message.from_user.id, "maintenance_mode", "on")
    await message.answer(
        "<b>Maintenance mode is ON.</b>\n\n"
        "<blockquote>Users will see the maintenance message until you turn it off.</blockquote>"
    )


@router.message(F.text == BTN_MAINTENANCE_OFF)
async def maintenance_off(message: Message):
    if not await admin_only(message):
        return

    set_bot_setting("maintenance_mode", "off")
    audit_admin_action(message.from_user.id, "maintenance_mode", "off")
    await message.answer(
        "<b>Maintenance mode is OFF.</b>\n\n"
        "<blockquote>The bot is available to users again.</blockquote>"
    )


@router.message(F.text == BTN_EXTRACT_CODE)
async def extract_coupon_code_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await state.set_state(ExtractCodeState.waiting_for_order_id)
    await message.answer(
        "<b>Extract Coupon Code</b>\n\n"
        "<blockquote>Send the Order ID from the order history. Only delivered orders have codes to extract.</blockquote>"
    )


@router.message(ExtractCodeState.waiting_for_order_id)
async def extract_coupon_code(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    order_id = (message.text or "").strip().upper()
    order = get_order_by_id(order_id)
    if not order:
        await message.answer("<b>Order not found.</b> Send a valid Order ID.")
        return

    if not order.coupon_code:
        await message.answer(
            "<b>No coupon code is available for this order.</b>\n\n"
            f"<blockquote>Payment: <i>{escape(order.payment_status)}</i>\n"
            f"Delivery: <i>{escape(order.delivery_status)}</i></blockquote>"
        )
        await state.clear()
        return

    await message.answer(
        "<b>Extracted Coupon Code</b>\n\n"
        f"<blockquote>Order: <code>{order.order_id}</code>\n"
        f"Coupon: <code>{escape(order.coupon_name)}</code>\n"
        f"Quantity: <b>{order.quantity or 1}</b>\n"
        f"Customer ID: <code>{order.user_id}</code>\n\n"
        f"Codes:\n<code>{escape(order.coupon_code)}</code></blockquote>"
    )
    audit_admin_action(message.from_user.id, "extract_coupon_code", order.order_id)
    await state.clear()


@router.message(F.text == BTN_BROADCAST)
async def broadcast(message: Message, state: FSMContext):
    if not await admin_only(message):
        return
    await message.answer("Send the broadcast text. Cutie will show a preview and require you to type CONFIRM before it sends.")
    await state.set_state(BroadcastState.waiting_for_message)


@router.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message):
        return
    data = await state.get_data()
    if not data.get("broadcast_text"):
        if not message.text:
            await message.answer("Text broadcasts only for the confirmation flow. Send your message as text.")
            return
        await state.update_data(broadcast_text=message.text)
        await message.answer(f"<b>Preview</b>\n\n<blockquote>{escape(message.text)[:900]}</blockquote>\n\nType <code>CONFIRM</code> to send, or <code>CANCEL</code> to discard.")
        return
    command = (message.text or "").strip().upper()
    if command == "CANCEL":
        await state.clear()
        await message.answer("Broadcast cancelled.")
        return
    if command != "CONFIRM":
        await message.answer("Type CONFIRM to send or CANCEL to discard.")
        return
    broadcast_text = data["broadcast_text"]
    if not claim_broadcast_message(message.chat.id, message.message_id):
        return
    await broadcast_launch_effect(message)
    sent = failed = 0
    for user_id in get_all_user_ids():
        if is_user_banned(user_id):
            continue
        try:
            await bot.send_message(user_id, "📣 <b>Broadcast from BB Coupon Bot</b>\n\n" f"<blockquote>{escape(broadcast_text)}</blockquote>")
            sent += 1
        except Exception:
            failed += 1
    await message.answer("✨ <b>Broadcast complete</b>\n\n" f"<blockquote>Sent: <b>{sent}</b>\nFailed: <b>{failed}</b></blockquote>")
    audit_admin_action(message.from_user.id, "broadcast", f"type=text, sent={sent}, failed={failed}")
    await state.clear()


@router.message(F.text == BTN_SETTINGS)
async def settings(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await admin_sync_effect(message, "Settings sync")
    settings_list = get_all_bot_settings()
    settings_text = "\n".join(
        f"<code>{escape(setting.key)}</code> = <b>{escape(setting.value)}</b>"
        for setting in settings_list
    )

    if not settings_text:
        settings_text = "No custom settings yet."

    await message.answer(
        "⚙️ <b>Settings</b>\n\n"
        f"<blockquote>{settings_text}</blockquote>\n\n"
        "<b>Useful keys</b>\n"
        "<code>maintenance_mode</code> = <code>on</code> or <code>off</code>\n"
        "<code>maintenance_text</code> = message during maintenance\n\n"
        "<i>Send the setting key to edit.</i>"
    )
    await state.set_state(SettingState.waiting_for_key)


@router.message(SettingState.waiting_for_key)
async def settings_key(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    await state.update_data(key=message.text.strip())
    await message.answer("✍️ <b>Now send the setting value.</b>")
    await state.set_state(SettingState.waiting_for_value)


@router.message(SettingState.waiting_for_value)
async def settings_value(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    data = await state.get_data()
    key = data["key"]
    value = message.text.strip()
    set_bot_setting(key, value)

    await message.answer(
        "✅ <b>Setting saved</b>\n\n"
        f"<blockquote><code>{escape(key)}</code> = <b>{escape(value)}</b></blockquote>"
    )
    audit_admin_action(message.from_user.id, "setting_update", f"{key}={value}")
    await state.clear()


@router.message(F.text == BTN_BAN_USER)
async def ban_user_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await message.answer("🚫 <b>Send Telegram user ID to ban.</b>")
    await state.set_state(BanState.waiting_for_user_id)


@router.message(BanState.waiting_for_user_id)
async def ban_user_id(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Send a numeric Telegram user ID.")
        return

    await state.update_data(user_id=user_id)
    await message.answer("📝 <b>Send ban reason.</b>")
    await state.set_state(BanState.waiting_for_reason)


@router.message(BanState.waiting_for_reason)
async def ban_user_reason(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    data = await state.get_data()
    user_id = data["user_id"]
    reason = message.text.strip() or "Admin ban"
    ban_user(user_id, reason)

    await message.answer(
        "🚫 <b>User banned</b>\n\n"
        f"<blockquote>User: <code>{user_id}</code>\nReason: <i>{escape(reason)}</i></blockquote>"
    )
    audit_admin_action(message.from_user.id, "ban_user", f"{user_id}: {reason}")
    await state.clear()


@router.message(F.text == BTN_UNBAN_USER)
async def unban_user_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await message.answer("✅ <b>Send Telegram user ID to unban.</b>")
    await state.set_state(UnbanState.waiting_for_user_id)


@router.message(UnbanState.waiting_for_user_id)
async def unban_user_id(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Send a numeric Telegram user ID.")
        return

    removed = unban_user(user_id)
    status = "removed from ban list" if removed else "was not banned"

    await message.answer(
        "✅ <b>Unban complete</b>\n\n"
        f"<blockquote>User <code>{user_id}</code> {status}.</blockquote>"
    )
    await state.clear()


@router.message(F.text == BTN_SET_PRICE)
async def set_price_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await message.answer("💰 <b>Send exact coupon name to change price.</b>")
    await state.set_state(PriceState.waiting_for_coupon_name)


@router.message(PriceState.waiting_for_coupon_name)
async def set_price_name(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    await state.update_data(coupon_name=message.text.strip())
    await message.answer("💰 <b>Send new selling price in Rs.</b>")
    await state.set_state(PriceState.waiting_for_price)


@router.message(PriceState.waiting_for_price)
async def set_price_value(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("Send a number only, example: <code>14</code>")
        return

    data = await state.get_data()
    coupon_name = data["coupon_name"]
    updated = update_coupon_price(coupon_name, price)

    await message.answer(
        "✅ <b>Price update complete</b>\n\n"
        f"<blockquote>Coupon: <code>{escape(coupon_name)}</code>\n"
        f"New Price: <b>Rs {price}</b>\n"
        f"Rows Updated: <b>{updated}</b></blockquote>"
    )
    audit_admin_action(message.from_user.id, "set_price", f"{coupon_name}: {price}")
    await state.clear()


@router.message(F.text == BTN_BULK_BUYER)
async def bulk_buyer_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    prices = get_bulk_buyer_prices(limit=10)
    lines = [
        f"User <code>{row.user_id}</code> • <code>{escape(row.coupon_name)}</code> • Rs <b>{row.price}</b>"
        for row in prices
    ]
    summary = (
        "⭐ <b>Bulk Buyer Special Price</b>\n\n"
        f"<blockquote>{chr(10).join(lines) if lines else 'No special buyers yet.'}</blockquote>\n\n"
        "Send Telegram user ID to add/update a special price."
    )

    await message.answer(summary)
    await state.set_state(BulkBuyerPriceState.waiting_for_user_id)


@router.message(BulkBuyerPriceState.waiting_for_user_id)
async def bulk_buyer_user_id(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Send a numeric Telegram user ID.")
        return

    await state.update_data(user_id=user_id)
    await message.answer("Send exact coupon name for this special price.")
    await state.set_state(BulkBuyerPriceState.waiting_for_coupon_name)


@router.message(BulkBuyerPriceState.waiting_for_coupon_name)
async def bulk_buyer_coupon_name(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    await state.update_data(coupon_name=message.text.strip())
    await message.answer("Send special price per coupon in Rs.")
    await state.set_state(BulkBuyerPriceState.waiting_for_price)


@router.message(BulkBuyerPriceState.waiting_for_price)
async def bulk_buyer_price(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("Send a number only, example: <code>10</code>")
        return

    if price < 0:
        await message.answer("Price cannot be negative.")
        return

    data = await state.get_data()
    ok = set_bulk_buyer_price(data["user_id"], data["coupon_name"], price)

    if ok:
        await message.answer(
            "✅ <b>Bulk buyer price saved.</b>\n\n"
            f"<blockquote>User: <code>{data['user_id']}</code>\n"
            f"Coupon: <code>{escape(data['coupon_name'])}</code>\n"
            f"Special Price: <b>Rs {price}</b></blockquote>"
        )
        audit_admin_action(message.from_user.id, "bulk_buyer_price", str(data))
    else:
        await message.answer("⚠️ <b>Could not save special price.</b>")

    await state.clear()


@router.message(F.text == BTN_DELETE_COUPON)
async def delete_coupon_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await message.answer(
        "🗑 <b>Delete Unsold Coupon Stock</b>\n\n"
        "<blockquote>Send exact coupon name. Sold coupons stay preserved for order history.</blockquote>"
    )
    await state.set_state(DeleteCouponState.waiting_for_coupon_name)


@router.message(DeleteCouponState.waiting_for_coupon_name)
async def delete_coupon_name(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    coupon_name = message.text.strip()
    deleted = delete_coupon_group(coupon_name, only_unsold=True)

    await message.answer(
        "🗑 <b>Delete complete</b>\n\n"
        f"<blockquote>Coupon: <code>{escape(coupon_name)}</code>\n"
        f"Unsold rows deleted: <b>{deleted}</b></blockquote>"
    )
    audit_admin_action(message.from_user.id, "delete_coupon", f"{coupon_name}: {deleted}")
    await state.clear()


@router.message(F.text == BTN_TICKETS)
async def tickets(message: Message):
    if not is_admin(message):
        return

    await admin_sync_effect(message, "Ticket board sync")
    tickets_list = get_open_tickets()
    lines = []

    for ticket in tickets_list:
        preview = (ticket.messages or "").replace("USER:", "").strip()
        if len(preview) > 180:
            preview = preview[:180] + "..."
        lines.append(
            f"🎫 <code>{ticket.id}</code> • User <code>{ticket.user_id}</code>\n"
            f"<b>{escape(ticket.subject)}</b>\n"
            f"<i>{escape(preview or 'No message')}</i>"
        )

    await message.answer(
        "🎫 <b>Open Tickets</b>\n\n"
        f"<blockquote>{chr(10).join(lines) if lines else 'No open tickets.'}</blockquote>\n\n"
        "<i>Use Reply Ticket to answer and close a ticket.</i>"
    )


@router.message(F.text == BTN_REPLY_TICKET)
async def ticket_reply_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await message.answer(
        "💬 <b>Reply Ticket</b>\n\n"
        "<blockquote>Send the ticket ID from the Open Tickets list.</blockquote>"
    )
    await state.set_state(TicketReplyState.waiting_for_ticket_id)


@router.message(TicketReplyState.waiting_for_ticket_id)
async def ticket_reply_id(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        ticket_id = int(message.text.strip())
    except ValueError:
        await message.answer("Send a numeric ticket ID.")
        return

    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        await message.answer("⚠️ <b>Ticket not found.</b>\n\nSend a valid open ticket ID.")
        return

    await state.update_data(ticket_id=ticket_id)
    await message.answer(
        "✍️ <b>Send admin reply</b>\n\n"
        f"<blockquote>Ticket: <code>{ticket.id}</code>\n"
        f"User: <code>{ticket.user_id}</code>\n"
        f"Subject: <b>{escape(ticket.subject)}</b>\n\n"
        f"{escape((ticket.messages or '')[-900:])}</blockquote>"
    )
    await state.set_state(TicketReplyState.waiting_for_reply)


@router.message(TicketReplyState.waiting_for_reply)
async def ticket_reply_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message):
        return

    data = await state.get_data()
    ticket_id = data["ticket_id"]
    reply_text = (message.text or "").strip()
    if not reply_text:
        await message.answer("Please send a text reply for the user.")
        return

    ok = add_ticket_reply(ticket_id, "admin", reply_text)

    if ok:
        ticket = get_ticket_by_id(ticket_id)
        close_ticket(ticket_id)
        if ticket:
            try:
                await bot.send_message(
                    ticket.user_id,
                    "💬 <b>Admin replied to your ticket</b>\n\n"
                    f"<blockquote>Ticket ID: <code>{ticket_id}</code>\n"
                    f"{escape(reply_text)}</blockquote>\n\n"
                    "<i>This ticket is now closed. Raise a new ticket if you still need help.</i>",
                )
            except Exception:
                pass
        await message.answer(
            "✅ <b>Ticket replied and closed.</b>\n\n"
            f"<blockquote>Ticket ID: <code>{ticket_id}</code></blockquote>"
        )
        audit_admin_action(message.from_user.id, "ticket_reply", str(ticket_id))
    else:
        await message.answer("⚠️ <b>Ticket not found.</b>")

    await state.clear()


@router.message(F.text == BTN_WALLET_CREDIT)
async def wallet_credit_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await message.answer("💎 <b>Send user ID for wallet credit.</b>")
    await state.set_state(WalletCreditState.waiting_for_user_id)


@router.message(WalletCreditState.waiting_for_user_id)
async def wallet_credit_user(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Send a numeric user ID.")
        return

    await state.update_data(user_id=user_id)
    await message.answer("💰 <b>Send credit amount in Rs.</b>")
    await state.set_state(WalletCreditState.waiting_for_amount)


@router.message(WalletCreditState.waiting_for_amount)
async def wallet_credit_amount(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("Send a number only.")
        return

    await state.update_data(amount=amount)
    await message.answer("📝 <b>Send reason.</b>")
    await state.set_state(WalletCreditState.waiting_for_reason)


@router.message(WalletCreditState.waiting_for_reason)
async def wallet_credit_reason(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    data = await state.get_data()
    add_wallet_credit(data["user_id"], data["amount"], message.text or "Admin credit")
    await message.answer(
        "✅ <b>Wallet credited.</b>\n\n"
        f"<blockquote>User: <code>{data['user_id']}</code>\nAmount: <b>Rs {data['amount']}</b></blockquote>"
    )
    audit_admin_action(message.from_user.id, "wallet_credit", str(data))
    await state.clear()


@router.message(F.text == BTN_FLASH_SALE)
async def flash_sale_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    available = [item for item in get_coupon_summary(limit=1000) if item["available"] > 0]
    if not available:
        await message.answer("No coupon stock is available. Add coupons before creating a flash sale.")
        return
    names = "\n".join(
        f"• <code>{escape(item['name'])}</code> — {item['available']} available — Rs {item['price']}"
        for item in available[:30]
    )
    await message.answer(
        "⚡ <b>Select an available coupon for the flash sale.</b>\n\n"
        f"<blockquote>{names}</blockquote>\n\nSend the exact coupon name."
    )
    await state.set_state(FlashSaleState.waiting_for_coupon_name)


@router.message(FlashSaleState.waiting_for_coupon_name)
async def flash_sale_coupon(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    await state.update_data(coupon_name=message.text.strip())
    await message.answer("🏷 <b>Send flash sale title.</b>")
    await state.set_state(FlashSaleState.waiting_for_title)


@router.message(FlashSaleState.waiting_for_title)
async def flash_sale_title(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    await state.update_data(title=message.text.strip())
    await message.answer("Send the sale price in rupees. This updates the price for this coupon name.")
    await state.set_state(FlashSaleState.waiting_for_sale_price)


@router.message(FlashSaleState.waiting_for_sale_price)
async def flash_sale_price(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    try:
        sale_price = int((message.text or "").strip())
        if sale_price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Send a valid non-negative rupee amount.")
        return
    await state.update_data(sale_price=sale_price)
    await message.answer("Send duration in minutes, for example 60. The sale disappears automatically at the end time.")
    await state.set_state(FlashSaleState.waiting_for_duration_minutes)


@router.message(FlashSaleState.waiting_for_duration_minutes)
async def flash_sale_duration(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message):
        return
    try:
        minutes = int((message.text or "").strip())
        if not 1 <= minutes <= 10080:
            raise ValueError
    except ValueError:
        await message.answer("Send duration from 1 to 10080 minutes.")
        return
    data = await state.get_data()
    existing_sale = get_active_flash_sale_for_coupon(data["coupon_name"])
    if existing_sale:
        await message.answer(
            f"An active sale already exists for this coupon (sale #{existing_sale.id}). Cancel it first to protect the original price."
        )
        await state.clear()
        return
    if get_coupon_stock(data["coupon_name"]) < 1:
        await message.answer("No available stock exists for that coupon name. Add stock first, then create the sale.")
        await state.clear()
        return
    summary = next((item for item in get_coupon_summary(limit=1000) if item["name"] == data["coupon_name"]), None)
    if not summary or not update_coupon_price(data["coupon_name"], data["sale_price"]):
        await message.answer("Coupon name was not found. No sale was created.")
        await state.clear()
        return
    expires_at = datetime.utcnow() + timedelta(minutes=minutes)
    sale_id = create_flash_sale(
        data["coupon_name"],
        data["title"],
        f"Rs {data['sale_price']} · ends in {minutes} minutes",
        expires_at=expires_at,
    )
    if not sale_id:
        update_coupon_price(data["coupon_name"], summary["price"])
        await message.answer("The sale could not be saved. The original price has been restored.")
        await state.clear()
        return
    set_bot_setting(f"flash_sale_original_price:{sale_id}", str(summary["price"]))
    broadcast_text = (
        f"⚡ <b>{escape(data['title'])}</b>\n\n"
        f"<blockquote>Coupon: <code>{escape(data['coupon_name'])}</code>\n"
        f"Sale price: <b>Rs {data['sale_price']}</b>\n"
        f"Ends: <b>{expires_at.strftime('%d %b %Y, %I:%M %p UTC')}</b></blockquote>\n\n"
        "Open BB Coupon Shop to buy while stock lasts."
    )
    sent = 0
    for user_id in get_all_user_ids():
        if is_user_banned(user_id):
            continue
        try:
            await bot.send_message(user_id, broadcast_text)
            sent += 1
        except Exception:
            pass
    await message.answer(
        "Flash sale created.\n\n"
        f"<blockquote>Sale ID: <code>{sale_id}</code>\nPrice: <b>Rs {data['sale_price']}</b>\n"
        f"Original price: <b>Rs {summary['price']}</b>\n"
        f"Ends: <b>{expires_at.strftime('%d %b %Y, %I:%M %p UTC')}</b>\nBroadcast sent: <b>{sent}</b></blockquote>"
    )
    audit_admin_action(message.from_user.id, "flash_sale", f"{data}; minutes={minutes}; sent={sent}")
    await state.clear()


@router.message(F.text == BTN_CANCEL_FLASH_SALE)
async def cancel_flash_sale_start(message: Message, state: FSMContext):
    if not await admin_only(message):
        return
    sales = get_active_flash_sales(limit=20)
    if not sales:
        await message.answer("No active flash sales.")
        return
    listing = "\n".join(f"#{sale.id} — {escape(sale.coupon_name)} — {escape(sale.title)}" for sale in sales)
    await message.answer(f"<b>Active flash sales</b>\n\n<blockquote>{listing}</blockquote>\n\nSend the Sale ID to cancel and restore its normal price.")
    await state.set_state(CancelFlashSaleState.waiting_for_sale_id)


@router.message(CancelFlashSaleState.waiting_for_sale_id)
async def cancel_flash_sale_confirm(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    try:
        sale_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Send a numeric Sale ID.")
        return
    sale = cancel_flash_sale(sale_id)
    if not sale:
        await message.answer("That sale is not active or could not be cancelled.")
        return
    audit_admin_action(message.from_user.id, "cancel_flash_sale", str(sale_id))
    await message.answer(f"Sale #{sale_id} cancelled. Normal price for <code>{escape(sale.coupon_name)}</code> has been restored.")
    await state.clear()


@router.message(F.text == BTN_RECONCILE_DELIVERY)
async def delivery_recovery(message: Message):
    if not await admin_only(message):
        return
    orders = get_delivery_reconciliation(limit=30)
    if not orders:
        await message.answer("✅ <b>Delivery recovery</b>\n\nNo Cashfree-successful orders are waiting for coupon delivery.")
        return
    lines = "\n".join(
        f"<code>{order.order_id}</code> — user <code>{order.user_id}</code> — {escape(order.coupon_name)}"
        for order in orders
    )
    await message.answer(
        "⚠️ <b>Cashfree-successful orders awaiting delivery</b>\n\n"
        f"<blockquote>{lines}</blockquote>\n\nUse <code>/retry_delivery ORDER_ID</code> for a single safe delivery retry."
    )


@router.message(F.text == BTN_BACKUP)
async def backup(message: Message):
    if not is_admin(message):
        return

    rows = export_backup_rows()
    backup_dir = Path("database/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    coupons_path = backup_dir / "coupons_backup.csv"
    orders_path = backup_dir / "orders_backup.csv"

    with coupons_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "name", "code", "discount", "minimum", "price", "sold"])
        writer.writerows(rows["coupons"])

    with orders_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["order_id", "user_id", "coupon", "amount", "payment", "delivery", "created"])
        writer.writerows(rows["orders"])

    await message.answer(
        "📤 <b>Backup created.</b>\n\n"
        f"<blockquote><code>{coupons_path}</code>\n<code>{orders_path}</code></blockquote>"
    )
    audit_admin_action(message.from_user.id, "backup", "csv")


@router.message(F.text == BTN_AUDIT_LOGS)
async def audit_logs(message: Message):
    if not is_admin(message):
        return

    logs = get_recent_audit_logs()
    lines = [
        f"🧾 <code>{log.admin_id}</code> • <b>{escape(log.action)}</b>\n{escape(log.details or '')}"
        for log in logs
    ]
    await message.answer(
        "🧾 <b>Audit Logs</b>\n\n"
        f"<blockquote>{chr(10).join(lines) if lines else 'No audit logs yet.'}</blockquote>"
    )


@router.message(F.text == "/feedbacks")
async def feedbacks_report(message: Message):
    if not is_admin(message):
        return

    feedbacks = get_recent_feedback(limit=20)
    lines = [
        f"User <code>{item.user_id}</code> • Order <code>{item.order_id or 'N/A'}</code> • {item.rating}/5\n"
        f"{escape(item.message or 'No written feedback')}"
        for item in feedbacks
    ]
    await message.answer(
        "💬 <b>Purchase Feedback</b>\n\n"
        f"<blockquote>{chr(10).join(lines) if lines else 'No feedback saved yet.'}</blockquote>"
    )


@router.message(F.text == BTN_RESET_ALL)
async def reset_all_confirm(message: Message, state: FSMContext):
    if not is_admin(message):
        return
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Yes, Reset Everything", callback_data="confirm_reset_all", style="danger"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_reset_all", style="primary"),
            ]
        ]
    )
    
    await message.answer(
        "💥 <b>RESET EVERYTHING</b>\n\n"
        "<blockquote>⚠️ WARNING: This will delete ALL data:\n\n"
        "🗑 All users\n"
        "🗑 All orders\n"
        "🗑 All coupons\n"
        "🗑 All wallet transactions\n"
        "🗑 All referrals\n"
        "🗑 All support tickets\n"
        "🗑 All statistics\n\n"
        "This action CANNOT be undone!</blockquote>",
        reply_markup=markup
    )


@router.callback_query(F.data == "confirm_reset_all")
async def confirm_reset_all(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Admin only.", show_alert=True)
        return
    
    try:
        counts = reset_platform_data()

        # Structured error returned from reset_platform_data()
        if isinstance(counts, dict) and counts.get("error"):
            err = counts.get("error")
            audit_admin_action(callback.from_user.id, "reset_all_failed", err)
            await callback.message.edit_text(
                "❌ <b>Reset failed</b>\n\n"
                f"<blockquote>Error: {escape(str(err))}</blockquote>"
            )
            await callback.answer()
            return

        if counts is None:
            audit_admin_action(callback.from_user.id, "reset_all_failed", "unknown error")
            await callback.message.edit_text(
                "❌ <b>Reset failed</b>\n\n"
                "<blockquote>Database error occurred. Please try again.</blockquote>"
            )
            await callback.answer()
            return

        audit_admin_action(callback.from_user.id, "reset_all", f"deleted={counts}")

        await callback.message.edit_text(
            "✅ <b>Platform Reset Complete</b>\n\n"
            "<blockquote>"
            f"🗑 Users: <b>{counts.get('users', 0)}</b>\n"
            f"🗑 Orders: <b>{counts.get('orders', 0)}</b>\n"
            f"🗑 Coupons: <b>{counts.get('coupons', 0)}</b>\n"
            f"🗑 Wallet Transactions: <b>{counts.get('wallet_transactions', 0)}</b>\n"
            f"🗑 Referrals: <b>{counts.get('referrals', 0)}</b>\n"
            f"🗑 Tickets: <b>{counts.get('support_tickets', 0)}</b>\n"
            f"🗑 Stock Alerts: <b>{counts.get('stock_alerts', 0)}</b>\n"
            f"🗑 Flash Sales: <b>{counts.get('flash_sales', 0)}</b>\n"
            "</blockquote>"
        )
    except Exception as e:
        audit_admin_action(callback.from_user.id, "reset_all_failed", str(e))
        await callback.message.edit_text(
            "❌ <b>Reset failed</b>\n\n"
            f"<blockquote>Error: {escape(str(e))}</blockquote>"
        )

    await callback.answer()


@router.callback_query(F.data == "cancel_reset_all")
async def cancel_reset_all(callback: CallbackQuery):
    await callback.message.edit_text("✅ <b>Reset cancelled.</b>")
    await callback.answer()


@router.message(F.text.startswith("/retry_delivery "))
async def retry_delivery(message: Message, bot: Bot):
    if not await admin_only(message):
        return

    from database.crud import update_delivery_status, update_order_status

    order_id = message.text.replace("/retry_delivery ", "").strip()
    order = get_order_by_id(order_id)

    if not order:
        await message.answer("⚠️ <b>Order not found.</b>")
        return

    if order.coupon_name == "WALLET_TOPUP":
        add_wallet_credit(order.user_id, order.amount, f"Wallet top up for {order.order_id}")
        update_order_status(order_id, "SUCCESS")
        update_delivery_status(order_id, "DELIVERED")
        balance = get_wallet_balance(order.user_id)

        await bot.send_message(
            order.user_id,
            "💎 <b>Wallet Top Up Successful</b>\n\n"
            f"<blockquote>Order: <code>{order_id}</code>\n"
            f"Added: <b>Rs {order.amount}</b>\n"
            f"Wallet Balance: <b>Rs {balance}</b></blockquote>",
        )
        await message.answer("✅ <b>Retry wallet top up complete.</b>")
        audit_admin_action(message.from_user.id, "retry_wallet_topup", order_id)
        return

    coupon_code, remaining_stock = deliver_coupon(order.coupon_name)

    if not coupon_code:
        await message.answer("⚠️ <b>No unsold stock available for retry.</b>")
        return

    update_order_status(order_id, "SUCCESS")
    update_delivery_status(order_id, "DELIVERED")

    if should_send_stock_alert(remaining_stock):
        await notify_stock_alerts(
            bot,
            order.coupon_name,
            remaining_stock,
            reason="low_stock" if remaining_stock > 0 else "sold_out",
        )

    await bot.send_message(
        order.user_id,
        "🎉 <b>Delivery Retry Successful</b>\n\n"
        f"<blockquote>Order: <code>{order_id}</code>\n"
        f"Coupon Code:\n<code>{coupon_code}</code></blockquote>",
    )
    await message.answer("✅ <b>Retry delivery complete.</b>")
    audit_admin_action(message.from_user.id, "retry_delivery", order_id)
