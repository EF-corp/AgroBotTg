from aiogram.types import (ReplyKeyboardMarkup,
                           KeyboardButton,
                           InlineKeyboardMarkup,
                           InlineKeyboardButton)

from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import Config


def get_user_menu_kb():
    menu = InlineKeyboardBuilder()
    menu.row(
        InlineKeyboardButton(text="❤ Подписка",
                             callback_data="sub_user")
    )
    menu.row(
        InlineKeyboardButton(text="💰 Баланс",
                             callback_data="user_balance_menu")
    )
    menu.row(
        InlineKeyboardButton(text="📊 Статистика",
                             callback_data="user_stats_menu")
    )
    menu.row(
        InlineKeyboardButton(text="🗑️ Новый диалог",
                             callback_data="clear")
    )
    menu.row(
        InlineKeyboardButton(text="❓ Помощь",
                             callback_data="user_help"),
        InlineKeyboardButton(text="📄 Оферта",
                             callback_data="doc_ofert"),
        width=2
    )

    return menu


def get_user_sub_menu(rates, page=0, page_size=Config.n_rate_per_page, from_menu=False):
    markup = InlineKeyboardBuilder()
    start = page * page_size
    end = start + page_size

    for rate in rates[start:end]:
        markup.row(InlineKeyboardButton(text=rate["_id"],
                                        callback_data=f"buy_rate_{rate['_id']}"))

    if len(rates) > page_size:
        if page == 0:
            markup.row(
                InlineKeyboardButton(text="➡️",
                                     callback_data=f"next_rate_{page}")
            )
        elif ((page + 1) * page_size) >= len(rates):
            markup.row(
                InlineKeyboardButton(text="⬅️",
                                     callback_data=f"prev_rate_{page}")
            )
        else:
            markup.row(
                InlineKeyboardButton(text="⬅️",
                                     callback_data=f"prev_rate_{page}"),
                InlineKeyboardButton(text="➡️",
                                     callback_data=f"next_rate_{page}"),
                width=2)
    if from_menu:
        markup.row(InlineKeyboardButton(text='⬅️Назад в меню',
                                        callback_data='user_menu'))
    return markup


def get_adds_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🛒 Купить подписку",
                             callback_data="sub_user")
    ]])

    return kb


def get_document_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📄 Оферта",
                             callback_data="doc_ofert")
    ]])

    return kb


def get_back_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️В меню",
                             callback_data="user_menu")
    ]])

    return kb


def get_user_stats_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="💰 Баланс",
                             callback_data="user_balance_menu")
    )
    kb.row(
        InlineKeyboardButton(text="⬅️В меню",
                             callback_data="user_menu")
    )
    return kb


def get_user_balance_kb(user_rate):
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📊 Статистика",
                             callback_data="user_stats_menu")
    )
    kb.row(
        InlineKeyboardButton(text="ℹ Информация о тарифе",
                             callback_data=f"buy_rate_{user_rate}")
    )
    kb.row(
        InlineKeyboardButton(text="⬅️В меню",
                             callback_data="user_menu")
    )
    return kb


def get_user_rate_kb(rate_name, has_premium: bool = False):
    kb = InlineKeyboardBuilder()
    if has_premium:
        kb.row(
            InlineKeyboardButton(text="❌ Отменить",
                                 callback_data="cancel_rate"),
        )
    else:
        kb.row(
            InlineKeyboardButton(text="🛒 Купить",
                                 callback_data=f"buying_rate_{rate_name}")
        )
    kb.row(
        InlineKeyboardButton(text="⬅️Назад",
                             callback_data="sub_user")
    )
    return kb
