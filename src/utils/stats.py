from src.database import DataBase as db
from src.config import Config
import matplotlib
matplotlib.use("AGG")
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
import os
import asyncio
import aiofiles
import aiofiles.os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
import seaborn as sns


class Statistics:
    def __init__(self):
        self.executor = ThreadPoolExecutor()

    async def __call__(self, user_id: int,
                       *args, **kwargs):

        if await db.check_if_admin_exists(user_id):
            out_path = f"../stats/plots/{str(datetime.now().date())}"
            await aiofiles.os.makedirs(out_path, exist_ok=True)
            users_data = await db.get_all_users_data()
            data_stats = await self.get_stats_for_admin(users_data=users_data,
                                                        out_path=out_path)
            return data_stats

        user_data = await db.get_user_data(user_id=user_id)

        return await self.get_user_stats(user_data=user_data)

    async def get_stats_for_admin(self, users_data, out_path: str):
        data = {
            "user_id": [],
            "rate": [],
            "n_used_tokens": [],
            "n_transcribed_seconds": [],
            "n_generate_seconds": [],
            "n_used_tokens_all": [],
            "n_transcribed_seconds_all": [],
            "n_generate_seconds_all": [],
        }

        data_point = out_path.split('/')[-1]

        for user in users_data:
            data["user_id"].append(user["_id"])
            data["rate"].append(user["rate"])
            data["n_used_tokens"].append(user["current_spend"]["month"]["n_used_tokens"])
            data["n_transcribed_seconds"].append(user["current_spend"]["month"]["n_transcribed_seconds"])
            data["n_generate_seconds"].append(user["current_spend"]["month"]["n_generate_seconds"])
            data["n_used_tokens_all"].append(user["current_spend"]["all"]["n_used_tokens"])
            data["n_transcribed_seconds_all"].append(user["current_spend"]["all"]["n_transcribed_seconds"])
            data["n_generate_seconds_all"].append(user["current_spend"]["all"]["n_generate_seconds"])

        df = pd.DataFrame(data)
        sns.set_theme(style="whitegrid")

        async def save_plot(fig, filename):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, fig.savefig, filename)
            plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 6))
        sns.barplot(x="user_id", y="n_used_tokens", data=df, palette="Blues_d", ax=ax)
        ax.set(xlabel='ID Пользователя', ylabel='Использованные Токены (Этот Месяц)',
               title='Ежемесячное Использование Токенов Пользователями')
        plt.xticks(rotation=45)
        plt.tight_layout()
        token_usage_path = os.path.join(out_path, 'token_usage.png')
        await save_plot(fig, token_usage_path)

        fig, ax = plt.subplots(figsize=(12, 6))
        sns.barplot(x="user_id", y="n_transcribed_seconds", data=df, palette="Greens_d", ax=ax)
        ax.set(xlabel='ID Пользователя', ylabel='Секунды на Расшифровку (Этот Месяц)',
               title='Ежемесячное Использование Секунд на Расшифровку Пользователями')
        plt.xticks(rotation=45)
        plt.tight_layout()
        transcribed_seconds_path = os.path.join(out_path, 'transcribed_seconds_usage.png')
        await save_plot(fig, transcribed_seconds_path)

        fig, ax = plt.subplots(figsize=(12, 6))
        sns.barplot(x="user_id", y="n_generate_seconds", data=df, palette="Reds_d", ax=ax)
        ax.set(xlabel='ID Пользователя', ylabel='Секунды на Генерацию (Этот Месяц)',
               title='Ежемесячное Использование Секунд на Генерацию Пользователями')
        plt.xticks(rotation=45)
        plt.tight_layout()
        generate_seconds_path = os.path.join(out_path, 'generate_seconds_usage.png')
        await save_plot(fig, generate_seconds_path)

        fig, ax = plt.subplots(figsize=(12, 6))
        rate_counts = df["rate"].value_counts()
        sns.barplot(x=rate_counts.index, y=rate_counts.values, palette="Purples_d", ax=ax)
        ax.set(xlabel='Тип Подписки', ylabel='Количество Пользователей',
               title='Количество Пользователей по Типу Подписки')
        plt.xticks(rotation=0)
        plt.tight_layout()
        subscription_rate_path = os.path.join(out_path, 'subscription_rate.png')
        await save_plot(fig, subscription_rate_path)

        total_users = len(users_data)
        free_users = len([user for user in users_data if user["rate"] == "free"])
        premium_users = len(users_data) - free_users

        total_tokens_used = sum(data["n_used_tokens"])
        total_transcribed_seconds = sum(data["n_transcribed_seconds"])
        total_generate_seconds = sum(data["n_generate_seconds"])

        total_tokens_used_all = sum(data["n_used_tokens_all"])
        total_transcribed_seconds_all = sum(data["n_transcribed_seconds_all"])
        total_generate_seconds_all = sum(data["n_generate_seconds_all"])

        total_cost_tokens = total_tokens_used * Config.TOKEN_COST
        total_cost_transcribe = total_transcribed_seconds * Config.TRANSCRIBE_SECOND_COST
        total_cost_generate = total_generate_seconds * Config.GENERATE_SECOND_COST

        total_cost_tokens_all = total_tokens_used_all * Config.TOKEN_COST
        total_cost_transcribe_all = total_transcribed_seconds_all * Config.TRANSCRIBE_SECOND_COST
        total_cost_generate_all = total_generate_seconds_all * Config.GENERATE_SECOND_COST

        total_cost = total_cost_tokens + total_cost_transcribe + total_cost_transcribe
        total_cost_all = total_cost_tokens_all + total_cost_transcribe_all + total_cost_transcribe_all

        text_stats = (
            f"<b>📊 Общая статистика использования сервиса:</b>\n\n"
            f"<b>👥 Всего пользователей:</b> <code>{total_users}</code>\n"
            f"<b>🆓 Пользователей с бесплатной подпиской:</b> <code>{free_users}</code>\n"
            f"<b>💎 Пользователей с премиум подпиской:</b> <code>{premium_users}</code>\n\n"

            f"<b>💬 Общее количество использованных токенов за месяц:</b> <code>{total_tokens_used}</code>\n"
            f"<b>💰 Затраты на токены в месяц:</b> <code>${total_cost_tokens:.2f}</code>\n"
            f"<b>💬 Общее количество использованных токенов за все время:</b> <code>{total_tokens_used_all}</code>\n"
            f"<b>💰 Затраты на токены за все время:</b> <code>${total_cost_tokens_all:.2f}</code>\n\n"

            f"<b>🎙 Общее количество секунд на расшифровку за месяц:</b> <code>{total_transcribed_seconds:.2f}</code>\n"
            f"<b>💰 Затраты на расшифровку в месяц:</b> <code>${total_cost_transcribe:.2f}</code>\n"
            f"<b>🎙 Общее количество секунд на расшифровку за все время:</b> <code>{total_transcribed_seconds_all:.2f}</code>\n"
            f"<b>💰 Затраты на расшифровку за все время:</b> <code>${total_cost_transcribe_all:.2f}</code>\n\n"

            f"<b>🗣 Общее количество секунд на генерацию за месяц:</b> <code>{total_generate_seconds:.2f}</code>\n"
            f"<b>💰 Затраты на генерацию в месяц:</b> <code>${total_cost_generate:.2f}</code>\n"
            f"<b>🗣 Общее количество секунд на генерацию за все время:</b> <code>{total_generate_seconds_all:.2f}</code>\n"
            f"<b>💰 Затраты на генерацию за все время:</b> <code>${total_cost_generate_all:.2f}</code>\n\n"

            f"<b>💰 Общие затраты за месяц:</b> <code>${total_cost:.2f}</code>\n"
            f"<b>💰 Общие затраты за все время:</b> <code>${total_cost_all:.2f}</code>"
        )

        return {
            "token_usage_path": token_usage_path,
            "transcribed_seconds_path": transcribed_seconds_path,
            "generate_seconds_path": generate_seconds_path,
            "subscription_rate_path": subscription_rate_path,
            "text_stats": text_stats,
            "data": data_point
        }

    @staticmethod
    async def get_user_stats(user_data) -> str:
        data_stats = (
            f"📊 <b>Статистика пользователя</b> <code>{user_data['username']}</code>:\n\n"
            f"👤 <b>ID Пользователя:</b> <code>{user_data['_id']}</code>\n"
            f"📅 <b>Дата первого взаимодействия:</b> <code>{user_data['first_seen']}</code>\n"
            f"⏳ <b>Дата последнего взаимодействия:</b> <code>{user_data['last_interaction']}</code>\n\n"
            f"🤖 <b>Текущая модель:</b> <code>{user_data['current_model']}</code>\n"
            f"💬 <b>Использовано токенов (входящих):</b> <code>{user_data['n_used_tokens']['n_input_tokens']}</code>\n"
            f"💬 <b>Использовано токенов (исходящих):</b> <code>{user_data['n_used_tokens']['n_output_tokens']}</code>\n\n"
            f"🎙 <b>Количество секунд на расшифровку:</b> <code>{user_data['n_transcribed_seconds']}</code>\n"
            f"🗣 <b>Количество секунд на генерацию:</b> <code>{user_data['n_generate_seconds']}</code>\n"
            f"💰 <b>Текущая подписка:</b> <code>{user_data['rate']}</code>\n"
        )
        return data_stats
