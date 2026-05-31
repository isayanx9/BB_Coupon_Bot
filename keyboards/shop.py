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