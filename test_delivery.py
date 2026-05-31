from services.coupon_service import (
    deliver_coupon
)

coupon = deliver_coupon(
    "BigBasket Chocolate & Ice Cream"
)

print(coupon)