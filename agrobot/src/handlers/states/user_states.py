from aiogram.fsm.state import State, StatesGroup


class UserPhone(StatesGroup):
    waiting_for_user_phone = State()
