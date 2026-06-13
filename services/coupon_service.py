from database.crud import (
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
