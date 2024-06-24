from aiogram.types import BotCommandScopeChat, BotCommand
from aiogram import Bot


async def set_admin_commands_menu(bot: Bot, user_id: int):
    commands = [
        BotCommand(command="start",
                   description="Начало общения с ботом"),
        BotCommand(command="menu",
                   description="🏠 Основное меню взаимодействия"),
        BotCommand(command="tariffs",
                   description="⚙ Конфигуратор тарифов"),
        BotCommand(command="stats",
                   description="📊 Статистика"),
        BotCommand(command="knowledge",
                   description="🧠 Добавить знания"),
        BotCommand(command="notify",
                   description="📩 Отправить уведомление всем пользователям"),
        BotCommand(command="partner",
                   description="🤝 Партнеры"),
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

