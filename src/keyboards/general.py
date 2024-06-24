from aiogram.types import (ReplyKeyboardMarkup,
                           KeyboardButton,
                           InlineKeyboardMarkup,
                           InlineKeyboardButton)

from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import Config


def get_help_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛠️ Тех. поддержка",
                                                                     url=Config.support_url)]])
    return kb


def get_feed_kb(user_id, dialog_id):
    # need smile
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👍",
                                                                     callback_data=f"good_{dialog_id}"),
                                                InlineKeyboardButton(text="👎",
                                                                     callback_data=f"bad_{dialog_id}")]])
    return kb
