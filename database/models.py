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

    # NEW
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