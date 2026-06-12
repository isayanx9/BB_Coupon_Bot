from aiogram.fsm.state import State, StatesGroup


class CouponUpload(StatesGroup):
    waiting_for_bulk_coupons = State()


class AIAssist(StatesGroup):
    waiting_for_question = State()


class BroadcastState(StatesGroup):
    waiting_for_message = State()


class BanState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_reason = State()


class UnbanState(StatesGroup):
    waiting_for_user_id = State()


class PriceState(StatesGroup):
    waiting_for_coupon_name = State()
    waiting_for_price = State()


class DeleteCouponState(StatesGroup):
    waiting_for_coupon_name = State()


class SettingState(StatesGroup):
    waiting_for_key = State()
    waiting_for_value = State()


class SupportTicketState(StatesGroup):
    waiting_for_message = State()


class TicketReplyState(StatesGroup):
    waiting_for_ticket_id = State()
    waiting_for_reply = State()


class WalletCreditState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_reason = State()


class FlashSaleState(StatesGroup):
    waiting_for_coupon_name = State()
    waiting_for_title = State()
    waiting_for_discount_text = State()
