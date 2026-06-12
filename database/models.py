from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    BigInteger,
    DateTime
)

from sqlalchemy.orm import declarative_base

from datetime import datetime

Base = declarative_base()


# =========================
# USERS
# =========================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    telegram_id = Column(
        BigInteger,
        unique=True
    )

    username = Column(String(100))

    joined_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class BannedUser(Base):
    __tablename__ = "banned_users"

    id = Column(Integer, primary_key=True)

    telegram_id = Column(
        BigInteger,
        unique=True
    )

    reason = Column(
        String(255),
        default="Admin ban"
    )

    banned_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class BotSetting(Base):
    __tablename__ = "bot_settings"

    id = Column(Integer, primary_key=True)

    key = Column(
        String(100),
        unique=True
    )

    value = Column(String(1000))


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    amount = Column(Integer)
    reason = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True)
    referrer_id = Column(BigInteger)
    referred_id = Column(BigInteger, unique=True)
    reward_amount = Column(Integer, default=0)
    rewarded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    subject = Column(String(255))
    status = Column(String(50), default="OPEN")
    messages = Column(String(4000), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class StockAlert(Base):
    __tablename__ = "stock_alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    coupon_name = Column(String(255), default="ALL")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger)
    action = Column(String(255))
    details = Column(String(1000))
    created_at = Column(DateTime, default=datetime.utcnow)


class FlashSale(Base):
    __tablename__ = "flash_sales"

    id = Column(Integer, primary_key=True)
    coupon_name = Column(String(255))
    title = Column(String(255))
    discount_text = Column(String(255))
    active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================
# COUPONS
# =========================

class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True)

    coupon_name = Column(String(255))

    coupon_code = Column(
        String(255),
        unique=True
    )

    discount_value = Column(Integer)

    minimum_order = Column(Integer)

    selling_price = Column(
        Integer,
        default=14
    )

    sold = Column(
        Boolean,
        default=False
    )


# =========================
# ORDERS
# =========================

class Order(Base):
    __tablename__ = "orders"

    id = Column(
        Integer,
        primary_key=True
    )

    order_id = Column(
        String(50),
        unique=True
    )

    user_id = Column(
        BigInteger
    )

    coupon_name = Column(
        String(255)
    )

    coupon_code = Column(
        String(255)
    )

    # NEW FIELD
    payment_session_id = Column(
        String(500),
        nullable=True
    )

    amount = Column(
        Integer
    )

    payment_status = Column(
        String(50),
        default="PENDING"
    )

    delivery_status = Column(
        String(50),
        default="NOT_DELIVERED"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
