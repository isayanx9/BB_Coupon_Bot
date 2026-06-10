from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from texts import BTN_BUY_NOW, BTN_CANCEL_ORDER, BTN_PAY_NOW


def buy_coupon_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_BUY_NOW,
                    callback_data="buy_bb_coupon",
                )
            ]
        ]
    )


def payment_keyboard(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_PAY_NOW,
                    callback_data=f"pay_{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN_CANCEL_ORDER,
                    callback_data=f"cancel_{order_id}",
                )
            ],
        ]
    )
