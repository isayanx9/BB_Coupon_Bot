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
CASHFREE_ENV = os.getenv("CASHFREE_ENV", "production")
CASHFREE_CUSTOMER_PHONE = os.getenv("CASHFREE_CUSTOMER_PHONE", "9999999999")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
ADMIN_WEB_TOKEN = os.getenv("ADMIN_WEB_TOKEN", "").strip()


def require_env():
    required_values = {
        "BOT_TOKEN": BOT_TOKEN,
        "ADMIN_ID": ADMIN_ID,
        "CASHFREE_CLIENT_ID": CASHFREE_CLIENT_ID,
        "CASHFREE_CLIENT_SECRET": CASHFREE_CLIENT_SECRET,
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
