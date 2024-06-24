from datetime import datetime, timedelta

from aiogram.types import Message, CallbackQuery
from aiogram.methods import SendMessage, EditMessageText

from src.database import DataBase as db
from src.utils import is_previous_message_not_answered_yet
from src.nn import OpenAIHelper

import asyncio


async def register_user(message: Message | CallbackQuery, user_semaphores):
    user_id = message.from_user.id
    if not await db.check_if_user_exists(user_id=user_id):
        await db.add_new_user(user_id=user_id,
                              chat_id=message.chat.id,
                              username=message.from_user.username,
                              first_name=message.from_user.first_name,
                              last_name=message.from_user.last_name)
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore()


async def get_user_balance(user_id):
    user_data = await db.get_user_data(user_id=user_id)
    type_ = {
        "годовой": timedelta(days=365),
        "месячный": timedelta(days=30)
    }
    type_rate_user = await db.get_rate_attribute(rate_name=user_data["rate"],
                                                 key="type")
    balance_data = (
        f"Ваш баланс на {str(datetime.now().date())}:\n"
        f"Количество токенов на балансе: {user_data['n_tokens']}\n"
        f"Количество секунд на распознавание речи: {user_data['n_transcribed_seconds']}\n"
        f"Количество секунд на генерацию речи: {user_data['n_generate_seconds']}\n\n"
        f"Ваш тариф: {'Бесплатный' if user_data['rate'] == 'free' else user_data['rate']}\n"
        f"Последняя оплата: {user_data['last_pay'].date()}\n"
        f"Дата отключения тарифа: {str((user_data['last_pay'].date() + type_[type_rate_user]).date()) if user_data['rate'] != 'free' else ''}"
    )

    return balance_data


if __name__ == "__main__":
    asyncio.run(get_user_balance(user_id=6925528772))
