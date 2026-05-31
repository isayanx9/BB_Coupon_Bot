from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.order_states import CouponUpload

from database.crud import (
    add_coupon,
    get_total_coupons,
    get_total_orders,
    get_total_revenue,
    get_pending_orders,
    get_completed_orders,
    get_failed_orders,
    get_cancelled_orders
)

from config import ADMIN_ID

from keyboards.admin import developer_menu

from keyboards.user import (
    admin_main_menu,
    user_main_menu
)

router = Router()


# =========================
# DEVELOPER COMMAND
# =========================

@router.message(F.text == "/developer")
async def developer_panel(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Developer Only")
        return

    await message.answer(
        "🛠 Developer Panel",
        reply_markup=developer_menu()
    )


# =========================
# DEVELOPER BUTTON
# =========================

@router.message(F.text == "🛠 Developer")
async def developer_button(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Developer Only")
        return

    await message.answer(
        "🛠 Developer Panel",
        reply_markup=developer_menu()
    )


# =========================
# MAIN MENU
# =========================

@router.message(F.text == "🏠 Main Menu")
async def main_menu_button(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        "🏠 Main Menu",
        reply_markup=admin_main_menu()
    )


# =========================
# EXIT DEVELOPER PANEL
# =========================

@router.message(F.text == "❌ Exit Developer Panel")
async def exit_developer(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        "✅ Developer Panel Closed",
        reply_markup=user_main_menu()
    )


# =========================
# ADD COUPON
# =========================

@router.message(F.text == "➕ Add Coupon")
async def add_coupon_button(
    message: Message,
    state: FSMContext
):

    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Developer Only")
        return

    await message.answer(
        "📥 Send bulk coupons\n\n"
        "Format:\n"
        "Coupon Name|Coupon Code|Discount|Minimum Order|Price\n\n"
        "Example:\n"
        "BigBasket Chocolate & Ice Cream|BB100ICE001|100|100|14"
    )

    await state.set_state(
        CouponUpload.waiting_for_bulk_coupons
    )


# =========================
# PROCESS COUPONS
# =========================

@router.message(
    CouponUpload.waiting_for_bulk_coupons
)
async def process_bulk_coupon(
    message: Message,
    state: FSMContext
):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    lines = message.text.split("\n")

    added = 0
    failed = 0

    for line in lines:

        try:

            (
                name,
                code,
                discount,
                minimum,
                price
            ) = line.split("|")

            success = add_coupon(
                name.strip(),
                code.strip(),
                int(discount),
                int(minimum),
                int(price)
            )

            if success:
                added += 1
            else:
                failed += 1

        except Exception:
            failed += 1

    await message.answer(
        f"✅ Upload Complete\n\n"
        f"Added: {added}\n"
        f"Failed: {failed}"
    )

    await state.clear()


# =========================
# INVENTORY
# =========================

@router.message(F.text == "📦 Inventory")
async def inventory(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    total = get_total_coupons()

    await message.answer(
        f"📦 Inventory\n\n"
        f"Total Coupons: {total}"
    )


# =========================
# STATISTICS
# =========================

@router.message(F.text == "📊 Statistics")
async def statistics(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    total_coupons = get_total_coupons()
    total_orders = get_total_orders()
    revenue = get_total_revenue()

    await message.answer(
        f"📊 Statistics\n\n"
        f"📦 Total Coupons: {total_coupons}\n"
        f"📋 Total Orders: {total_orders}\n"
        f"💰 Revenue: ₹{revenue}"
    )


# =========================
# USERS
# =========================

@router.message(F.text == "👥 Users")
async def users(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        "👥 User Statistics\n\n"
        "Coming Soon..."
    )


# =========================
# PAYMENTS
# =========================

@router.message(F.text == "💰 Payments")
async def payments(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    revenue = get_total_revenue()

    await message.answer(
        f"💰 Payment Dashboard\n\n"
        f"✅ Successful: {get_completed_orders()}\n"
        f"⏳ Pending: {get_pending_orders()}\n"
        f"❌ Failed: {get_failed_orders()}\n"
        f"🚫 Cancelled: {get_cancelled_orders()}\n\n"
        f"💵 Revenue: ₹{revenue}"
    )


# =========================
# ORDERS
# =========================

@router.message(F.text == "📋 Orders")
async def orders(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        f"📋 Orders Dashboard\n\n"
        f"Total Orders: {get_total_orders()}\n"
        f"Pending: {get_pending_orders()}\n"
        f"Completed: {get_completed_orders()}\n"
        f"Failed: {get_failed_orders()}\n"
        f"Cancelled: {get_cancelled_orders()}"
    )


# =========================
# BROADCAST
# =========================

@router.message(F.text == "📢 Broadcast")
async def broadcast(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        "📢 Broadcast System\n\nComing Soon..."
    )


# =========================
# SETTINGS
# =========================

@router.message(F.text == "⚙️ Settings")
async def settings(message: Message):

    if str(message.from_user.id) != str(ADMIN_ID):
        return

    await message.answer(
        "⚙️ Settings\n\nComing Soon..."
    )