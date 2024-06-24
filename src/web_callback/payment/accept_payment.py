from src.web_callback.payment.recurrent_tools import create_new_recurrent_payment, \
    get_status_recurrent_payment, \
    create_extend_recurrent_payment, \
    processing_payments
from src.database import DataBase as db
from src.exceptions import PaymentError

from aiogram.types import Message, WebAppInfo, \
    InlineKeyboardMarkup, InlineKeyboardButton


async def accept_new_rec_pay(message: Message,
                             rate_name: str):
    user_id = message.from_user.id

    await db.check_if_user_exists(user_id, raise_exception=True)
    await db.check_if_rate_exists(rate_name, raise_exception=True)

    data_payment = await create_new_recurrent_payment(message=message,
                                                      rate_name=rate_name)

    pay_link = data_payment["payUrl"]

    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="🛒 Оплатить",
        web_app=WebAppInfo(url=pay_link)
    )]])

    await message.answer(text="Вот ссылка на оплату тарифа:",
                         reply_markup=markup)

    result = await processing_payments(data_rec_pay=data_payment,
                                       user_id=user_id,
                                       rate_name=rate_name)

    if not result:
        await db.delete_payment_user(user_id=user_id)
        raise PaymentError

    payment_data = await db.get_payment_data_user(user_id=user_id)

    status_data = await get_status_recurrent_payment(payment_data["reg_pay_id"])
    if status_data["state"] in ["payed", "processed"] and \
            int(status_data["totalAmount"]) == int(payment_data["amount"]):
        await db.accept_rec_payment(user_id=user_id,
                                    rate_name=rate_name)


async def accept_extend_rec_pay(user_id: int):
    rate_name = await db.get_user_attribute(user_id, "rate")

    await db.check_if_user_exists(user_id, raise_exception=True)

    if rate_name == "free":
        return

    await db.check_if_rate_exists(rate_name, raise_exception=True)

    result = await create_extend_recurrent_payment(user_id=user_id,
                                                   rate_name=rate_name)
    result = await processing_payments(data_rec_pay=result,
                                       user_id=user_id,
                                       rate_name=rate_name)
    if not result:
        await db.delete_payment_user(user_id=user_id)
        raise PaymentError

    payment_data = await db.get_payment_data_user(user_id=user_id)

    status_data = await get_status_recurrent_payment(payment_data["reg_pay_id"])
    if status_data["state"] in ["payed", "processed"] and \
            int(status_data["totalAmount"]) == int(payment_data["amount"]):
        await db.accept_rec_payment(user_id=user_id,
                                    rate_name=rate_name)
