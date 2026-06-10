from database.db import SessionLocal
from database.models import BannedUser, BotSetting, Coupon, Order, User

import random


def track_user(telegram_id, username=None):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.telegram_id == telegram_id)
            .first()
        )

        if user:
            user.username = username or user.username
        else:
            user = User(
                telegram_id=telegram_id,
                username=username
            )
            db.add(user)

        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def get_total_users():
    db = SessionLocal()

    try:
        return db.query(User).count()

    finally:
        db.close()


def get_all_user_ids():
    db = SessionLocal()

    try:
        return [
            row.telegram_id
            for row in db.query(User.telegram_id).all()
        ]

    finally:
        db.close()


def ban_user(telegram_id, reason="Admin ban"):
    db = SessionLocal()

    try:
        banned = (
            db.query(BannedUser)
            .filter(BannedUser.telegram_id == telegram_id)
            .first()
        )

        if banned:
            banned.reason = reason
        else:
            banned = BannedUser(
                telegram_id=telegram_id,
                reason=reason
            )
            db.add(banned)

        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def unban_user(telegram_id):
    db = SessionLocal()

    try:
        banned = (
            db.query(BannedUser)
            .filter(BannedUser.telegram_id == telegram_id)
            .first()
        )

        if not banned:
            return False

        db.delete(banned)
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def is_user_banned(telegram_id):
    db = SessionLocal()

    try:
        return (
            db.query(BannedUser)
            .filter(BannedUser.telegram_id == telegram_id)
            .first()
            is not None
        )

    finally:
        db.close()


def get_banned_users(limit=20):
    db = SessionLocal()

    try:
        return (
            db.query(BannedUser)
            .order_by(BannedUser.id.desc())
            .limit(limit)
            .all()
        )

    finally:
        db.close()


def set_bot_setting(key, value):
    db = SessionLocal()

    try:
        setting = (
            db.query(BotSetting)
            .filter(BotSetting.key == key)
            .first()
        )

        if setting:
            setting.value = value
        else:
            setting = BotSetting(key=key, value=value)
            db.add(setting)

        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def get_bot_setting(key, default=None):
    db = SessionLocal()

    try:
        setting = (
            db.query(BotSetting)
            .filter(BotSetting.key == key)
            .first()
        )

        if setting:
            return setting.value

        return default

    finally:
        db.close()


def get_all_bot_settings():
    db = SessionLocal()

    try:
        return db.query(BotSetting).order_by(BotSetting.key).all()

    finally:
        db.close()


# =========================
# COUPON FUNCTIONS
# =========================

def add_coupon(
    coupon_name,
    coupon_code,
    discount_value,
    minimum_order,
    selling_price
):
    db = SessionLocal()

    try:

        coupon = Coupon(
            coupon_name=coupon_name,
            coupon_code=coupon_code,
            discount_value=discount_value,
            minimum_order=minimum_order,
            selling_price=selling_price
        )

        db.add(coupon)
        db.commit()

        return True

    except Exception:

        db.rollback()

        return False

    finally:

        db.close()


def get_total_coupons():
    db = SessionLocal()

    try:
        return db.query(Coupon).count()

    finally:
        db.close()


def get_available_coupons():
    db = SessionLocal()

    try:
        return (
            db.query(Coupon)
            .filter(Coupon.sold == False)
            .all()
        )

    finally:
        db.close()


def get_coupon_type_options():
    db = SessionLocal()

    try:
        coupons = (
            db.query(Coupon)
            .filter(Coupon.sold == False)
            .order_by(Coupon.coupon_name.asc(), Coupon.id.asc())
            .all()
        )

        options = {}

        for coupon in coupons:
            item = options.setdefault(
                coupon.coupon_name,
                {
                    "coupon_id": coupon.id,
                    "coupon_name": coupon.coupon_name,
                    "stock": 0,
                    "price": coupon.selling_price,
                    "discount": coupon.discount_value,
                    "minimum": coupon.minimum_order,
                }
            )
            item["stock"] += 1

        return list(options.values())

    finally:
        db.close()


def get_coupon_by_id(coupon_id):
    db = SessionLocal()

    try:
        return (
            db.query(Coupon)
            .filter(Coupon.id == coupon_id)
            .first()
        )

    finally:
        db.close()


def get_coupon_summary(limit=20):
    db = SessionLocal()

    try:
        coupons = db.query(Coupon).order_by(Coupon.coupon_name.asc()).all()
        summary = {}

        for coupon in coupons:
            item = summary.setdefault(
                coupon.coupon_name,
                {
                    "name": coupon.coupon_name,
                    "total": 0,
                    "sold": 0,
                    "available": 0,
                    "price": coupon.selling_price,
                    "discount": coupon.discount_value,
                    "minimum": coupon.minimum_order,
                }
            )
            item["total"] += 1

            if coupon.sold:
                item["sold"] += 1
            else:
                item["available"] += 1

        return list(summary.values())[:limit]

    finally:
        db.close()


def update_coupon_price(coupon_name, selling_price):
    db = SessionLocal()

    try:
        updated = (
            db.query(Coupon)
            .filter(Coupon.coupon_name == coupon_name)
            .update(
                {Coupon.selling_price: selling_price},
                synchronize_session=False
            )
        )

        db.commit()
        return updated

    except Exception:
        db.rollback()
        return 0

    finally:
        db.close()


def delete_coupon_group(coupon_name, only_unsold=True):
    db = SessionLocal()

    try:
        query = db.query(Coupon).filter(Coupon.coupon_name == coupon_name)

        if only_unsold:
            query = query.filter(Coupon.sold == False)

        deleted = query.delete(synchronize_session=False)
        db.commit()
        return deleted

    except Exception:
        db.rollback()
        return 0

    finally:
        db.close()


# =========================
# ORDER FUNCTIONS
# =========================

def create_order(
    user_id,
    coupon_name,
    amount
):
    db = SessionLocal()

    try:

        order_id = (
            "BB" +
            str(random.randint(100000, 999999))
        )

        order = Order(
            order_id=order_id,
            user_id=user_id,
            coupon_name=coupon_name,
            amount=amount,
            payment_status="PENDING",
            delivery_status="NOT_DELIVERED"
        )

        db.add(order)
        db.commit()

        return order_id

    except Exception:
        db.rollback()
        return None

    finally:
        db.close()


def get_total_orders():
    db = SessionLocal()

    try:
        return db.query(Order).count()

    finally:
        db.close()


def get_pending_orders():
    db = SessionLocal()

    try:
        return (
            db.query(Order)
            .filter(
                Order.payment_status == "PENDING"
            )
            .count()
        )

    finally:
        db.close()


def get_completed_orders():
    db = SessionLocal()

    try:
        return (
            db.query(Order)
            .filter(
                Order.payment_status == "SUCCESS"
            )
            .count()
        )

    finally:
        db.close()


def get_failed_orders():
    db = SessionLocal()

    try:
        return (
            db.query(Order)
            .filter(
                Order.payment_status == "FAILED"
            )
            .count()
        )

    finally:
        db.close()


def get_cancelled_orders():
    db = SessionLocal()

    try:
        return (
            db.query(Order)
            .filter(
                Order.payment_status == "CANCELLED"
            )
            .count()
        )

    finally:
        db.close()


# =========================
# REVENUE FUNCTIONS
# =========================

def get_total_revenue():
    db = SessionLocal()

    try:

        orders = (
            db.query(Order)
            .filter(
                Order.payment_status == "SUCCESS"
            )
            .all()
        )

        revenue = 0

        for order in orders:
            revenue += order.amount

        return revenue

    finally:
        db.close()

def get_coupon_stock(coupon_name):
    db = SessionLocal()

    try:
        return (
            db.query(Coupon)
            .filter(
                Coupon.coupon_name == coupon_name,
                Coupon.sold == False
            )
            .count()
        )

    finally:
        db.close()        

def get_user_orders(user_id):
    db = SessionLocal()

    try:
        return (
            db.query(Order)
            .filter(
                Order.user_id == user_id
            )
            .order_by(Order.id.desc())
            .all()
        )

    finally:
        db.close()        

def get_unsold_coupon(coupon_name):
    db = SessionLocal()

    try:

        coupon = (
            db.query(Coupon)
            .filter(
                Coupon.coupon_name == coupon_name,
                Coupon.sold == False
            )
            .first()
        )

        return coupon

    finally:
        db.close()


def mark_coupon_sold(coupon_id):
    db = SessionLocal()

    try:

        coupon = (
            db.query(Coupon)
            .filter(
                Coupon.id == coupon_id
            )
            .first()
        )

        if coupon:

            coupon.sold = True

            db.commit()

            return True

        return False

    except Exception:

        db.rollback()

        return False

    finally:
        db.close()      

def get_total_orders():
    db = SessionLocal()

    try:
        return db.query(Order).count()

    finally:
        db.close()


def get_pending_orders():
    db = SessionLocal()

    try:
        return (
            db.query(Order)
            .filter(Order.payment_status == "PENDING")
            .count()
        )

    finally:
        db.close()


def get_success_orders():
    db = SessionLocal()

    try:
        return (
            db.query(Order)
            .filter(Order.payment_status == "SUCCESS")
            .count()
        )

    finally:
        db.close()          

def get_coupon_price(coupon_name):
    db = SessionLocal()

    try:

        coupon = (
            db.query(Coupon)
            .filter(
                Coupon.coupon_name == coupon_name
            )
            .first()
        )

        if coupon:
            return coupon.selling_price

        return 14

    finally:
        db.close()

def get_order_by_id(order_id):

    db = SessionLocal()

    try:

        return (
            db.query(Order)
            .filter(
                Order.order_id == order_id
            )
            .first()
        )

    finally:
        db.close()


def update_order_status(
    order_id,
    status
):

    db = SessionLocal()

    try:

        order = (
            db.query(Order)
            .filter(
                Order.order_id == order_id
            )
            .first()
        )

        if order:

            order.payment_status = status

            db.commit()

            return True

        return False

    except Exception:

        db.rollback()

        return False

    finally:
        db.close()


def update_delivery_status(
    order_id,
    status
):

    db = SessionLocal()

    try:

        order = (
            db.query(Order)
            .filter(
                Order.order_id == order_id
            )
            .first()
        )

        if order:

            order.delivery_status = status

            db.commit()

            return True

        return False

    except Exception:

        db.rollback()

        return False

    finally:
        db.close()        

def save_payment_session(
    order_id,
    payment_session_id
):

    db = SessionLocal()

    try:

        order = (
            db.query(Order)
            .filter(
                Order.order_id == order_id
            )
            .first()
        )

        if order:

            order.payment_session_id = (
                payment_session_id
            )

            db.commit()

            return True

        return False

    except Exception:

        db.rollback()

        return False

    finally:

        db.close()


def get_payment_session(
    order_id
):

    db = SessionLocal()

    try:

        order = (
            db.query(Order)
            .filter(
                Order.order_id == order_id
            )
            .first()
        )

        if order:
            return order.payment_session_id

        return None

    finally:

        db.close()
