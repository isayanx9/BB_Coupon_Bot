from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)


# =========================
# JOIN & VERIFY KEYBOARD
# =========================

def join_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(
        text="📢 Join Channel",
        url="https://t.me/FlashXDeal"
    )

    kb.button(
        text="👥 Join Group",
        url="https://t.me/FlashXSupports"
    )

    kb.button(
        text="✅ Verify",
        callback_data="verify_user"
    )

    kb.adjust(1)

    return kb.as_markup()


# =========================
# TERMS & CONDITIONS
# =========================

def terms_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(
        text="✅ Accept",
        callback_data="accept_terms"
    )

    kb.button(
        text="❌ Decline",
        callback_data="decline_terms"
    )

    kb.adjust(2)

    return kb.as_markup()


# =========================
# NORMAL USER MENU
# =========================

def user_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛒 Buy Coupons"),
                KeyboardButton(text="📦 My Orders")
            ],
            [
                KeyboardButton(text="👤 Profile"),
                KeyboardButton(text="🎁 Referral")
            ],
            [
                KeyboardButton(text="📞 Support")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Select an option..."
    )

    return keyboard


# =========================
# ADMIN MAIN MENU
# =========================

def admin_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛒 Buy Coupons"),
                KeyboardButton(text="📦 My Orders")
            ],
            [
                KeyboardButton(text="👤 Profile"),
                KeyboardButton(text="🎁 Referral")
            ],
            [
                KeyboardButton(text="📞 Support")
            ],
            [
                KeyboardButton(text="🛠 Developer")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Developer Mode Enabled"
    )

    return keyboard


# =========================
# DEFAULT MAIN MENU
# =========================

def main_menu():
    return user_main_menu()