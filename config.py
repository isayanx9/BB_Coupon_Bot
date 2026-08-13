from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

ADMIN_ID = os.getenv("ADMIN_ID", "").strip()

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@FlashXDeal").strip()
GROUP_USERNAME = os.getenv("GROUP_USERNAME", "@FlashXSupports").strip()
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://bbcouponbot-production.up.railway.app",
).strip().rstrip("/")

DATABASE_URL = os.getenv("DATABASE_URL")

CASHFREE_CLIENT_ID = os.getenv("CASHFREE_CLIENT_ID")
CASHFREE_CLIENT_SECRET = os.getenv("CASHFREE_CLIENT_SECRET")
CASHFREE_ENV = os.getenv("CASHFREE_ENV", "production").strip().lower()
CASHFREE_CUSTOMER_PHONE = os.getenv("CASHFREE_CUSTOMER_PHONE", "").strip()
# The same configured server value creates Cashfree's order expiry and drives
# the Mini App's live countdown, so the UI never promises a different window.
PAYMENT_EXPIRY_MINUTES = max(1, int(os.getenv("PAYMENT_EXPIRY_MINUTES", "5")))
RUN_BOT_POLLING = os.getenv("RUN_BOT_POLLING", "false").lower() == "true"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
ADMIN_WEB_TOKEN = os.getenv("ADMIN_WEB_TOKEN", "").strip()


def require_env():
    if CASHFREE_ENV not in {"sandbox", "production"}:
        raise RuntimeError("CASHFREE_ENV must be either 'sandbox' or 'production'.")

    required_values = {
        "BOT_TOKEN": BOT_TOKEN,
        "ADMIN_ID": ADMIN_ID,
        "DATABASE_URL": DATABASE_URL,
        "CASHFREE_CLIENT_ID": CASHFREE_CLIENT_ID,
        "CASHFREE_CLIENT_SECRET": CASHFREE_CLIENT_SECRET,
        "CASHFREE_CUSTOMER_PHONE": CASHFREE_CUSTOMER_PHONE,
    }

    missing = [
        name
        for name, value in required_values.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )
