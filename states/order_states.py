from aiogram.fsm.state import State, StatesGroup


class CouponUpload(StatesGroup):
    waiting_for_bulk_coupons = State()


class AIAssist(StatesGroup):
    waiting_for_question = State()
