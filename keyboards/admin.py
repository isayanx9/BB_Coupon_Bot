from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from texts import (
    BTN_ADD_COUPON,
    BTN_BROADCAST,
    BTN_BAN_USER,
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
)


def developer_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=BTN_ADD_COUPON),
                KeyboardButton(text=BTN_INVENTORY),
            ],
            [
                KeyboardButton(text=BTN_STATISTICS),
                KeyboardButton(text=BTN_USERS),
            ],
            [
                KeyboardButton(text=BTN_PAYMENTS),
                KeyboardButton(text=BTN_ORDERS),
            ],
            [
                KeyboardButton(text=BTN_BROADCAST),
                KeyboardButton(text=BTN_SETTINGS),
            ],
            [
                KeyboardButton(text=BTN_BAN_USER),
                KeyboardButton(text=BTN_UNBAN_USER),
            ],
            [
                KeyboardButton(text=BTN_SET_PRICE),
                KeyboardButton(text=BTN_DELETE_COUPON),
            ],
            [
                KeyboardButton(text=BTN_MAIN_MENU),
            ],
            [
                KeyboardButton(text=BTN_EXIT_DEVELOPER),
            ],
        ],
        resize_keyboard=True,
    )
