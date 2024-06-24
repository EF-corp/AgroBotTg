from aiogram.types import Message, CallbackQuery

from src.database import DataBase as db
from src.utils import is_previous_message_not_answered_yet
from src.nn import OpenAIHelper
from src.keyboards import kb_rates_admin

import asyncio
import io
from typing import Dict
from datetime import datetime


async def show_rates_admin(message: Message, rates, page, text, edit_id=None, from_menu=False):
    user_id = message.from_user.id
    if edit_id is None:
        await message.bot.send_message(chat_id=user_id,
                                       text=text,
                                       parse_mode="HTML",
                                       reply_markup=kb_rates_admin(rates, page, from_menu).as_markup())
    else:
        await message.bot.edit_message_text(chat_id=message.chat.id,
                                            message_id=edit_id,
                                            text=text,
                                            parse_mode="HTML",
                                            reply_markup=kb_rates_admin(rates, page, from_menu).as_markup())


async def register_admin_in_db_as_user(message: Message | CallbackQuery, admin_semaphores):
    admin_id = message.from_user.id
    if not await db.check_if_user_exists(user_id=admin_id):
        await db.add_new_user(user_id=admin_id,
                              chat_id=message.chat.id,
                              username=message.from_user.username,
                              first_name=message.from_user.first_name,
                              last_name=message.from_user.last_name,
                              is_admin=True)
    if admin_id not in admin_semaphores:
        admin_semaphores[admin_id] = asyncio.Semaphore(2)
