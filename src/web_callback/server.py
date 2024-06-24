from fastapi import APIRouter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.bot import bot
from src.database import DataBase as db
from src.web_callback.models import PaymentData


router = APIRouter()


@router.get("/")
async def hello():
    return {"hello": "start working"}


@router.post("/notification")
async def main(data: PaymentData):
    if data.state == "PAYED":
        pay_data = await db.get_payments_by_reg(reg_pay_id=data.regPayNum)
        user_id = int(pay_data["_id"])
        if await db.accept_payment(data.regPayNum):
            await bot.send_message(chat_id=user_id,
                                   text="Оплата прошла успешно!\nВаш баланс обнавлён!",
                                   parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="🏠 Меню",
                                                            callback_data="user_menu")
                                   ]]))
