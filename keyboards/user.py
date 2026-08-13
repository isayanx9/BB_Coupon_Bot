from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CHANNEL_USERNAME, GROUP_USERNAME, PUBLIC_BASE_URL
from texts import (
    BTN_ACCEPT,
    BTN_ACCESS_LOG,
    BTN_AI_ASSIST,
    BTN_CONTROL_CENTER,
    BTN_DEAL_VAULT,
    BTN_DECLINE,
    BTN_JOIN_CHANNEL,
    BTN_JOIN_GROUP,
    BTN_PROFILE,
    BTN_REFERRAL,
    BTN_RAISE_TICKET,
    BTN_STOCK_ALERTS,
    BTN_SUPPORT,
    BTN_VERIFY,
    BTN_WALLET,
)


def join_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text=BTN_JOIN_CHANNEL, url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")
    kb.button(text=BTN_JOIN_GROUP, url=f"https://t.me/{GROUP_USERNAME.lstrip('@')}")
    kb.button(text=BTN_VERIFY, callback_data="verify_user", style="primary")
    kb.adjust(1)
    return kb.as_markup()


def terms_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text=BTN_ACCEPT, callback_data="accept_terms", style="success")
    kb.button(text=BTN_DECLINE, callback_data="decline_terms", style="danger")
    kb.adjust(2)
    return kb.as_markup()


def launch_shop_keyboard():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="🛍️ Open BB Coupon Shop",
            web_app=WebAppInfo(url=f"{PUBLIC_BASE_URL}/mini"),
            style="primary",
        )
    )
    return kb.as_markup()


def user_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_DEAL_VAULT, style="success"), KeyboardButton(text=BTN_ACCESS_LOG, style="primary")],
            [KeyboardButton(text=BTN_WALLET, style="success"), KeyboardButton(text=BTN_REFERRAL, style="primary")],
            [KeyboardButton(text=BTN_AI_ASSIST, style="primary"), KeyboardButton(text=BTN_PROFILE, style="primary")],
            [KeyboardButton(text=BTN_SUPPORT, style="primary"), KeyboardButton(text=BTN_RAISE_TICKET, style="danger")],
            [KeyboardButton(text=BTN_STOCK_ALERTS, style="primary")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✨ What would you like to do?",
    )


def admin_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_DEAL_VAULT, style="success"), KeyboardButton(text=BTN_ACCESS_LOG, style="primary")],
            [KeyboardButton(text=BTN_WALLET, style="success"), KeyboardButton(text=BTN_REFERRAL, style="primary")],
            [KeyboardButton(text=BTN_AI_ASSIST, style="primary"), KeyboardButton(text=BTN_PROFILE, style="primary")],
            [KeyboardButton(text=BTN_SUPPORT, style="primary"), KeyboardButton(text=BTN_RAISE_TICKET, style="danger")],
            [KeyboardButton(text=BTN_STOCK_ALERTS, style="primary")],
            [KeyboardButton(text=BTN_CONTROL_CENTER, style="danger")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="🛠️ Admin control center",
    )


def main_menu():
    return user_main_menu()
