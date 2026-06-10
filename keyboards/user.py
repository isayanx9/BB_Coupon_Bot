from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from config import CHANNEL_USERNAME, GROUP_USERNAME
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
    BTN_SUPPORT,
    BTN_VERIFY,
)


def join_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(
        text=BTN_JOIN_CHANNEL,
        url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
    )
    kb.button(
        text=BTN_JOIN_GROUP,
        url=f"https://t.me/{GROUP_USERNAME.lstrip('@')}",
    )
    kb.button(
        text=BTN_VERIFY,
        callback_data="verify_user",
    )

    kb.adjust(1)
    return kb.as_markup()


def terms_keyboard():
    kb = InlineKeyboardBuilder()

    kb.button(
        text=BTN_ACCEPT,
        callback_data="accept_terms",
    )
    kb.button(
        text=BTN_DECLINE,
        callback_data="decline_terms",
    )

    kb.adjust(2)
    return kb.as_markup()


def user_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_DEAL_VAULT),
                KeyboardButton(text=BTN_ACCESS_LOG),
            ],
            [
                KeyboardButton(text=BTN_AI_ASSIST),
                KeyboardButton(text=BTN_PROFILE),
            ],
            [
                KeyboardButton(text=BTN_SUPPORT),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="FLASH-X AI",
    )


def admin_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_DEAL_VAULT),
                KeyboardButton(text=BTN_ACCESS_LOG),
            ],
            [
                KeyboardButton(text=BTN_AI_ASSIST),
                KeyboardButton(text=BTN_PROFILE),
            ],
            [
                KeyboardButton(text=BTN_SUPPORT),
            ],
            [
                KeyboardButton(text=BTN_CONTROL_CENTER),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="FLASH-X CONTROL CENTER",
    )


def main_menu():
    return user_main_menu()
