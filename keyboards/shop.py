from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from texts import BTN_BUY_NOW, BTN_CANCEL_ORDER, BTN_PAY_NOW


def coupon_list_keyboard(options):
    rows = []

    for option in options:
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"🎟 {option['coupon_name']} "
                        f"• Rs {option['price']} "
                        f"• Stock {option['stock']}"
                    ),
                    callback_data=f"buy_type_{option['coupon_id']}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


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
