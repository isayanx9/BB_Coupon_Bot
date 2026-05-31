from database.crud import (
    get_unsold_coupon,
    mark_coupon_sold
)


def deliver_coupon(coupon_name):

    coupon = get_unsold_coupon(
        coupon_name
    )

    if not coupon:
        return None

    mark_coupon_sold(
        coupon.id
    )

    return coupon.coupon_code