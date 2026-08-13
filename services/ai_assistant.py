from functools import lru_cache
from html import escape

import requests

from config import OPENAI_API_KEY, OPENAI_MODEL
from database.crud import get_feedback_memory_summary
from texts import AI_NAME, COUPON_NAME


BOT_KNOWLEDGE = """
BB Coupon Bot helps users join the required channel/group, accept terms, browse
Deal Vault coupons, create orders, pay through Cashfree, receive coupon codes
after payment webhooks, review Access Log orders, contact support, and use
Cutie AI for help. Admins can open Control Center, upload coupons in bulk,
review inventory, broadcast messages, ban/unban users, change prices, delete
unsold coupon stock, and edit settings like maintenance_mode.

Payment flow: user selects a coupon, the bot creates an order, Cashfree creates
a payment_session_id, the Pay Securely button opens /pay/<order_id>, Cashfree
redirects to /payment-result/<order_id>, and webhook /webhook/cashfree marks
SUCCESS orders as paid. If payment is debited but coupon is not
delivered, user should press I Paid, Recheck and send Order ID plus screenshot
to support. Admin should verify PUBLIC_BASE_URL, Cashfree production/sandbox
keys, CASHFREE_ENV, webhook URL, and coupon stock.

Ticket flow: user taps Support, sends one issue message, receives a Ticket ID,
and admin is notified. Admin opens Control Center, views Tickets, uses Reply
Ticket, sends the answer, and the bot delivers the reply to the user then closes
the ticket.

Premium UX: the bot uses quote blocks, bold, italic, monospace order IDs,
progress bars, payment energy effects, flash messages, wallet/referral/support
guidance, and hidden admin controls.
"""

SYSTEM_PROMPT = (
    f"You are {AI_NAME}, BB Coupon Bot's emotional AI assistant. Answer every "
    "question that is about this bot, how to use it, payments, orders, coupons, "
    "admin tools, settings, bugs, database issues, Railway deployment, or "
    "support. Be warm, clear, and practical. If the user asks unrelated general "
    "knowledge, politely bring them back to BB Coupon Bot. Never claim you can "
    "directly edit production or guarantee payment success. Bot knowledge: "
    f"{BOT_KNOWLEDGE}"
)

EMOTION_KEYWORDS = {
    "worried": ["stuck", "help", "not delivered", "missing", "waiting", "delay", "crash", "502", "gateway"],
    "upset": ["angry", "bad", "fraud", "scam", "hate", "wrong", "failed", "not working", "money debited"],
    "excited": ["wow", "nice", "great", "love", "awesome", "fast", "premium", "ultra", "pro"],
    "confused": ["how", "where", "what", "why", "confused", "don't know", "use", "which", "setup"],
    "urgent": ["urgent", "now", "quick", "immediately", "asap", "customer waiting"],
}

INTENT_KEYWORDS = {
    "payment": ["payment", "paid", "cashfree", "money", "debited", "upi", "checkout", "gateway", "webhook"],
    "coupon": ["coupon", "code", "buy", "stock", "deal", "vault", "inventory"],
    "database": ["database", "postgres", "sql", "railway", "db", "crash"],
    "admin": ["admin", "upload", "panel", "developer", "broadcast", "ban", "setting"],
    "order": ["order", "status", "delivery", "delivered", "pending", "access log"],
    "support": ["support", "contact", "issue", "problem", "bug", "fix", "ticket", "reply"],
    "howto": ["how", "use", "start", "join", "verify", "terms", "menu"],
    "premium": ["premium", "effect", "animation", "flash", "bar", "energy", "design", "ui"],
}


def detect_emotion(question):
    normalized = question.lower()
    scores = {
        emotion: sum(word in normalized for word in words)
        for emotion, words in EMOTION_KEYWORDS.items()
    }
    emotion = max(scores, key=scores.get)
    return emotion if scores[emotion] else "calm"


def detect_intent(question):
    normalized = question.lower()
    scores = {
        intent: sum(word in normalized for word in words)
        for intent, words in INTENT_KEYWORDS.items()
    }
    intent = max(scores, key=scores.get)
    return intent if scores[intent] else "general"


def emotion_prefix(emotion):
    prefixes = {
        "worried": "💖 I feel the stress. Cutie will walk you through it.",
        "upset": "🫶 That sounds frustrating. Let us make the next step clear.",
        "excited": "✨ Love that energy. Cutie is ready.",
        "confused": "🌸 No stress. I will explain it simply.",
        "calm": "💖 Cutie is online and listening.",
    }
    return prefixes.get(emotion, prefixes["calm"])


def answer_body(intent):
    if intent == "payment":
        return (
            "Payment path: <b>Deal Vault</b> -> select coupon -> <b>Pay Now</b> "
            "-> Cashfree checkout -> return to Telegram -> tap <b>I Paid, Recheck</b>. "
            "If money is debited but coupon is not delivered, keep the Order ID, "
            "UPI/payment screenshot, and exact time. Admin should verify "
            "<code>PUBLIC_BASE_URL</code>, <code>CASHFREE_CLIENT_ID</code>, "
            "<code>CASHFREE_CLIENT_SECRET</code>, <code>CASHFREE_ENV</code>, "
            "webhook URL <code>/webhook/cashfree</code>, and available coupon stock."
        )

    if intent == "coupon":
        return (
            f"Coupons are managed by admin. Users buy from <b>Deal Vault</b>. "
            f"Admin uploads rows like <code>{COUPON_NAME}|BB100ICE001|100|100|14</code>. "
            "The code is delivered only after successful payment webhook."
        )

    if intent == "database":
        return (
            "If Postgres was deleted, add a new Railway Postgres service and "
            "connect its <code>DATABASE_URL</code>. The bot now retries the DB "
            "and restart the service. Production orders require Postgres; the bot "
            "does not fall back to local SQLite."
        )

    if intent == "admin":
        return (
            "Admin tools are hidden from users. Use <b>Control Center</b> for "
            "bulk coupons, inventory, broadcast, settings, users, bans, price "
            "changes, and deleting unsold coupon groups."
        )

    if intent == "order":
        return (
            "Use <b>Access Log</b> to see orders. Pending means payment is not "
            "confirmed yet. SUCCESS plus NOT_DELIVERED means support should "
            "check coupon stock and webhook delivery."
        )

    if intent == "support":
        return (
            "To raise a ticket, tap <b>Support</b> and send one clear message. "
            "Include Order ID, payment screenshot details, the button you pressed, "
            "and the exact error. Admin receives the ticket instantly and can reply "
            "from Control Center -> Reply Ticket. You will receive the reply in chat."
        )

    if intent == "premium":
        return (
            "Premium effects available in this bot include quote panels, bold "
            "headings, italic guidance, monospace order IDs, flash edits, payment "
            "progress bars, and energy-ball checkout frames. Telegram does not "
            "let bots choose custom quote colors directly, so Cutie uses supported "
            "HTML styling that works for all users."
        )

    if intent == "howto":
        return (
            "Start with /start, join the channel and support group, press "
            "<b>Verify</b>, accept terms, then use <b>Deal Vault</b>, "
            "<b>Access Log</b>, <b>Support</b>, or <b>Cutie AI</b>."
        )

    return (
        "I can answer anything about BB Coupon Bot: setup, Deal Vault, coupon "
        "stock, orders, payments, Cashfree, webhook, refunds, support, wallet, "
        "referrals, admin tools, settings, bans, database, Railway deployment, "
        "and premium UI behavior. Ask me in normal language."
    )


@lru_cache(maxsize=512)
def local_ai_answer(question):
    emotion = detect_emotion(question)
    intent = detect_intent(question)
    prefix = emotion_prefix(emotion)

    return (
        f"<b>{AI_NAME} AI</b> 💖\n"
        f"<blockquote>{prefix}\n\n{answer_body(intent)}</blockquote>"
    )


def get_ai_answer(question):
    cleaned_question = (question or "").strip()
    # Free local FAQ mode: no external API, credits, or customer-question
    # sharing. Keep the legacy online path below unreachable for now.
    return local_ai_answer(cleaned_question)

    feedback_memory = get_feedback_memory_summary()

    if not cleaned_question:
        return local_ai_answer("")

    if not OPENAI_API_KEY:
        return local_ai_answer(cleaned_question)

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nRecent purchase feedback memory:\n{feedback_memory}"},
            {"role": "user", "content": cleaned_question},
        ],
        "temperature": 0.35,
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
        payload_data = response.json()
        content = payload_data["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise ValueError("OpenAI returned an empty response")
        return (
            f"<b>{AI_NAME} AI</b> 💖\n"
            f"<blockquote>{escape(content.strip())}</blockquote>"
        )
    except requests.RequestException as error:
        status = getattr(error.response, "status_code", "network")
        # Never log headers, the API key, or user messages. Railway logs need
        # only this safe status to diagnose billing, permissions, or model access.
        print(f"Cutie AI OpenAI request failed: status={status}, model={OPENAI_MODEL}")
        return local_ai_answer(cleaned_question)
    except (KeyError, TypeError, ValueError) as error:
        print(f"Cutie AI response format failed: {type(error).__name__}, model={OPENAI_MODEL}")
        return local_ai_answer(cleaned_question)


def get_ai_health():
    """Safe configuration status for health checks; never reveals the API key."""
    return {"mode": "free_local_faq", "external_api": False}
