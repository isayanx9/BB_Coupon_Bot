from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def coupon_list_keyboard(options):
    rows = [
        [
            InlineKeyboardButton(
                text=f"Buy {option['coupon_name']} | Rs {option['price']} | {option['stock']} left",
                callback_data=f"buy_type_{option['coupon_id']}",
            )
        ]
        for option in options
    ]
    rows.append([InlineKeyboardButton(text="Notify me when deals restock", callback_data="stock_alert_ALL")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def buy_coupon_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Browse coupon deals", callback_data="buy_bb_coupon")]]
    )


def payment_keyboard(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Pay securely", callback_data=f"pay_{order_id}")],
            [InlineKeyboardButton(text="I've paid - check status", callback_data=f"recheck_{order_id}")],
            [InlineKeyboardButton(text="Cancel this order", callback_data=f"cancel_{order_id}")],
        ]
    )
