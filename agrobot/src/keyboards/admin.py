from aiogram.types import (ReplyKeyboardMarkup,
                           KeyboardButton,
                           InlineKeyboardMarkup,
                           InlineKeyboardButton)

from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import Config


def kb_rates_admin(rates, page=0, page_size=Config.n_rate_per_page, from_menu=False):
    markup = InlineKeyboardBuilder()
    start = page * page_size
    end = start + page_size

    for rate in rates[start:end]:
        markup.row(InlineKeyboardButton(text=rate["_id"],
                                        callback_data=f"edit_rate_{rate['_id']}"))

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

    markup.row(InlineKeyboardButton(text='➕ Добавить Тариф',
                                    callback_data='add_rate'))
    if from_menu:
        markup.row(InlineKeyboardButton(text='⬅️Назад в меню',
                                        callback_data='menu'))
    return markup


def kb_menu_admin():
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="⚙ Конфигуратор Тарифов",
                             callback_data="to_rates_from_menu")
    )

    builder.row(
        InlineKeyboardButton(text="📊 Статистика",
                             callback_data="stats")
    )
    builder.row(
        InlineKeyboardButton(text="🧠 Добавить знания",
                             callback_data="add_knowledge")
    )
    builder.row(
        InlineKeyboardButton(text="📩 Отправить сообщение всем пользователям",
                             callback_data="notify")
    )
    builder.row(
        InlineKeyboardButton(text="🤝 Партнеры",
                             callback_data="partner")
    )
    builder.row(
        InlineKeyboardButton(text="❓ Помощь",
                             callback_data="help_admin"),
        InlineKeyboardButton(text="🗑️ Новый диалог",
                             callback_data="clear")
    )
    return builder


def get_type_rate():
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Годовой",
                             callback_data="type_годовой"),
        InlineKeyboardButton(text="Месячный",
                             callback_data="type_месячный")
    ]])
    return kb


def get_edit_rate_kb(rate_name, from_menu=False):
    markup = InlineKeyboardBuilder()
    markup.row(InlineKeyboardButton(text='✏ Изменить', callback_data=f'change_rate_{rate_name}'))
    markup.row(InlineKeyboardButton(text='🗑️ Удалить', callback_data=f'delete_rate_{rate_name}'))
    if from_menu:
        markup.row(InlineKeyboardButton(text='⬅️Назад', callback_data='to_rates_from_menu'))
    else:
        markup.row(InlineKeyboardButton(text='⬅️Назад', callback_data='to_rates'))

    return markup


def kb_knowledge_admin():
    markup = InlineKeyboardBuilder()
    markup.row(InlineKeyboardButton(text='🎥 YouTube', callback_data=f'knowledge_youtube'))
    markup.row(InlineKeyboardButton(text='💾 Гугл Диск', callback_data=f'knowledge_gdrive'))
    markup.row(InlineKeyboardButton(text='📁 Файл', callback_data=f'knowledge_file'))

    markup.row(InlineKeyboardButton(text='⬅️Назад', callback_data='menu'))

    return markup


def kb_stats_admin(data: str):
    markup = InlineKeyboardBuilder()
    markup.row(InlineKeyboardButton(text='📈 Графики', callback_data=f'stats_plot_{data}'))
    markup.row(InlineKeyboardButton(text='⬅️Назад', callback_data='menu'))

    return markup



