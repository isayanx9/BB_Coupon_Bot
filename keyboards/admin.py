from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def developer_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Add Coupon"),
                KeyboardButton(text="📦 Inventory")
            ],
            [
                KeyboardButton(text="📊 Statistics"),
                KeyboardButton(text="👥 Users")
            ],
            [
                KeyboardButton(text="💰 Payments"),
                KeyboardButton(text="📋 Orders")
            ],
            [
                KeyboardButton(text="📢 Broadcast"),
                KeyboardButton(text="⚙️ Settings")
            ],
            [
                KeyboardButton(text="🏠 Main Menu")
            ],
            [
                KeyboardButton(text="❌ Exit Developer Panel")
            ]
        ],
        resize_keyboard=True
    )