import os
import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL

LOCAL_DATABASE_URL = "sqlite:///database/bot.db"
ALLOW_SQLITE_FALLBACK = os.getenv(
    "ALLOW_SQLITE_FALLBACK",
    "false",
).lower() == "true"


def normalize_database_url(url):
    if not url:
        return None

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)

    return url


def build_engine(url):
    connect_args = {}

    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


active_database_url = normalize_database_url(DATABASE_URL) or LOCAL_DATABASE_URL
engine = build_engine(active_database_url)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def switch_database(url):
    global active_database_url, engine, SessionLocal

    active_database_url = url
    engine = build_engine(url)
    SessionLocal.configure(bind=engine)


def initialize_database(base, retries=3, delay=2):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            base.metadata.create_all(bind=engine)
            _migrate_order_fields()
            print(f"Database ready: {active_database_url}")
            return active_database_url
        except SQLAlchemyError as error:
            last_error = error
            print(f"Database connection failed ({attempt}/{retries}): {error}")
            time.sleep(delay)

    if (
        active_database_url != LOCAL_DATABASE_URL
        and ALLOW_SQLITE_FALLBACK
    ):
        print("Postgres unavailable. Falling back to local SQLite database.")
        switch_database(LOCAL_DATABASE_URL)
        base.metadata.create_all(bind=engine)
        _migrate_order_fields()
        return active_database_url

    raise RuntimeError(
        "Database is not available. Add a new Railway Postgres database and "
        "set DATABASE_URL, or enable ALLOW_SQLITE_FALLBACK=true."
    ) from last_error


def _migrate_order_fields():
    """Add fields introduced after the first deployed orders table."""
    columns = {column["name"] for column in inspect(engine).get_columns("orders")}
    statements = []
    if "quantity" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1")
    if "payment_expires_at" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN payment_expires_at TIMESTAMP NULL")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
