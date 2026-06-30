from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from texts import (
    BTN_ADD_COUPON,
    BTN_ANALYTICS,
    BTN_AUDIT_LOGS,
    BTN_BACKUP,
    BTN_BAN_USER,
    BTN_BROADCAST,
    BTN_BULK_BUYER,
    BTN_DELETE_COUPON,
    BTN_EXIT_DEVELOPER,
    BTN_FLASH_SALE,
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
)


def developer_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADD_COUPON), KeyboardButton(text=BTN_INVENTORY)],
            [KeyboardButton(text=BTN_STATISTICS), KeyboardButton(text=BTN_ANALYTICS)],
            [KeyboardButton(text=BTN_PAYMENTS), KeyboardButton(text=BTN_ORDERS)],
            [KeyboardButton(text=BTN_BROADCAST), KeyboardButton(text=BTN_SETTINGS)],
            [KeyboardButton(text=BTN_BAN_USER), KeyboardButton(text=BTN_UNBAN_USER)],
            [KeyboardButton(text=BTN_SET_PRICE), KeyboardButton(text=BTN_DELETE_COUPON)],
            [KeyboardButton(text=BTN_TICKETS), KeyboardButton(text=BTN_REPLY_TICKET)],
            [KeyboardButton(text=BTN_WALLET_CREDIT), KeyboardButton(text=BTN_FLASH_SALE)],
            [KeyboardButton(text=BTN_BULK_BUYER)],
            [KeyboardButton(text=BTN_BACKUP), KeyboardButton(text=BTN_AUDIT_LOGS)],
            [KeyboardButton(text=BTN_RESET_ALL)],
            [KeyboardButton(text=BTN_MAIN_MENU)],
            [KeyboardButton(text=BTN_EXIT_DEVELOPER)],
        ],
        resize_keyboard=True,
    )
