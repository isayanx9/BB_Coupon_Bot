import requests
from html import escape

from config import OPENAI_API_KEY, OPENAI_MODEL
from texts import COUPON_NAME


SYSTEM_PROMPT = (
    "You are BB Coupon Bot AI Assist. Help users with coupon buying, order "
    "status, payment delay guidance, support steps, and basic admin workflow. "
    "Be concise, truthful, and never claim you can directly change production "
    "unless the admin takes action."
)


def local_ai_answer(question):
    normalized = question.lower()

    if any(word in normalized for word in ["payment", "paid", "cashfree"]):
        return (
            "<b>Payment help</b>\n"
            "<blockquote>If payment succeeded but the coupon was not delivered, "
            "send your Order ID to support. Delivery depends on Cashfree webhook "
            "confirmation.</blockquote>"
        )

    if any(word in normalized for word in ["coupon", "code", "buy", "stock"]):
        return (
            "<b>Coupon help</b>\n"
            f"The current product is <code>{COUPON_NAME}</code>.\n"
            "Open <b>Deal Vault</b>, create an order, then pay from the secure "
            "payment button."
        )

    if any(word in normalized for word in ["bug", "error", "fix", "issue"]):
        return (
            "<b>Bug support</b>\n"
            "<i>I can help diagnose common bot issues.</i>\n"
            "Send the error message, Order ID, and what button you pressed. "
            "The admin can then update and redeploy the bot."
        )

    if any(word in normalized for word in ["admin", "upload", "inventory"]):
        return (
            "<b>Admin help</b>\n"
            "Use <b>Control Center</b> to upload coupons in this format:\n"
            f"<code>{COUPON_NAME}|BB100ICE001|100|100|14</code>"
        )

    return (
        "<b>AI Assist</b>\n"
        "<blockquote>I can help with orders, payments, coupon delivery, stock, "
        "support, and admin upload steps.</blockquote>\n"
        "Please send your question with any Order ID or error text."
    )


def get_ai_answer(question):
    if not OPENAI_API_KEY:
        return local_ai_answer(question)

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return (
            "<b>AI Assist</b>\n"
            f"<blockquote>{escape(content.strip())}</blockquote>"
        )
    except Exception:
        return local_ai_answer(question)
