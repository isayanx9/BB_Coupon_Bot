from database.db import SessionLocal, engine
from database.models import (
    AdminAuditLog,
    BannedUser,
    BotSetting,
    Coupon,
    FlashSale,
    Order,
    Referral,
    StockAlert,
    SupportTicket,
    User,
    WalletTransaction,
)
from sqlalchemy import text

import uuid


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


def delete_bot_setting(key):
    db = SessionLocal()

    try:
        deleted = (
            db.query(BotSetting)
            .filter(BotSetting.key == key)
            .delete(synchronize_session=False)
        )
        db.commit()
        return deleted

    except Exception:
        db.rollback()
        return 0

    finally:
        db.close()


def add_wallet_credit(user_id, amount, reason):
    db = SessionLocal()

    try:
        tx = WalletTransaction(
            user_id=user_id,
            amount=amount,
            reason=reason,
        )
        db.add(tx)
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def get_wallet_balance(user_id):
    db = SessionLocal()

    try:
        transactions = (
            db.query(WalletTransaction)
            .filter(WalletTransaction.user_id == user_id)
            .all()
        )
        return sum(tx.amount for tx in transactions)

    finally:
        db.close()


def get_wallet_transactions(user_id, limit=10):
    db = SessionLocal()

    try:
        return (
            db.query(WalletTransaction)
            .filter(WalletTransaction.user_id == user_id)
            .order_by(WalletTransaction.id.desc())
            .limit(limit)
            .all()
        )

    finally:
        db.close()


def refund_order_wallet_if_needed(order_id, reason="Wallet refund"):
    db = SessionLocal()

    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .first()
        )

        if not order or not order.wallet_used:
            return False

        if order.payment_status == "SUCCESS" or order.delivery_status == "DELIVERED":
            return False

        existing = (
            db.query(WalletTransaction)
            .filter(
                WalletTransaction.user_id == order.user_id,
                WalletTransaction.reason == f"{reason} for {order.order_id}",
            )
            .first()
        )

        if existing:
            return False

        db.add(
            WalletTransaction(
                user_id=order.user_id,
                amount=order.wallet_used,
                reason=f"{reason} for {order.order_id}",
            )
        )
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def reset_platform_data():
    db = SessionLocal()

    try:
        counts = {}

        # If using SQLite, temporarily disable foreign key checks
        is_sqlite = getattr(engine.dialect, "name", "") == "sqlite"
        if is_sqlite:
            try:
                db.execute(text("PRAGMA foreign_keys = OFF"))
            except Exception:
                # Non-fatal: continue without PRAGMA if it fails
                pass

        # Delete all data from all tables (order generally safe)
        counts["admin_audit_logs"] = db.query(AdminAuditLog).delete(synchronize_session=False)
        counts["support_tickets"] = db.query(SupportTicket).delete(synchronize_session=False)
        counts["stock_alerts"] = db.query(StockAlert).delete(synchronize_session=False)
        counts["flash_sales"] = db.query(FlashSale).delete(synchronize_session=False)
        counts["banned_users"] = db.query(BannedUser).delete(synchronize_session=False)
        counts["wallet_transactions"] = db.query(WalletTransaction).delete(synchronize_session=False)
        counts["referrals"] = db.query(Referral).delete(synchronize_session=False)
        counts["orders"] = db.query(Order).delete(synchronize_session=False)
        counts["coupons"] = db.query(Coupon).delete(synchronize_session=False)
        counts["users"] = db.query(User).delete(synchronize_session=False)

        db.commit()

        # Re-enable foreign keys for SQLite if we turned them off
        if is_sqlite:
            try:
                db.execute(text("PRAGMA foreign_keys = ON"))
            except Exception:
                pass

        return counts

    except Exception as e:
        db.rollback()
        # Return structured error so callers can display more info to admin
        err = str(e)
        print(f"Reset error: {err}")
        return {"error": err}

    finally:
        db.close()


def create_referral(referrer_id, referred_id, reward_amount=0):
    if str(referrer_id) == str(referred_id):
        return False

    db = SessionLocal()

    try:
        existing = (
            db.query(Referral)
            .filter(Referral.referred_id == referred_id)
            .first()
        )

        if existing:
            return False

        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            reward_amount=reward_amount,
        )
        db.add(referral)
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def reward_referral_if_needed(referred_id, default_reward=1):
    db = SessionLocal()

    try:
        referral = (
            db.query(Referral)
            .filter(
                Referral.referred_id == referred_id,
                Referral.rewarded == False
            )
            .first()
        )

        if not referral:
            return False

        reward = referral.reward_amount or default_reward
        referral.reward_amount = reward
        referral.rewarded = True
        db.add(
            WalletTransaction(
                user_id=referral.referrer_id,
                amount=reward,
                reason=f"Referral reward for {referred_id}",
            )
        )
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def get_referral_count(user_id):
    db = SessionLocal()

    try:
        return (
            db.query(Referral)
            .filter(Referral.referrer_id == user_id)
            .count()
        )

    finally:
        db.close()


def create_support_ticket(user_id, subject, message):
    db = SessionLocal()

    try:
        ticket = SupportTicket(
            user_id=user_id,
            subject=subject[:255],
            messages=f"USER: {message}",
        )
        db.add(ticket)
        db.commit()
        return ticket.id

    except Exception:
        db.rollback()
        return None

    finally:
        db.close()


def add_ticket_reply(ticket_id, sender, message):
    db = SessionLocal()

    try:
        ticket = (
            db.query(SupportTicket)
            .filter(SupportTicket.id == ticket_id)
            .first()
        )

        if not ticket:
            return False

        ticket.messages = (
            f"{ticket.messages}\n\n{sender.upper()}: {message}"
        )[:4000]
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def close_ticket(ticket_id):
    db = SessionLocal()

    try:
        ticket = (
            db.query(SupportTicket)
            .filter(SupportTicket.id == ticket_id)
            .first()
        )

        if not ticket:
            return False

        ticket.status = "CLOSED"
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def get_open_tickets(limit=10):
    db = SessionLocal()

    try:
        return (
            db.query(SupportTicket)
            .filter(SupportTicket.status == "OPEN")
            .order_by(SupportTicket.id.desc())
            .limit(limit)
            .all()
        )

    finally:
        db.close()


def get_ticket_by_id(ticket_id):
    db = SessionLocal()

    try:
        return (
            db.query(SupportTicket)
            .filter(SupportTicket.id == ticket_id)
            .first()
        )

    finally:
        db.close()


def subscribe_stock_alert(user_id, coupon_name="ALL"):
    db = SessionLocal()

    try:
        alert = (
            db.query(StockAlert)
            .filter(
                StockAlert.user_id == user_id,
                StockAlert.coupon_name == coupon_name,
                StockAlert.active == True
            )
            .first()
        )

        if alert:
            return True

        db.add(
            StockAlert(
                user_id=user_id,
                coupon_name=coupon_name,
            )
        )
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def get_stock_alert_user_ids(coupon_name=None):
    db = SessionLocal()

    try:
        query = db.query(StockAlert).filter(StockAlert.active == True)

        if coupon_name:
            query = query.filter(
                (StockAlert.coupon_name == coupon_name)
                | (StockAlert.coupon_name == "ALL")
            )

        return list({alert.user_id for alert in query.all()})

    finally:
        db.close()


def audit_admin_action(admin_id, action, details=""):
    db = SessionLocal()

    try:
        db.add(
            AdminAuditLog(
                admin_id=admin_id,
                action=action,
                details=details[:1000],
            )
        )
        db.commit()
        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()


def get_recent_audit_logs(limit=10):
    db = SessionLocal()

    try:
        return (
            db.query(AdminAuditLog)
            .order_by(AdminAuditLog.id.desc())
            .limit(limit)
            .all()
        )

    finally:
        db.close()


def create_flash_sale(coupon_name, title, discount_text, expires_at=None):
    db = SessionLocal()

    try:
        sale = FlashSale(
            coupon_name=coupon_name,
            title=title,
            discount_text=discount_text,
            expires_at=expires_at,
        )
        db.add(sale)
        db.commit()
        return sale.id

    except Exception:
        db.rollback()
        return None

    finally:
        db.close()


def get_active_flash_sales(limit=5):
    db = SessionLocal()

    try:
        return (
            db.query(FlashSale)
            .filter(FlashSale.active == True)
            .order_by(FlashSale.id.desc())
            .limit(limit)
            .all()
        )

    finally:
        db.close()


def get_analytics_snapshot():
    db = SessionLocal()

    try:
        total_orders = db.query(Order).count()
        success_orders = (
            db.query(Order)
            .filter(Order.payment_status == "SUCCESS")
            .count()
        )
        pending_orders = (
            db.query(Order)
            .filter(Order.payment_status == "PENDING")
            .count()
        )
        total_users = db.query(User).count()
        total_coupons = db.query(Coupon).count()
        available_coupons = (
            db.query(Coupon)
            .filter(Coupon.sold == False)
            .count()
        )
        revenue = sum(
            order.amount
            for order in db.query(Order)
            .filter(Order.payment_status == "SUCCESS")
            .all()
        )

        conversion = (
            round((success_orders / total_orders) * 100, 2)
            if total_orders
            else 0
        )

        return {
            "total_orders": total_orders,
            "success_orders": success_orders,
            "pending_orders": pending_orders,
            "total_users": total_users,
            "total_coupons": total_coupons,
            "available_coupons": available_coupons,
            "revenue": revenue,
            "conversion": conversion,
        }

    finally:
        db.close()


def export_backup_rows():
    db = SessionLocal()

    try:
        coupons = db.query(Coupon).order_by(Coupon.id.asc()).all()
        orders = db.query(Order).order_by(Order.id.asc()).all()

        return {
            "coupons": [
                [
                    c.id,
                    c.coupon_name,
                    c.coupon_code,
                    c.discount_value,
                    c.minimum_order,
                    c.selling_price,
                    c.sold,
                ]
                for c in coupons
            ],
            "orders": [
                [
                    o.order_id,
                    o.user_id,
                    o.coupon_name,
                    o.amount,
                    o.payment_status,
                    o.delivery_status,
                    o.created_at,
                ]
                for o in orders
            ],
        }

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
    amount,
    use_wallet=True
):
    db = SessionLocal()

    try:

        wallet_used = 0
        payable_amount = amount

        if use_wallet:
            balance = get_wallet_balance(user_id)
            wallet_used = min(balance, amount)
            payable_amount = amount - wallet_used

            if wallet_used > 0:
                db.add(
                    WalletTransaction(
                        user_id=user_id,
                        amount=-wallet_used,
                        reason="Wallet used for coupon purchase",
                    )
                )

        order_id = "BB" + uuid.uuid4().hex[:12].upper()

        order = Order(
            order_id=order_id,
            user_id=user_id,
            coupon_name=coupon_name,
            amount=amount,
            wallet_used=wallet_used,
            payable_amount=payable_amount,
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
