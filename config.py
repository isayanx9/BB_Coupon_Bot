from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

ADMIN_ID = os.getenv("ADMIN_ID")

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
GROUP_USERNAME = os.getenv("GROUP_USERNAME")

DATABASE_URL = os.getenv("DATABASE_URL")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
GROUP_USERNAME = os.getenv("GROUP_USERNAME")

CASHFREE_CLIENT_ID = os.getenv(
    "CASHFREE_CLIENT_ID"
)

CASHFREE_CLIENT_SECRET = os.getenv(
    "CASHFREE_CLIENT_SECRET"
)

CASHFREE_ENV = os.getenv(
    "CASHFREE_ENV"
)