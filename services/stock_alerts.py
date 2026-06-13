from html import escape

from database.crud import get_stock_alert_user_ids


SMART_STOCK_LEVELS = {5, 3, 1, 0}


def should_send_stock_alert(stock_count):
    return stock_count in SMART_STOCK_LEVELS


def build_stock_alert_message(coupon_name, stock_count, reason="low_stock"):
    safe_coupon = escape(coupon_name)

    if reason == "restock":
        return (
            "🔔 <b>Fresh stock available</b>\n\n"
            f"<blockquote>Coupon: <code>{safe_coupon}</code>\n"
            f"Available now: <b>{stock_count}</b>\n"
            "Open Deal Vault before it sells out again.</blockquote>"
        )

    if stock_count == 0:
        tone = "Sold out"
        hint = "This coupon is fully exhausted for now."
    elif stock_count == 1:
        tone = "Final one left"
        hint = "Only one coupon remains."
    elif stock_count == 3:
        tone = "Low stock"
        hint = "Stock is moving fast."
    else:
        tone = "Stock watch"
        hint = "Only a few coupons remain."

    return (
        "⚠️ <b>Smart Stock Alert</b>\n\n"
        f"<blockquote>{tone}\n"
        f"Coupon: <code>{safe_coupon}</code>\n"
        f"Available: <b>{stock_count}</b>\n"
        f"{hint}</blockquote>"
    )


async def notify_stock_alerts(bot, coupon_name, stock_count, reason="low_stock"):
    user_ids = get_stock_alert_user_ids(coupon_name)

    if not user_ids:
        return 0

    message = build_stock_alert_message(coupon_name, stock_count, reason=reason)
    sent = 0

    for user_id in user_ids:
        try:
            await bot.send_message(chat_id=user_id, text=message)
            sent += 1
        except Exception:
            pass

    return sent
