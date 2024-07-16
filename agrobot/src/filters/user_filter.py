from aiogram.types import Message
from aiogram.filters import BaseFilter

from src.database import DataBase as db


class UserCheck(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return not await db.check_if_admin_exists(admin_id=message.from_user.id)
