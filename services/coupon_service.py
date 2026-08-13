from database.crud import (
    claim_unsold_coupons,
    get_coupon_stock,
)


def deliver_coupon(coupon_name):
    codes, remaining = claim_unsold_coupons(coupon_name, 1)
    if not codes:
        return None, 0
    return codes[0], remaining


def deliver_coupons(coupon_name, quantity):
    return claim_unsold_coupons(coupon_name, max(1, quantity))
