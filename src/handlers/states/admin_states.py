from aiogram.fsm.state import State, StatesGroup


class RateForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_n_tokens = State()
    waiting_for_n_transcribed_seconds = State()
    waiting_for_n_generated_seconds = State()
    waiting_for_price = State()
    waiting_for_type = State()
    waiting_for_change = State()


class MassSend(StatesGroup):
    waiting_for_message = State()


class AddKnowledge(StatesGroup):
    waiting_for_youtube = State()
    waiting_for_gdrive = State()
    waiting_for_file = State()

class AddPartner(StatesGroup):
    waiting_for_link = State()
