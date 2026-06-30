from database.crud import (
    claim_unsold_coupons,
    get_coupon_stock,
    get_unsold_coupon,
    mark_coupon_sold
)


def deliver_coupon(coupon_name):

    coupon = get_unsold_coupon(
        coupon_name
    )

    if not coupon:
        return None, 0

    mark_coupon_sold(
        coupon.id
    )

    remaining = get_coupon_stock(coupon_name)

    return coupon.coupon_code, remaining


def deliver_coupons(coupon_name, quantity):
    if quantity <= 1:
        code, remaining = deliver_coupon(coupon_name)
        return ([code] if code else []), remaining

    return claim_unsold_coupons(coupon_name, quantity)
