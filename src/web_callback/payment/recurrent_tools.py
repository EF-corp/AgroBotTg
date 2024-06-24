import base64
import httpx
import json

from src.config import Config
from src.exceptions import RegistrationError, RecurrentPaymentCheckError, \
    ConfirmPaymentError, PaymentCreationError
from src.database import DataBase as db

import asyncio
from aiogram.types import Message

import datetime


async def make_credential(login: str,
                          password: str):
    credential = f'{login}:{password}'
    encoded_credential = base64.b64encode(credential.encode("ascii"))

    return f'Basic {encoded_credential.decode("ascii")}'


async def registr_user(url: str = "https://demo-api2.ckassa.ru/api-shop/user/registration",
                       phone_number: str | None = None,
                       name: str | None = None,
                       surname: str | None = None,
                       middlename: str | None = None):
    if phone_number is None:
        raise RegistrationError

    headers = {
        'Content-Type': 'application/json',
        'Authorization': await make_credential(login=Config.shop_token,
                                               password=Config.sec_key)
    }

    payload = json.dumps({
        'login': phone_number,
        'name': name,
        'surName': surname,
        'middleName': middlename,
    })

    async with httpx.AsyncClient() as client:

        reg_response = await client.request(method="POST",
                                            url=url,
                                            headers=headers,
                                            data=payload)

        if reg_response.status_code == 200:
            return reg_response.json()

        else:
            raise RegistrationError


async def get_active_user_cards(user_token: str,
                                url: str = "https://api2.ckassa.ru/api-shop/ver3/get/cards"):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': await make_credential(login=Config.shop_token,
                                               password=Config.sec_key)
    }

    payload = json.dumps({
        "userToken": user_token,
    })

    async with httpx.AsyncClient() as client:

        reg_response = await client.request(method="POST",
                                            url=url,
                                            headers=headers,
                                            data=payload)

        if reg_response.status_code == 200:
            cards_data = reg_response.json()
            active_cards_tokens = [card["cardToken"] for card in cards_data["cards"] if card["state"] == "active"]
            return active_cards_tokens

        else:
            raise RecurrentPaymentCheckError


async def get_status_recurrent_payment(url: str = "https://api2.ckassa.ru/api-shop/rs/shop/check/payment/state",
                                       reg_pay_num: int | str = None):
    if reg_pay_num is None:
        raise RecurrentPaymentCheckError

    headers = {
        'Content-Type': 'application/json',
        'Authorization': await make_credential(login=Config.shop_token,
                                               password=Config.sec_key)
    }

    payload = json.dumps({
        "regPayNum": reg_pay_num,
    })

    async with httpx.AsyncClient() as client:

        reg_response = await client.request(method="POST",
                                            url=url,
                                            headers=headers,
                                            data=payload)

        if reg_response.status_code == 200:
            return reg_response.json()

        else:
            raise RecurrentPaymentCheckError


async def confirm_payment(url: str = "https://api2.ckassa.ru/api-shop/provision-services/confirm",
                          reg_pay_num: int | str = None,
                          order_id: int | str = None):
    if reg_pay_num is None or order_id is None:
        raise ConfirmPaymentError

    headers = {
        'Content-Type': 'application/json',
        'Authorization': await make_credential(login=Config.shop_token,
                                               password=Config.sec_key)
    }
    payload = json.dumps({
        "regPayNum": reg_pay_num,
        "orderId": order_id
    })

    async with httpx.AsyncClient() as client:

        reg_response = await client.request(method="POST",
                                            url=url,
                                            headers=headers,
                                            data=payload)

        if reg_response.status_code == 200:
            return reg_response.json()

        else:
            raise ConfirmPaymentError


async def create_new_recurrent_payment(message: Message,
                                       rate_name: str,
                                       url: str = "https://api2.ckassa.ru/api-shop/do/payment", ):
    user_id = message.from_user.id
    user_token = await db.get_user_attribute(user_id, "userToken")
    user_phone = await db.get_user_attribute(user_id, "phone")

    if user_token is None and user_phone is None:
        raise PaymentCreationError

    if user_token is None:
        callback_api = await registr_user(phone_number=user_phone,
                                          name=message.from_user.first_name,
                                          surname=message.from_user.last_name)
        user_token = callback_api["userToken"]

    rate_data = await db.get_rate_data(rate_name=rate_name)

    amount = rate_data["price"] * 100

    # available_cards = await get_active_user_cards(user_token=user_token)
    # need_reg = True

    headers = {
        'Content-Type': 'application/json',
        'Authorization': await make_credential(login=Config.shop_token,
                                               password=Config.sec_key)
    }

    payload = json.dumps({
        "serviceCode": Config.service_code,
        "userToken": user_token,
        "clientType": "mobile",
        "amount": amount,
        "comission": "0",
        "payType": "card",
        "needRegCard": True,
        "orderNote": f"Оплата тарифа {rate_name}",
        "successUrl": Config.main_bot_url,
        "failUrl": Config.main_bot_url,
        "cbUrl": Config.notification_url,
        "properties": [

        ]
    })
    async with httpx.AsyncClient() as client:

        reg_response = await client.request(method="POST",
                                            url=url,
                                            headers=headers,
                                            data=payload)

        if reg_response.status_code == 200:
            data_rec_pay = reg_response.json()
            return data_rec_pay

        else:
            raise ConfirmPaymentError


async def create_extend_recurrent_payment(user_id: int,
                                          rate_name: str,
                                          url: str = "https://api2.ckassa.ru/api-shop/do/payment"):
    user_token = await db.get_user_attribute(user_id, "userToken")
    user_phone = await db.get_user_attribute(user_id, "phone")

    if user_token is None and user_phone is None:
        raise PaymentCreationError

    if user_token is None:
        callback_api = await registr_user(phone_number=user_phone)
        user_token = callback_api["userToken"]

    rate_data = await db.get_rate_data(rate_name=rate_name)

    amount = rate_data["price"] * 100

    available_cards = await get_active_user_cards(user_token=user_token)

    if not available_cards:
        return False

    headers = {
        'Content-Type': 'application/json',
        'Authorization': await make_credential(login=Config.shop_token,
                                               password=Config.sec_key)
    }

    payload = json.dumps({
        "serviceCode": Config.service_code,
        "userToken": user_token,
        "cardToken": available_cards[-1],
        "clientType": "mobile",
        "amount": amount,
        "comission": "0",
        "payType": "card",
        "needRegCard": False,
        "orderNote": f"Оплата тарифа {rate_name}",
        "successUrl": Config.main_bot_url,
        "failUrl": Config.main_bot_url,
        "cbUrl": Config.notification_url,
        "properties": [

        ]
    })

    async with httpx.AsyncClient() as client:

        reg_response = await client.request(method="POST",
                                            url=url,
                                            headers=headers,
                                            data=payload)

        if reg_response.status_code == 200:
            data_rec_pay = reg_response.json()
            return data_rec_pay
        else:
            raise ConfirmPaymentError


async def processing_payments(data_rec_pay: dict,
                              user_id: int,
                              rate_name: str):

    reg_pay_num = data_rec_pay["regPayNum"]
    status_data = await get_status_recurrent_payment(reg_pay_num=reg_pay_num)

    await db.add_new_payment(user_id=int(user_id),
                             amount=int(status_data["totalAmount"]),
                             reg_pay_num=reg_pay_num,
                             rate_id=rate_name)

    start_time = datetime.datetime.now()

    while status_data["state"] not in ["payed", "holded", "processed", "error"]:
        status_data = await get_status_recurrent_payment(reg_pay_num=reg_pay_num)
        await asyncio.sleep(0.5)

    if status_data["state"] in ["payed", "processed"]:
        return True

    elif status_data["state"] == "holded":

        unhold_data = await confirm_payment(reg_pay_num=reg_pay_num,
                                            order_id=...)
        if unhold_data["resultState"] == "success":
            return True
        else:
            return False
    else:
        return False

if __name__ == "__main__":
    data = asyncio.run(registr_user(phone_number="79999999999"))
    print(data)
