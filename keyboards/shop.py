from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def buy_coupon_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Buy Now",
                    callback_data="buy_bb_coupon"
                )
            ]
        ]
    )


def payment_keyboard(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Pay Now",
                    callback_data=f"pay_{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancel Order",
                    callback_data=f"cancel_{order_id}"
                )
            ]
        ]
    )