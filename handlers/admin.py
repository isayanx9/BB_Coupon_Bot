from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID
from database.crud import (
    add_coupon,
    get_cancelled_orders,
    get_completed_orders,
    get_failed_orders,
    get_pending_orders,
    get_total_coupons,
    get_total_orders,
    get_total_revenue,
)
from keyboards.admin import developer_menu
from keyboards.user import (
    admin_main_menu,
    user_main_menu,
)
from states.order_states import CouponUpload
from texts import (
    BTN_ADD_COUPON,
    BTN_BROADCAST,
    BTN_CONTROL_CENTER,
    BTN_EXIT_DEVELOPER,
    BTN_INVENTORY,
    BTN_MAIN_MENU,
    BTN_ORDERS,
    BTN_PAYMENTS,
    BTN_SETTINGS,
    BTN_STATISTICS,
    BTN_USERS,
    COUPON_NAME,
)

router = Router()


@router.message(F.text == "/developer")
async def developer_panel(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("🚫 <b>Developer only.</b>")
        return

    await message.answer(
        "🛠 <b>FLASH-X Control Center</b>\n\n"
        "<blockquote>Cutie is watching inventory, payments, orders, and bug reports.</blockquote>",
        reply_markup=developer_menu(),
    )


@router.message(F.text == BTN_CONTROL_CENTER)
async def developer_button(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("🚫 <b>Access denied.</b>")
        return

    await message.answer(
        "🛠 <b>Developer Panel</b>\n\n"
        "<blockquote>Premium control mode is active.</blockquote>",
        reply_markup=developer_menu(),
    )


@router.message(F.text == BTN_MAIN_MENU)
async def main_menu_button(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        "🏠 <b>Main Menu</b>",
        reply_markup=admin_main_menu(),
    )


@router.message(F.text == BTN_EXIT_DEVELOPER)
async def exit_developer(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        "✨ <b>Control center closed.</b>",
        reply_markup=user_main_menu(),
    )


@router.message(F.text == BTN_ADD_COUPON)
async def add_coupon_button(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("🚫 <b>Developer only.</b>")
        return

    await message.answer(
        "➕ <b>Inventory Import</b>\n\n"
        "<blockquote>Cutie will parse bulk coupons fast. Coupon codes stay "
        "clean in monospace format.</blockquote>\n\n"
        "📌 <b>Format</b>\n"
        "<code>Coupon Name|Coupon Code|Discount|Minimum Order|Price</code>\n\n"
        "✨ <b>Example</b>\n"
        f"<code>{COUPON_NAME}|BB100ICE001|100|100|14</code>"
    )

    await state.set_state(CouponUpload.waiting_for_bulk_coupons)


@router.message(CouponUpload.waiting_for_bulk_coupons)
async def process_bulk_coupon(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    lines = message.text.split("\n")
    added = 0
    failed = 0

    for line in lines:
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
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    total = get_total_coupons()

    await message.answer(
        "📦 <b>Inventory</b>\n\n"
        f"<blockquote>🎟 Total Coupons: <b>{total}</b></blockquote>"
    )


@router.message(F.text == BTN_STATISTICS)
async def statistics(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    total_coupons = get_total_coupons()
    total_orders = get_total_orders()
    revenue = get_total_revenue()

    await message.answer(
        "📊 <b>Statistics</b>\n\n"
        f"<blockquote>🎟 Total Coupons: <b>{total_coupons}</b>\n"
        f"📋 Total Orders: <b>{total_orders}</b>\n"
        f"💰 Revenue: <b>Rs {revenue}</b></blockquote>"
    )


@router.message(F.text == BTN_USERS)
async def users(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer("👥 <b>User Statistics</b>\n\n<i>Coming soon.</i>")


@router.message(F.text == BTN_PAYMENTS)
async def payments(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    revenue = get_total_revenue()

    await message.answer(
        "💳 <b>Payment Dashboard</b>\n\n"
        f"<blockquote>✅ Successful: <b>{get_completed_orders()}</b>\n"
        f"⏳ Pending: <b>{get_pending_orders()}</b>\n"
        f"❌ Failed: <b>{get_failed_orders()}</b>\n"
        f"🚫 Cancelled: <b>{get_cancelled_orders()}</b>\n\n"
        f"💰 Revenue: <b>Rs {revenue}</b></blockquote>"
    )


@router.message(F.text == BTN_ORDERS)
async def orders(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
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
async def broadcast(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer("📣 <b>Broadcast System</b>\n\n<i>Coming soon.</i>")


@router.message(F.text == BTN_SETTINGS)
async def settings(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer("⚙️ <b>Settings</b>\n\n<i>Coming soon.</i>")
