from functools import lru_cache
from html import escape

import requests

from config import OPENAI_API_KEY, OPENAI_MODEL
from texts import AI_NAME, COUPON_NAME


SYSTEM_PROMPT = (
    f"You are {AI_NAME}, BB Coupon Bot's emotional AI assistant. You are warm, "
    "sweet, premium, and concise. You help users with coupon buying, order "
    "status, payment delay guidance, support steps, bug reports, and admin "
    "workflow. Detect the user's emotion and respond with empathy. Do not "
    "claim you can directly edit production or guarantee bug fixes unless an "
    "admin deploys changes."
)

EMOTION_KEYWORDS = {
    "worried": ["stuck", "help", "not delivered", "missing", "waiting", "delay"],
    "upset": ["angry", "bad", "fraud", "scam", "hate", "wrong"],
    "excited": ["wow", "nice", "great", "love", "awesome", "fast"],
    "confused": ["how", "where", "what", "why", "confused", "don't know"],
}

INTENT_KEYWORDS = {
    "payment": ["payment", "paid", "cashfree", "money", "debited", "upi"],
    "coupon": ["coupon", "code", "buy", "stock", "deal", "vault"],
    "bug": ["bug", "error", "fix", "issue", "broken", "crash"],
    "admin": ["admin", "upload", "inventory", "panel", "developer"],
    "order": ["order", "status", "delivery", "delivered", "pending"],
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
        "worried": "💖 I feel that worry. Cutie is here with you.",
        "upset": "🫶 I get why that feels frustrating. Let us fix the path.",
        "excited": "✨ Love that energy. Cutie is ready.",
        "confused": "🌸 No stress. I will make it simple.",
        "calm": "💖 Cutie is online and listening.",
    }
    return prefixes.get(emotion, prefixes["calm"])


@lru_cache(maxsize=256)
def local_ai_answer(question):
    emotion = detect_emotion(question)
    intent = detect_intent(question)
    prefix = emotion_prefix(emotion)

    if intent == "payment":
        body = (
            "If payment succeeded but the coupon was not delivered, send your "
            "Order ID and payment screenshot to support. Delivery waits for "
            "Cashfree webhook confirmation, so gateway delay can happen."
        )
    elif intent == "coupon":
        body = (
            f"The current premium coupon is <code>{COUPON_NAME}</code>. Open "
            "<b>Deal Vault</b>, tap <b>Buy Now</b>, then complete the secure "
            "payment checkout."
        )
    elif intent == "bug":
        body = (
            "Send the exact error, button name, Order ID if any, and what you "
            "expected. I can guide the report so the admin can patch and "
            "redeploy the bot faster."
        )
    elif intent == "admin":
        body = (
            "Open <b>Control Center</b> and upload inventory like this:\n"
            f"<code>{COUPON_NAME}|BB100ICE001|100|100|14</code>"
        )
    elif intent == "order":
        body = (
            "Open <b>Access Log</b> to see your latest orders. If payment is "
            "<i>SUCCESS</i> but delivery is not complete, contact support with "
            "the Order ID."
        )
    else:
        body = (
            "Ask me about payments, orders, coupon stock, delivery, bugs, or "
            "admin uploads. I use a small local machine-learning style keyword "
            "model here, and deep AI answers when OpenAI is configured."
        )

    return (
        f"<b>{AI_NAME} AI</b> 💖\n"
        f"<blockquote>{prefix}\n\n{body}</blockquote>"
    )


def get_ai_answer(question):
    cleaned_question = (question or "").strip()

    if not cleaned_question:
        return local_ai_answer("")

    if not OPENAI_API_KEY:
        return local_ai_answer(cleaned_question)

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
        content = response.json()["choices"][0]["message"]["content"]
        return (
            f"<b>{AI_NAME} AI</b> 💖\n"
            f"<blockquote>{escape(content.strip())}</blockquote>"
        )
    except Exception:
        return local_ai_answer(cleaned_question)
