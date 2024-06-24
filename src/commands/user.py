from aiogram.types import BotCommandScopeChat, BotCommand
from aiogram import Bot


async def set_user_commands_menu(bot: Bot, user_id: int):
    commands = [
        BotCommand(command="start",
                   description="Начало общения с ботом"),
        BotCommand(command="menu",
                   description="🏠 Основное меню взаимодействия"),
        BotCommand(command="tariffs",
                   description="❤ Подписка"),
        BotCommand(command="balance",
                   description="💰 Баланс"),
        BotCommand(command="stats",
                   description="📊 Статистика"),
        BotCommand(command="help",
                   description="❓ Помощь"),
        BotCommand(command="new",
                   description="🗑️ Начать новый диалог"),
        BotCommand(command="retry",
                   description="🔄 Сгенерировать последний ответ заново"),
        BotCommand(command="cancel",
                   description="⛔ Завершить обработку запроса"),
    ]

    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeChat(chat_id=user_id)
    )
