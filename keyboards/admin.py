from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from texts import (
    BTN_ADD_COUPON,
    BTN_BROADCAST,
    BTN_EXIT_DEVELOPER,
    BTN_INVENTORY,
    BTN_MAIN_MENU,
    BTN_ORDERS,
    BTN_PAYMENTS,
    BTN_SETTINGS,
    BTN_STATISTICS,
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
                KeyboardButton(text=BTN_MAIN_MENU),
            ],
            [
                KeyboardButton(text=BTN_EXIT_DEVELOPER),
            ],
        ],
        resize_keyboard=True,
    )
