from database.db import SessionLocal
from database.models import Coupon, Order

import random


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

