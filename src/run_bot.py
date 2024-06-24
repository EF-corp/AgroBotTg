import asyncio

from src.handlers import admin, user
from src.bot import bot

from aiogram.fsm.strategy import FSMStrategy
from aiogram import Dispatcher
import logging
import asyncio

logger = logging.getLogger(__name__)


async def starting_bot():
    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s:%(lineno)d #%(levelname)-8s "
               "[%(asctime)s] - %(name)s - %(message)s",
        filename="log_files/main_log.log",
        filemode="a"
    )

    logger.info("Starting bot")

    dp: Dispatcher = Dispatcher(fsm_strategy=FSMStrategy.USER_IN_CHAT)

    dp.include_routers(admin, user)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(starting_bot())

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
