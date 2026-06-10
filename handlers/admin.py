from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_ID
from database.crud import (
    add_coupon,
    ban_user,
    delete_coupon_group,
    get_all_bot_settings,
    get_all_user_ids,
    get_banned_users,
    get_cancelled_orders,
    get_completed_orders,
    get_coupon_summary,
    get_failed_orders,
    get_pending_orders,
    get_total_coupons,
    get_total_orders,
    get_total_revenue,
    get_total_users,
    is_user_banned,
    set_bot_setting,
    unban_user,
    update_coupon_price,
)
from keyboards.admin import developer_menu
from keyboards.user import admin_main_menu, user_main_menu
from states.order_states import (
    BanState,
    BroadcastState,
    CouponUpload,
    DeleteCouponState,
    PriceState,
    SettingState,
    UnbanState,
)
from texts import (
    BTN_ADD_COUPON,
    BTN_BAN_USER,
    BTN_BROADCAST,
    BTN_CONTROL_CENTER,
    BTN_DELETE_COUPON,
    BTN_EXIT_DEVELOPER,
    BTN_INVENTORY,
    BTN_MAIN_MENU,
    BTN_ORDERS,
    BTN_PAYMENTS,
    BTN_SETTINGS,
    BTN_SET_PRICE,
    BTN_STATISTICS,
    BTN_UNBAN_USER,
    BTN_USERS,
    COUPON_NAME,
)

router = Router()


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
        "<code>Coupon Name|Coupon Code|Discount|Minimum Order|Price</code>\n\n"
        "✨ <b>Example</b>\n"
        f"<code>{COUPON_NAME}|BB100ICE001|100|100|14</code>"
    )
    await state.set_state(CouponUpload.waiting_for_bulk_coupons)


@router.message(CouponUpload.waiting_for_bulk_coupons)
async def process_bulk_coupon(message: Message, state: FSMContext):
    if not is_admin(message):
        return

    added = 0
    failed = 0

    for line in message.text.splitlines():
        if not line.strip():
            continue

        try:
            name, code, discount, minimum, price = line.split("|")
            success = add_coupon(
                name.strip(),
                code.strip(),
                int(discount),
                int(minimum),
                int(price),
            )

            if success:
                added += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    await message.answer(
        "✨ <b>Upload Complete</b>\n\n"
        f"<blockquote>✅ Added: <b>{added}</b>\n"
        f"⚠️ Failed: <b>{failed}</b></blockquote>"
    )
    await state.clear()


@router.message(F.text == BTN_INVENTORY)
async def inventory(message: Message):
    if not is_admin(message):
        return

    summary = get_coupon_summary()
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


@router.message(F.text == BTN_BROADCAST)
async def broadcast(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

    await message.answer(
        "📣 <b>Broadcast System</b>\n\n"
        "<blockquote>Send the text Cutie should send to every known non-banned user.</blockquote>"
    )
    await state.set_state(BroadcastState.waiting_for_message)


@router.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message):
        return

    sent = 0
    failed = 0

    for user_id in get_all_user_ids():
        if is_user_banned(user_id):
            continue

        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "📣 <b>Broadcast from BB Coupon Bot</b>\n\n"
                    f"<blockquote>{escape(message.text)}</blockquote>"
                ),
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        "✨ <b>Broadcast complete</b>\n\n"
        f"<blockquote>Sent: <b>{sent}</b>\nFailed: <b>{failed}</b></blockquote>"
    )
    await state.clear()


@router.message(F.text == BTN_SETTINGS)
async def settings(message: Message, state: FSMContext):
    if not await admin_only(message):
        return

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
    await state.clear()
