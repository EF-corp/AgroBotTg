import pymongo
from typing import Optional, Any, List
import uuid
from datetime import datetime
from src.config import Config
from random import randint

MAX_INT = 2 ** 31 - 1
MAX_FLOAT = float(MAX_INT)


class Database:
    def __init__(self, name: str = Config.name):
        self.client = pymongo.MongoClient(Config.mongodb_url)
        self.db = self.client[name]

        self.user_collection = self.db["user"]
        self.dialog_collection = self.db["dialog"]
        self.promo_collection = self.db["promo"]
        self.rate_collection = self.db["rate"]
        self.admin_collection = self.db["admin"]
        self.vs_collection = self.db["vs"]
        self.partner_collection = self.db["partner"]
        self.payments_collection = self.db["payments"]

    def check_if_user_exists(self, user_id: int, raise_exception: bool = False):
        if self.user_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist!")
            else:
                return False

    def check_if_admin_exists(self, admin_id: int, raise_exception: bool = False):
        if self.admin_collection.count_documents({"_id": admin_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Admin {admin_id} does not exist!")
            else:
                return False

    def check_if_rate_exists(self, name, raise_exception: bool = False):
        if self.rate_collection.count_documents({"_id": name}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Rate {name} does not exist!")
            else:
                return False

    def check_if_promo_exists(self, promo_id, raise_exception: bool = False):
        if self.promo_collection.count_documents({"_id": promo_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Rate {promo_id} does not exist!")
            else:
                return False

    def check_if_vs_exists(self, vs_id, raise_exception: bool = False):
        if self.vs_collection.count_documents({"_id": vs_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Vector store {vs_id} does not exist!")
            else:
                return False

    def check_if_partner_exists(self, partner_id, raise_exception: bool = False):
        if self.partner_collection.count_documents({"_id": partner_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Vector store {partner_id} does not exist!")
            else:
                return False

    def check_if_payments_exists(self, reg_pay_id, raise_exception: bool = False):
        if self.payments_collection.count_documents({"reg_pay_id": reg_pay_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"Payment {reg_pay_id} does not exist!")
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

    def check_payment(self, user_id, raise_exception: bool = False):

        self.check_if_user_exists(user_id, raise_exception=True)

        rate = self.get_user_attribute(user_id, "rate")
        self.check_if_rate_exists(rate, raise_exception=True)

        rate_dict = self.rate_collection.find_one({"_id": rate})
        type_ = rate_dict["type"]

        if (type_ == "monthly" and (datetime.now() - self.get_user_attribute(user_id, "last_pay")).days <= 30) \
                or (type_ == "yearly" and (datetime.now() - self.get_user_attribute(user_id, "last_pay")).days <= 365):
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} don't pay!")
            else:
                return False

    def check_if_need_update(self, user_id, raise_exception: bool = False):
        self.check_if_user_exists(user_id, raise_exception=True)

        rate = self.get_user_attribute(user_id, "rate")
        self.check_if_rate_exists(rate, raise_exception=True)

        rate_dict = self.rate_collection.find_one({"_id": rate})
        type_ = rate_dict["type"]

        if (type_ == "monthly" and (datetime.now() - self.get_user_attribute(user_id, "last_pay")).days <= 30) \
                or (type_ == "yearly" and (datetime.now() - self.get_user_attribute(user_id, "last_pay")).days <= 365):
            return False
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} don't pay!")
            else:
                return True

    def add_new_payment(self,
                        user_id: int,
                        amount: int,
                        rate_id: str):

        payment_dict = {
            "_id": user_id,
            "reg_pay_id": randint(10000000000000000000, 20000000000000000000),    # ?
            "rate_id": rate_id,
            "amount": amount
        }

        self.payments_collection.insert_one(payment_dict)

    def add_new_user(
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

        if not self.check_if_user_exists(user_id):
            self.user_collection.insert_one(user_dict)

    def update_spend(self, user_id,
                     n_transcribed_seconds: float = 0.0,
                     n_generate_seconds: float = 0.0,
                     n_used_tokens: float = 0.0):

        current_spend = self.get_user_attribute(user_id, "current_spend")
        # last_reset = current_spend["last_reset"]

        now = datetime.now()

        self.set_user_attribute(user_id=user_id,
                                key="n_tokens",
                                value=self.get_user_attribute(user_id, "n_tokens") - n_used_tokens)
        self.set_user_attribute(user_id=user_id,
                                key="n_transcribed_seconds",
                                value=self.get_user_attribute(user_id, "n_transcribed_seconds") - n_transcribed_seconds)
        self.set_user_attribute(user_id=user_id,
                                key="n_generate_seconds",
                                value=self.get_user_attribute(user_id, "n_generate_seconds") - n_used_tokens)

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

        self.set_user_attribute(user_id, current_spend)

    def add_new_vs(self, vs_id):
        vs_dict = {
            "_id": vs_id,
        }
        if not self.check_if_vs_exists(vs_id):
            self.vs_collection.insert_one(vs_dict)

    def add_new_partner(self, partner_id):
        partner_dict = {
            "_id": partner_id,
        }
        if not self.check_if_partner_exists(partner_id):
            self.partner_collection.insert_one(partner_dict)

    def add_new_rate(self,
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

        if not self.check_if_rate_exists(name):
            self.rate_collection.insert_one(rate)

    def add_new_promo(self,
                      promo_id: str,
                      rate_name: str):
        promo = {
            "_id": promo_id,
            "rate": rate_name
        }
        if not self.check_if_promo_exists(promo_id=promo_id) and self.check_if_rate_exists(rate_name):
            self.promo_collection.insert_one(promo)

    def start_new_dialog(self, user_id: int):
        self.check_if_user_exists(user_id, raise_exception=True)

        dialog_id = str(uuid.uuid4())
        dialog_dict = {
            "_id": dialog_id,
            "user_id": user_id,
            "start_time": datetime.now(),
            "model": self.get_user_attribute(user_id, "current_model"),
            "messages": []
        }

        self.dialog_collection.insert_one(dialog_dict)

        self.user_collection.update_one(
            {"_id": user_id},
            {"$set": {"current_dialog_id": dialog_id}}
        )

        return dialog_id

    def get_user_attribute(self, user_id: int, key: str):
        self.check_if_user_exists(user_id, raise_exception=True)
        user_dict = self.user_collection.find_one({"_id": user_id})

        if key not in user_dict:
            return None

        return user_dict[key]

    def get_promo_attribute(self, promo_id, key: str):
        self.check_if_promo_exists(promo_id, raise_exception=True)
        promo_dict = self.user_collection.find_one({"_id": promo_id})

        rate_dict = self.rate_collection.find_one({"_id": promo_dict["rate"]})

        if key not in promo_dict and key not in rate_dict:
            return None
        elif key not in promo_dict:
            return promo_dict[key]
        else:
            return rate_dict[key]

    def get_rate_data(self, rate_name):
        self.check_if_rate_exists(rate_name, raise_exception=True)
        rate_data = self.rate_collection.find_one({"_id": rate_name})

        return rate_data

    def get_payment_data(self, id_):
        self.check_if_payments_exists(id_, raise_exception=True)
        payment_data = self.payments_collection.find_one({"_id": id_})

        return payment_data

    def get_user_data(self, user_id):
        self.check_if_user_exists(user_id, raise_exception=True)
        rate_data = self.rate_collection.find_one({"_id": user_id})

        return rate_data

    def get_all_rates(self):
        cursor = self.rate_collection.distinct("_id")
        return cursor

    def get_all_vs(self):
        cursor = self.vs_collection.distinct("_id")
        return cursor

    def get_all_partner(self):
        cursor = self.partner_collection.distinct("_id")
        return cursor

    def get_all_users_data(self):
        cursor = self.user_collection.find({})
        return list(cursor)

    def get_all_user_idS(self):
        cursor = self.user_collection.distinct("_id")
        return cursor

    def get_payments_by_reg(self, reg_pay_id):
        payment_data = self.payments_collection.find_one({"reg_pay_id": reg_pay_id})

        return payment_data

    def delete_rate(self, rate_name):
        self.check_if_rate_exists(rate_name, raise_exception=True)
        self.rate_collection.delete_one({"_id": rate_name})

    def delete_payment(self, p_id):
        self.check_if_payments_exists(p_id, raise_exception=True)
        self.payments_collection.delete_one({"reg_pay_id": p_id})

    def get_rate_attribute(self, rate_name, key: str):
        self.check_if_rate_exists(rate_name, raise_exception=True)

        rate_dict = self.rate_collection.find_one({"_id": rate_name})

        if key not in rate_dict:
            return None
        return rate_dict[key]

    def set_user_attribute(self, user_id: int, key: str, value: Any):
        self.check_if_user_exists(user_id, raise_exception=True)
        self.user_collection.update_one({"_id": user_id}, {"$set": {key: value}})

    def set_rate_attribute(self, rate_name, key: str, value: Any):
        self.check_if_rate_exists(rate_name, raise_exception=True)
        self.rate_collection.update_one({"_id": rate_name}, {"$set": {key: value}})

    ##

    def update_n_used_tokens(self, user_id: int, model: str, n_input_tokens: int, n_output_tokens: int):
        self.check_if_user_exists(user_id, raise_exception=True)
        n_used_tokens_dict = self.get_user_attribute(user_id, "n_used_tokens")
        n_tokens_available = self.get_user_attribute(user_id, "n_tokens")

        self.check_if_have_tokens_for_answer(n_tokens_available, n_input_tokens, n_output_tokens, raise_exception=True)

        n_used_tokens_dict["n_input_tokens"] += n_input_tokens
        n_used_tokens_dict["n_output_tokens"] += n_output_tokens

        n_tokens_available -= (n_input_tokens + n_output_tokens)

        self.set_user_attribute(user_id, "n_used_tokens", n_used_tokens_dict)
        self.set_user_attribute(user_id, "n_tokens", n_tokens_available)

    # def update_spend(self, user_id: int, **kwargs):#model: str, n_input_tokens: int, n_output_tokens: int, image_rec:int=0, voice_gen):
    #     self.check_if_user_exists(user_id, raise_exception=True)
    #     ...

    def get_dialog_messages(self, user_id: int, dialog_id: Optional[str] = None):
        self.check_if_user_exists(user_id, raise_exception=True)

        if dialog_id is None:
            dialog_id = self.get_user_attribute(user_id, "current_dialog_id")

        dialog_dict = self.dialog_collection.find_one({"_id": dialog_id, "user_id": user_id})
        return dialog_dict["messages"]

    def set_feedback(self, user_id, dialog_id: str | None = None, feed: bool | None = None):
        dialoges = self.get_dialog_messages(user_id, dialog_id)
        dialoges[-1]["feed"] = feed

        self.set_dialog_messages(user_id=user_id,
                                 dialog_messages=dialoges,
                                 dialog_id=dialog_id)

    def set_dialog_messages(self, user_id: int, dialog_messages: list, dialog_id: Optional[str] = None):
        self.check_if_user_exists(user_id, raise_exception=True)

        if dialog_id is None:
            dialog_id = self.get_user_attribute(user_id, "current_dialog_id")

        self.dialog_collection.update_one(
            {"_id": dialog_id, "user_id": user_id},
            {"$set": {"messages": dialog_messages}}
        )

    def use_promo(self, promo_id, user_id):
        self.check_if_user_exists(user_id, raise_exception=True)
        self.check_if_promo_exists(promo_id, raise_exception=True)

        promo_dict = self.user_collection.find_one({"_id": promo_id})

        self.check_if_rate_exists(promo_dict["rate"], raise_exception=True)

        rate_dict = self.rate_collection.find_one({"_id": promo_dict["rate"]})

        type_, price = rate_dict["type"], rate_dict["price"]

        rate_models, user_models = rate_dict["models"], self.get_user_attribute(user_id, "models")
        new_models = list(set(rate_models) + set(user_models))

        rate_n_tokens_monthly = rate_dict["n_tokens_monthly"]
        rate_n_rec_images = rate_dict["n_rec_images"]
        rate_n_transcribed_seconds = rate_dict["n_transcribed_seconds"]
        rate_n_generated_seconds = rate_dict["n_generated_char"]

        self.user_collection.update_one({"_id": user_id}, {"$set": {"models": new_models,
                                                                    "n_tokens_monthly": rate_n_tokens_monthly,
                                                                    "n_rec_images": rate_n_rec_images,
                                                                    "n_transcribed_char": rate_n_transcribed_seconds,
                                                                    "n_generated_seconds": rate_n_generated_seconds}
                                                           })
        # return type_

    def use_rate(self, rate_name, user_id):
        self.check_if_user_exists(user_id, raise_exception=True)
        self.check_if_rate_exists(rate_name, raise_exception=True)

        rate_dict = self.rate_collection.find_one({"_id": rate_name})

        type_, price = rate_dict["type"], rate_dict["price"]

        rate_models, user_models = rate_dict["models"], self.get_user_attribute(user_id, "models")

        rate_n_tokens_monthly = rate_dict["n_tokens"] + self.get_user_attribute(user_id, "n_tokens")
        rate_n_rec_images = rate_dict["n_rec_images"]
        rate_n_transcribed_seconds = rate_dict["n_transcribed_seconds"]
        rate_n_generated_seconds = rate_dict["n_generated_seconds"]

        self.user_collection.update_one({"_id": user_id}, {"$set": {"n_tokens": rate_n_tokens_monthly,
                                                                    "n_rec_images": rate_n_rec_images,
                                                                    "n_transcribed_seconds": rate_n_transcribed_seconds,
                                                                    "n_generated_seconds": rate_n_generated_seconds}})

        # return type_, price

    def set_payment(self, user_id, rate_name):
        self.check_if_user_exists(user_id, raise_exception=True)
        self.check_if_rate_exists(rate_name, raise_exception=True)

        self.user_collection.update_one({"_id": user_id}, {"$set": {"rate": rate_name,
                                                                    "last_pay": datetime.now()}})

        self.use_rate(rate_name=rate_name, user_id=user_id)

    def accept_payment(self, reg_pay_id):

        self.check_if_payments_exists(reg_pay_id, raise_exception=True)

        payment_data = self.get_payments_by_reg(reg_pay_id=reg_pay_id)
        user_id = int(payment_data["_id"])
        self.check_if_user_exists(user_id, raise_exception=True)

        if self.get_rate_attribute(rate_name=payment_data["rate_id"], key="price") <= payment_data["amount"] * 100:
            self.set_user_attribute(user_id, "last_pay", datetime.now())
            self.update_user(user_id)
            self.delete_payment(p_id=reg_pay_id)
            return True
        return False

    def update_user(self, user_id):
        # self.check_if_need_update(user_id, raise_exception=True)
        self.check_if_user_exists(user_id, raise_exception=True)
        self.set_user_attribute(user_id, "last_interaction", datetime.now())

        if self.get_user_attribute(user_id, "rate") == "free":
            return
        if self.check_payment(user_id):
            if (datetime.now() - self.get_user_attribute(user_id, "last_update")).days >= 30:
                rate_name = self.get_user_attribute(user_id, "rate")
                self.use_rate(rate_name, user_id)
                self.set_user_attribute(user_id, "last_update", datetime.now())
        else:
            self.set_user_attribute(user_id, "rate", "free")
            self.use_rate("free", user_id)
            self.set_user_attribute(user_id, "last_update", datetime.now())


DataBase = Database()
