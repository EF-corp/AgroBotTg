import motor.motor_asyncio as amotor
from typing import Optional, Any, List
import uuid
from datetime import datetime
from src.config import Config
from src.exceptions import *
import asyncio
import httpx
import json
import base64

# from src.web_callback.payment.accept_payment import create_extend_recurrent_payment

MAX_INT = 2 ** 31 - 1
MAX_FLOAT = float(MAX_INT)


class Database:
    def __init__(self, name: str = Config.db_name):
        self.client = amotor.AsyncIOMotorClient(Config.mongodb_url)
        self.db = self.client[name]

        self.user_collection = self.db["user"]
        self.dialog_collection = self.db["dialog"]
        self.promo_collection = self.db["promo"]
        self.rate_collection = self.db["rate"]
        self.admin_collection = self.db["admin"]
        self.vs_collection = self.db["vs"]
        self.partner_collection = self.db["partner"]
        self.payments_collection = self.db["payments"]
        # self.rec_payment_collection = self.db["recPayments"]

    async def add_admins_from_config(self):
        admins = Config.admins_ids
        for admin in admins:
            template = {
                "_id": admin
            }

            await self.admin_collection.insert_one(template)

    async def check_if_user_exists(self, user_id: int, raise_exception: bool = False):
        count = await self.user_collection.count_documents({"_id": user_id})
        if count > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist!")
            else:
                return False

    async def check_if_admin_exists(self, admin_id: int, raise_exception: bool = False):
        count = await self.admin_collection.count_documents({"_id": admin_id})
        if count > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Admin {admin_id} does not exist!")
            else:
                return False

    async def check_if_rate_exists(self, name, raise_exception: bool = False):
        count = await self.rate_collection.count_documents({"_id": name})
        if count > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Rate {name} does not exist!")
            else:
                return False

    async def check_if_promo_exists(self, promo_id, raise_exception: bool = False):
        count = await self.promo_collection.count_documents({"_id": promo_id})
        if count > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Rate {promo_id} does not exist!")
            else:
                return False

    async def check_if_vs_exists(self, vs_id, raise_exception: bool = False):
        count = await self.vs_collection.count_documents({"_id": vs_id})
        if count > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Vector store {vs_id} does not exist!")
            else:
                return False

    async def check_if_partner_exists(self, partner_id, raise_exception: bool = False):
        count = await self.partner_collection.count_documents({"_id": partner_id})
        if count > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Vector store {partner_id} does not exist!")
            else:
                return False

    async def check_if_payments_exists(self, reg_pay_id, raise_exception: bool = False):
        count = await self.payments_collection.count_documents({"reg_pay_id": reg_pay_id})
        if count > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Payment {reg_pay_id} does not exist!")
            else:
                return False

    async def check_if_payments_exists_user(self, user_id, raise_exception: bool = False):
        count = await self.payments_collection.count_documents({"_id": user_id})
        if count > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Payment user {user_id} does not exist!")
            else:
                return False

    @staticmethod
    def check_if_have_tokens_for_answer(n_tokens_available, n_input_tokens, n_output_tokens, raise_exception=True):
        if n_tokens_available - (n_input_tokens + n_output_tokens) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Нужно больше токенов!")
            else:
                return False

    async def check_payment(self, user_id, raise_exception: bool = False):

        await self.check_if_user_exists(user_id, raise_exception=True)

        rate = await self.get_user_attribute(user_id, "rate")
        await self.check_if_rate_exists(rate, raise_exception=True)

        rate_dict = await self.rate_collection.find_one({"_id": rate})
        type_ = rate_dict["type"]

        if (type_ == "monthly" and (datetime.now() - await self.get_user_attribute(user_id, "last_pay")).days <= 30) \
                or (type_ == "yearly" and (
                datetime.now() - await self.get_user_attribute(user_id, "last_pay")).days <= 365):
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} don't pay!")
            else:
                return False

    async def check_if_need_update(self, user_id, raise_exception: bool = False):
        await self.check_if_user_exists(user_id, raise_exception=True)

        rate = await self.get_user_attribute(user_id, "rate")
        await self.check_if_rate_exists(rate, raise_exception=True)

        rate_dict = await self.rate_collection.find_one({"_id": rate})
        type_ = rate_dict["type"]

        if (type_ == "monthly" and (datetime.now() - await self.get_user_attribute(user_id, "last_pay")).days <= 30) \
                or (type_ == "yearly" and (
                datetime.now() - await self.get_user_attribute(user_id, "last_pay")).days <= 365):
            return False
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} don't pay!")
            else:
                return True

    async def add_new_payment(self,
                              user_id: int,
                              amount: int,
                              reg_pay_num: int,
                              rate_id: str):

        payment_dict = {
            "_id": user_id,
            "reg_pay_id": reg_pay_num,  # ?
            "rate_id": rate_id,
            "amount": amount
        }

        await self.payments_collection.insert_one(payment_dict)

    async def add_new_user(
            self,
            user_id: int,
            chat_id: int,
            username: str = "",
            first_name: str = "",
            last_name: str = "",
            is_admin: bool = False
    ):
        user_dict = {
            "_id": user_id,
            "chat_id": chat_id,

            "username": username,
            "first_name": first_name,
            "last_name": last_name,

            "phone": None,
            "userToken": None,

            "last_interaction": datetime.now(),
            "first_seen": datetime.now(),

            "current_dialog_id": None,
            "current_model": "gpt-4o",  # Config.available_free_text_models,

            "n_tokens": 15000 if not is_admin else MAX_INT,
            "n_used_tokens": {
                "n_input_tokens": 0,
                "n_output_tokens": 0
            },

            "rate": "free",
            "last_pay": datetime.now(),
            "last_update": datetime.now(),

            # "n_recognition_images": 0,
            "n_transcribed_seconds": 0.0 if not is_admin else MAX_FLOAT,
            "n_generate_seconds": 0.0 if not is_admin else MAX_FLOAT,
            "current_spend": {
                "day": {
                    "n_transcribed_seconds": 0.0,
                    "n_generate_seconds": 0.0,
                    "n_used_tokens": 0.0,
                    "last_reset": datetime.now()
                },
                "week": {
                    "n_transcribed_seconds": 0.0,
                    "n_generate_seconds": 0.0,
                    "n_used_tokens": 0.0,
                    "last_reset": datetime.now()
                },
                "month": {
                    "n_transcribed_seconds": 0.0,
                    "n_generate_seconds": 0.0,
                    "n_used_tokens": 0.0,
                    "last_reset": datetime.now()
                },
                "all": {
                    "n_transcribed_seconds": 0.0,
                    "n_generate_seconds": 0.0,
                    "n_used_tokens": 0.0
                }
            }
        }

        if not await self.check_if_user_exists(user_id):
            await self.user_collection.insert_one(user_dict)

    async def update_spend(self, user_id,
                           n_transcribed_seconds: float = 0.0,
                           n_generate_seconds: float = 0.0,
                           n_used_tokens: float = 0.0):

        current_spend = await self.get_user_attribute(user_id, "current_spend")
        # last_reset = current_spend["last_reset"]

        now = datetime.now()

        await self.set_user_attribute(user_id=user_id,
                                      key="n_tokens",
                                      value=await self.get_user_attribute(user_id, "n_tokens") - n_used_tokens)
        await self.set_user_attribute(user_id=user_id,
                                      key="n_transcribed_seconds",
                                      value=await self.get_user_attribute(user_id,
                                                                          "n_transcribed_seconds") - n_transcribed_seconds)
        await self.set_user_attribute(user_id=user_id,
                                      key="n_generate_seconds",
                                      value=await self.get_user_attribute(user_id,
                                                                          "n_generate_seconds") - n_used_tokens)

        def reset_if_necessary(interval_name, interval_duration):
            if (now - current_spend[interval_name]["last_reset"]).days > interval_duration:
                current_spend[interval_name]["n_transcribed_seconds"] = 0.0
                current_spend[interval_name]["n_generate_seconds"] = 0.0
                current_spend[interval_name]["n_used_tokens"] = 0.0
                current_spend[interval_name]["last_reset"] = now

        reset_if_necessary("day", 1)
        reset_if_necessary("week", 7)
        reset_if_necessary("month", 30)

        current_spend["day"]["n_transcribed_seconds"] += n_transcribed_seconds
        current_spend["day"]["n_generate_seconds"] += n_generate_seconds
        current_spend["day"]["n_used_tokens"] += n_used_tokens

        current_spend["week"]["n_transcribed_seconds"] += n_transcribed_seconds
        current_spend["week"]["n_generate_seconds"] += n_generate_seconds
        current_spend["week"]["n_used_tokens"] += n_used_tokens

        current_spend["month"]["n_transcribed_seconds"] += n_transcribed_seconds
        current_spend["month"]["n_generate_seconds"] += n_generate_seconds
        current_spend["month"]["n_used_tokens"] += n_used_tokens

        current_spend["all"]["n_transcribed_seconds"] += n_transcribed_seconds
        current_spend["all"]["n_generate_seconds"] += n_generate_seconds
        current_spend["all"]["n_used_tokens"] += n_used_tokens

        await self.set_user_attribute(user_id, "current_spend", current_spend)

    async def add_new_vs(self, vs_id):
        vs_dict = {
            "_id": vs_id,
        }
        if not await self.check_if_vs_exists(vs_id):
            await self.vs_collection.insert_one(vs_dict)

    async def add_new_partner(self, partner_id):
        partner_dict = {
            "_id": partner_id,
        }
        if not await self.check_if_partner_exists(partner_id):
            await self.partner_collection.insert_one(partner_dict)

    async def add_new_rate(self,
                           name: str,
                           models: List[str],
                           n_tokens: int,
                           n_transcribed_seconds: float,
                           n_generated_seconds: float,
                           price: float,
                           type_: str):
        rate = {
            "_id": name,
            "models": models,
            "n_tokens": n_tokens,
            "n_transcribed_seconds": n_transcribed_seconds,
            "n_generated_seconds": n_generated_seconds,
            "price": price,
            "type": type_
        }

        if not await self.check_if_rate_exists(name):
            await self.rate_collection.insert_one(rate)

    async def add_new_promo(self,
                            promo_id: str,
                            rate_name: str):
        promo = {
            "_id": promo_id,
            "rate": rate_name
        }
        if not await self.check_if_promo_exists(promo_id=promo_id) and await self.check_if_rate_exists(rate_name):
            await self.promo_collection.insert_one(promo)

    async def start_new_dialog(self, user_id: int):
        await self.check_if_user_exists(user_id, raise_exception=True)

        dialog_id = str(uuid.uuid4())
        dialog_dict = {
            "_id": dialog_id,
            "user_id": user_id,
            "start_time": datetime.now(),
            "model": await self.get_user_attribute(user_id, "current_model"),
            "messages": []
        }

        await self.dialog_collection.insert_one(dialog_dict)

        await self.user_collection.update_one(
            {"_id": user_id},
            {"$set": {"current_dialog_id": dialog_id}}
        )

        return dialog_id

    async def get_user_attribute(self, user_id: int, key: str):
        await self.check_if_user_exists(user_id, raise_exception=True)
        user_dict = await self.user_collection.find_one({"_id": user_id})

        if key not in user_dict:
            return None

        return user_dict[key]

    async def get_promo_attribute(self, promo_id, key: str):
        await self.check_if_promo_exists(promo_id, raise_exception=True)
        promo_dict = await self.promo_collection.find_one({"_id": promo_id})

        rate_dict = await self.rate_collection.find_one({"_id": promo_dict["rate"]})

        if key not in promo_dict and key not in rate_dict:
            return None
        elif key in promo_dict:
            return promo_dict[key]
        else:
            return rate_dict[key]

    async def get_rate_data(self, rate_name):
        await self.check_if_rate_exists(rate_name, raise_exception=True)
        rate_data = await self.rate_collection.find_one({"_id": rate_name})

        return rate_data

    async def get_payment_data_user(self, user_id):
        await self.check_if_payments_exists_user(user_id, raise_exception=True)
        payment_data = await self.payments_collection.find_one({"_id": user_id})

        return payment_data

    async def get_user_data(self, user_id):
        await self.check_if_user_exists(user_id, raise_exception=True)
        user_data = await self.user_collection.find_one({"_id": user_id})

        return user_data

    async def get_all_rates(self):
        cursor = self.rate_collection.find({})
        rates = await cursor.to_list(length=None)
        return rates

    async def get_all_vs(self):
        cursor = self.vs_collection.find({})
        vs = await cursor.to_list(length=None)
        return vs

    async def get_all_partners(self):
        cursor = self.partner_collection.find({})
        partners = await cursor.to_list(length=None)
        return partners

    async def get_all_users_data(self):
        cursor = self.user_collection.find({})
        users = await cursor.to_list(length=None)
        return users

    async def get_all_user_ids(self):
        cursor = self.user_collection.find({})
        user_ids = await cursor.distinct('_id')
        return user_ids

    async def get_payments_by_reg(self, reg_pay_id):
        payment_data = await self.payments_collection.find_one({"reg_pay_id": reg_pay_id})

        return payment_data

    async def delete_rate(self, rate_name):
        await self.check_if_rate_exists(rate_name, raise_exception=True)
        await self.rate_collection.delete_one({"_id": rate_name})

    async def delete_payment(self, p_id):
        await self.check_if_payments_exists(p_id, raise_exception=True)
        await self.payments_collection.delete_one({"reg_pay_id": p_id})

    async def delete_payment_user(self, user_id):
        await self.check_if_payments_exists(user_id, raise_exception=True)
        await self.payments_collection.delete_one({"_id": user_id})

    async def get_rate_attribute(self, rate_name, key: str):
        await self.check_if_rate_exists(rate_name, raise_exception=True)

        rate_dict = await self.rate_collection.find_one({"_id": rate_name})

        if key not in rate_dict:
            return None
        return rate_dict[key]

    async def set_user_attribute(self, user_id: int, key: str, value: Any):
        await self.check_if_user_exists(user_id, raise_exception=True)
        await self.user_collection.update_one({"_id": user_id}, {"$set": {key: value}})

    async def set_rate_attribute(self, rate_name, key: str, value: Any):
        await self.check_if_rate_exists(rate_name, raise_exception=True)
        await self.rate_collection.update_one({"_id": rate_name}, {"$set": {key: value}})

    async def update_n_used_tokens(self, user_id: int, model: str, n_input_tokens: int, n_output_tokens: int):
        await self.check_if_user_exists(user_id, raise_exception=True)
        n_used_tokens_dict = await self.get_user_attribute(user_id, "n_used_tokens")
        n_tokens_available = await self.get_user_attribute(user_id, "n_tokens")

        self.check_if_have_tokens_for_answer(n_tokens_available, n_input_tokens, n_output_tokens, raise_exception=True)

        n_used_tokens_dict["n_input_tokens"] += n_input_tokens
        n_used_tokens_dict["n_output_tokens"] += n_output_tokens

        n_tokens_available -= (n_input_tokens + n_output_tokens)

        await self.set_user_attribute(user_id, "n_used_tokens", n_used_tokens_dict)
        await self.set_user_attribute(user_id, "n_tokens", n_tokens_available)

    async def get_dialog_messages(self, user_id: int, dialog_id: Optional[str] = None):
        await self.check_if_user_exists(user_id, raise_exception=True)

        if dialog_id is None:
            dialog_id = await self.get_user_attribute(user_id, "current_dialog_id")

        dialog_dict = await self.dialog_collection.find_one({"_id": dialog_id, "user_id": user_id})
        return dialog_dict["messages"]

    async def set_feedback(self, user_id, dialog_id: str = None, feed: bool = None):
        dialoges = await self.get_dialog_messages(user_id, dialog_id)
        dialoges[-1]["feed"] = feed

        await self.set_dialog_messages(user_id=user_id,
                                       dialog_messages=dialoges,
                                       dialog_id=dialog_id)

    async def set_dialog_messages(self, user_id: int, dialog_messages: list, dialog_id: Optional[str] = None):
        await self.check_if_user_exists(user_id, raise_exception=True)

        if dialog_id is None:
            dialog_id = await self.get_user_attribute(user_id, "current_dialog_id")

        await self.dialog_collection.update_one(
            {"_id": dialog_id, "user_id": user_id},
            {"$set": {"messages": dialog_messages}}
        )

    async def use_promo(self, promo_id, user_id):
        await self.check_if_user_exists(user_id, raise_exception=True)
        await self.check_if_promo_exists(promo_id, raise_exception=True)

        promo_dict = await self.promo_collection.find_one({"_id": promo_id})

        await self.check_if_rate_exists(promo_dict["rate"], raise_exception=True)

        rate_dict = await self.rate_collection.find_one({"_id": promo_dict["rate"]})

        rate_models, user_models = rate_dict["models"], await self.get_user_attribute(user_id, "models")
        new_models = list(set(rate_models) | set(user_models))

        rate_n_tokens_monthly = rate_dict["n_tokens"]
        rate_n_rec_images = rate_dict["n_rec_images"]
        rate_n_transcribed_seconds = rate_dict["n_transcribed_seconds"]
        rate_n_generated_seconds = rate_dict["n_generated_seconds"]

        await self.user_collection.update_one({"_id": user_id}, {"$set": {
            "models": new_models,
            "n_tokens": rate_n_tokens_monthly,
            "n_rec_images": rate_n_rec_images,
            "n_transcribed_seconds": rate_n_transcribed_seconds,
            "n_generated_seconds": rate_n_generated_seconds
        }})

    async def use_rate(self, rate_name, user_id):
        await self.check_if_user_exists(user_id, raise_exception=True)
        await self.check_if_rate_exists(rate_name, raise_exception=True)

        rate_dict = await self.rate_collection.find_one({"_id": rate_name})

        rate_models, user_models = rate_dict["models"], await self.get_user_attribute(user_id, "models")
        new_models = list(set(rate_models) | set(user_models))

        rate_n_tokens_monthly = rate_dict["n_tokens"] + await self.get_user_attribute(user_id, "n_tokens")
        rate_n_rec_images = rate_dict["n_rec_images"]
        rate_n_transcribed_seconds = rate_dict["n_transcribed_seconds"]
        rate_n_generated_seconds = rate_dict["n_generated_seconds"]

        await self.user_collection.update_one({"_id": user_id}, {"$set": {
            "models": new_models,
            "n_tokens": rate_n_tokens_monthly,
            "n_rec_images": rate_n_rec_images,
            "n_transcribed_seconds": rate_n_transcribed_seconds,
            "n_generated_seconds": rate_n_generated_seconds
        }})

    async def set_payment(self, user_id, rate_name):
        await self.check_if_user_exists(user_id, raise_exception=True)
        await self.check_if_rate_exists(rate_name, raise_exception=True)

        await self.user_collection.update_one({"_id": user_id}, {"$set": {
            "rate": rate_name,
            "last_pay": datetime.now()
        }})

        await self.use_rate(rate_name=rate_name, user_id=user_id)

    async def accept_payment(self, reg_pay_id):
        await self.check_if_payments_exists(reg_pay_id, raise_exception=True)

        payment_data = await self.get_payments_by_reg(reg_pay_id=reg_pay_id)
        user_id = int(payment_data["_id"])
        await self.check_if_user_exists(user_id, raise_exception=True)

        if await self.get_rate_attribute(rate_name=payment_data["rate_id"], key="price") <= \
                payment_data["amount"] * 100:
            await self.set_user_attribute(user_id, "last_pay", datetime.now())
            await self.update_user(user_id)
            await self.delete_payment(p_id=reg_pay_id)
            return True
        return False

    async def accept_rec_payment(self, user_id, rate_name):
        await self.check_if_user_exists(user_id, raise_exception=True)
        await self.check_if_rate_exists(rate_name, raise_exception=True)

        await self.set_user_attribute(user_id, "last_pay", datetime.now())
        await self.set_user_attribute(user_id, "rate", rate_name)
        await self.update_user(user_id)
        await self.delete_payment_user(user_id)

    async def update_user(self, user_id):
        await self.check_if_user_exists(user_id, raise_exception=True)
        await self.set_user_attribute(user_id, "last_interaction", datetime.now())
        rate_name = await self.get_user_attribute(user_id, "rate")

        if rate_name == "free":
            return

        if await self.check_payment(user_id):
            if (datetime.now() - await self.get_user_attribute(user_id, "last_update")).days >= 30:
                await self.use_rate(rate_name, user_id)
                await self.set_user_attribute(user_id, "last_update", datetime.now())
        else:
            if await self.get_user_attribute(user_id, "userToken") is not None:
                try:
                    await self.create_extend_recurrent_payment(user_id, rate_name)
                except:
                    pass
            else:
                await self.set_user_attribute(user_id, "rate", "free")
                await self.use_rate("free", user_id)
                await self.set_user_attribute(user_id, "last_update", datetime.now())

    async def accept_extend_rec_pay(self, user_id: int):
        rate_name = await self.get_user_attribute(user_id, "rate")

        await self.check_if_user_exists(user_id, raise_exception=True)

        if rate_name == "free":
            return

        await self.check_if_rate_exists(rate_name, raise_exception=True)

        result = await self.create_extend_recurrent_payment(user_id=user_id,
                                                            rate_name=rate_name)
        result = await self.processing_payments(data_rec_pay=result,
                                                user_id=user_id,
                                                rate_name=rate_name)
        if not result:
            await self.delete_payment_user(user_id=user_id)
            raise PaymentError

        payment_data = await self.get_payment_data_user(user_id=user_id)

        status_data = await self.get_status_recurrent_payment(payment_data["reg_pay_id"])
        if status_data["state"] in ["payed", "processed"] and \
                int(status_data["totalAmount"]) == int(payment_data["amount"]):
            await self.accept_rec_payment(user_id=user_id,
                                          rate_name=rate_name)

    async def create_extend_recurrent_payment(self,
                                              user_id: int,
                                              rate_name: str,
                                              url: str = "https://api2.ckassa.ru/api-shop/do/payment"):
        user_token = await self.get_user_attribute(user_id, "userToken")
        user_phone = await self.get_user_attribute(user_id, "phone")

        if user_token is None and user_phone is None:
            raise PaymentCreationError

        if user_token is None:
            callback_api = await self.registr_user(phone_number=user_phone)
            user_token = callback_api["userToken"]

        rate_data = await self.get_rate_data(rate_name=rate_name)

        amount = rate_data["price"] * 100

        available_cards = await self.get_active_user_cards(user_token=user_token)

        if not available_cards:
            return False

        headers = {
            'Content-Type': 'application/json',
            'Authorization': await self.make_credential(login=Config.shop_token,
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

    async def processing_payments(self,
                                  data_rec_pay: dict,
                                  user_id: int,
                                  rate_name: str):

        reg_pay_num = data_rec_pay["regPayNum"]
        status_data = await self.get_status_recurrent_payment(reg_pay_num=reg_pay_num)

        await self.add_new_payment(user_id=int(user_id),
                                   amount=int(status_data["totalAmount"]),
                                   reg_pay_num=reg_pay_num,
                                   rate_id=rate_name)

        start_time = datetime.now()

        while status_data["state"] not in ["payed", "holded", "processed", "error"]:
            status_data = await self.get_status_recurrent_payment(reg_pay_num=reg_pay_num)
            await asyncio.sleep(0.5)

        if status_data["state"] in ["payed", "processed"]:
            return True

        elif status_data["state"] == "holded":

            unhold_data = await self.confirm_payment(reg_pay_num=reg_pay_num,
                                                     order_id=...)
            if unhold_data["resultState"] == "success":
                return True
            else:
                return False
        else:
            return False

    async def make_credential(self,
                              login: str,
                              password: str):
        credential = f'{login}:{password}'
        encoded_credential = base64.b64encode(credential.encode("ascii"))

        return f'Basic {encoded_credential.decode("ascii")}'

    async def registr_user(self,
                           url: str = "https://demo-api2.ckassa.ru/api-shop/user/registration",
                           phone_number: str | None = None,
                           name: str | None = None,
                           surname: str | None = None,
                           middlename: str | None = None):
        if phone_number is None:
            raise RegistrationError

        headers = {
            'Content-Type': 'application/json',
            'Authorization': await self.make_credential(login=Config.shop_token,
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

    async def get_active_user_cards(self,
                                    user_token: str,
                                    url: str = "https://api2.ckassa.ru/api-shop/ver3/get/cards"):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': await self.make_credential(login=Config.shop_token,
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

    async def get_status_recurrent_payment(self,
                                           url: str = "https://api2.ckassa.ru/api-shop/rs/shop/check/payment/state",
                                           reg_pay_num: int | str = None):
        if reg_pay_num is None:
            raise RecurrentPaymentCheckError

        headers = {
            'Content-Type': 'application/json',
            'Authorization': await self.make_credential(login=Config.shop_token,
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

    async def confirm_payment(self,
                              url: str = "https://api2.ckassa.ru/api-shop/provision-services/confirm",
                              reg_pay_num: int | str = None,
                              order_id: int | str = None):
        if reg_pay_num is None or order_id is None:
            raise ConfirmPaymentError

        headers = {
            'Content-Type': 'application/json',
            'Authorization': await self.make_credential(login=Config.shop_token,
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


DataBase = Database()

#asyncio.run(DataBase.add_admins_from_config())
