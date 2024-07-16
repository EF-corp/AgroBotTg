import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, \
    InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from src.database import DataBase as db
from src.handlers.states import AddKnowledge, RateForm, MassSend, AddPartner, ChangeRate
from src.filters import AdminCheck
from src.nn import KnowledgeLoader, OpenAIHelper
from src.utils import ADMIN_HELP_MESSAGE, HELP_GROUP_CHAT_MESSAGE, \
    ADMIN_MENU_TEXT, ADMIN_RATE_TEXT, \
    get_rate_data, ADMIN_ADD_KNOWLEDGE_TEXT, \
    Stats, register_admin_in_db_as_user, \
    show_rates_admin, is_previous_message_not_answered_yet
from src.utils.general import extract_docx_text, extract_pdf_text, \
    extract_pptx_text, extract_xlsx_text

from src.keyboards import get_help_keyboard, kb_menu_admin, \
    kb_rates_admin, get_type_rate, \
    get_edit_rate_kb, kb_knowledge_admin, \
    kb_stats_admin, get_feed_kb
from src.config import Config
from src.commands.admin import set_admin_commands_menu

from datetime import datetime
import asyncio
import aiofiles
import aiofiles.os
import io
from typing import Dict
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import logging

admin = Router()

admin_tasks = {}
admin_semaphores = {}

knowledge_loader = KnowledgeLoader()
openai_helper = OpenAIHelper()
executor = ThreadPoolExecutor()


@admin.message(AdminCheck(), CommandStart())
async def start_admin_handle(message: Message):
    user_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await set_admin_commands_menu(bot=message.bot,
                                  user_id=user_id)

    await db.set_user_attribute(user_id, "last_interaction", datetime.now())
    await db.start_new_dialog(user_id)

    reply_text = "👋 Привет! Я АгроБот 🌱, твой помощник в мире растений! \n\n"
    reply_text += ADMIN_HELP_MESSAGE

    await message.answer(text=reply_text,
                         parse_mode="HTML")


@admin.message(AdminCheck(), Command("help"))
@admin.callback_query(AdminCheck(), F.data == "help_admin")
async def help_admin_handle(message: Message):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())
    # reply_text = "Привет! Я <b>АгроБот</b> - бот, созданный для помощи агрономам! 🤖\n\n"
    reply_text = ADMIN_HELP_MESSAGE
    if isinstance(message, Message):
        await message.answer(text=reply_text,
                             parse_mode="HTML",
                             reply_markup=get_help_keyboard())
    else:
        await message.bot.send_message(chat_id=admin_id,
                                       text=reply_text,
                                       parse_mode="HTML",
                                       reply_markup=get_help_keyboard()
                                       )


@admin.message(AdminCheck(), Command("notify"))
@admin.callback_query(AdminCheck(), F.data == "notify")
async def notify_handler(message: Message | CallbackQuery, state: FSMContext):
    await register_admin_in_db_as_user(message, admin_semaphores)
    await state.set_state(MassSend.waiting_for_message)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отменить рассылку",
                             callback_data="cancel_notify")
    ]])
    if isinstance(message, Message):
        await message.answer(text='Отправьте сообщение, которое вы хотите разослать всем пользователям\n'
                                  'Чтобы отменить уведомления пользователям во время рассылки, используйте комманду '
                                  'отмены (/cancel)',
                             reply_markup=cancel_kb
                             )
    else:
        await message.answer('')

        await message.message.answer(text='Отправьте сообщение, которое вы хотите разослать всем пользователям\n'
                                          'Чтобы отменить уведомления пользователям во время '
                                          'рассылки, используйте комманду отмены (/cancel).',
                                     reply_markup=cancel_kb)


@admin.message(AdminCheck(), MassSend.waiting_for_message)
async def notify_message_handler(message: Message | CallbackQuery, state: FSMContext):
    if isinstance(message, CallbackQuery) and message.data == "cancel_notify":
        await state.clear()
        await message.message.answer(text="✅ Рассылка остановлена",
                                     parse_mode="HTML")
        return

    await message.answer('⏳ Подождите... идёт рассылка.')

    admin_id = message.from_user.id

    user_ids = await db.get_all_user_ids()

    async def _send_message(_user_id):
        try:
            await message.send_copy(chat_id=_user_id)

        except Exception as e:
            await message.answer(f"❌ Произошла ошибка: <i>{e}</i> при отправлении пользователю <i>{_user_id}</i>",
                                 parse_mode="HTML")

    async def send_task():
        await asyncio.gather(*[_send_message(int(user_id)) for user_id in user_ids])

    async with admin_semaphores[admin_id]:
        task = asyncio.create_task(
            send_task()
        )

        admin_tasks[admin_id] = task
        try:
            await task
        except asyncio.CancelledError:
            await message.answer("✅ Процесс завершен",
                                 parse_mode="HTML")
        else:
            pass
        finally:
            if admin_id in admin_tasks:
                del admin_tasks[admin_id]
            await message.answer("✅ Рассылка успешно завершена",
                                 parse_mode="HTML")
            await state.clear()


@admin.message(AdminCheck(), Command("menu"))
@admin.callback_query(AdminCheck(), F.data == "menu")
async def admin_settings_handle(message: Message | CallbackQuery):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())

    if isinstance(message, Message):
        await message.answer(text=ADMIN_MENU_TEXT,
                             parse_mode="HTML",
                             reply_markup=kb_menu_admin().as_markup())

    else:
        await message.answer('')
        await message.bot.edit_message_text(chat_id=admin_id,
                                            message_id=message.message.message_id,
                                            text=ADMIN_MENU_TEXT,
                                            parse_mode="HTML",
                                            reply_markup=kb_menu_admin().as_markup()
                                            )


@admin.message(AdminCheck(), Command("tariffs"))
@admin.callback_query(AdminCheck(), F.data.startswith("to_rates"))
async def admin_rate_handler(message: Message | CallbackQuery):
    admin_id = message.from_user.id

    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())
    rates = await db.get_all_rates()

    if isinstance(message, Message):
        await message.answer(text=ADMIN_RATE_TEXT,
                             parse_mode="HTML",
                             reply_markup=kb_rates_admin(rates).as_markup())
        # await show_rates_admin(message=message,
        #                        text=ADMIN_RATE_TEXT,
        #                        rates=rates,
        #                        page=0)

    else:
        await message.answer('')

        await message.bot.edit_message_text(text=ADMIN_RATE_TEXT,
                                            parse_mode="HTML",
                                            chat_id=admin_id,
                                            message_id=message.message.message_id,
                                            reply_markup=kb_rates_admin(rates,
                                                                        from_menu=(
                                                                                message.data == "to_rates_from_menu")).as_markup())

        # await show_rates_admin(message=message.message,
        #                        edit_id=message.message.message_id,
        #                        text=ADMIN_RATE_TEXT,
        #                        rates=rates,
        #                        from_menu=(message.data == "to_rates_from_menu"),
        #                        page=0)


@admin.callback_query(AdminCheck(), F.data.startswith("prev_rate_"))
async def rate_prev_page_handler(callback: CallbackQuery):
    await callback.answer('')
    page = int(callback.data.split("_")[2])

    rates = await db.get_all_rates()
    page -= 1
    if page < 0:
        return

    await callback.bot.edit_message_text(chat_id=callback.from_user.id,
                                         message_id=callback.message.message_id,
                                         text=ADMIN_RATE_TEXT,
                                         parse_mode="HTML",
                                         reply_markup=kb_rates_admin(rates=rates, page=page).as_markup()
                                         )


@admin.callback_query(AdminCheck(), F.data.startswith("next_rate_"))
async def rate_next_page_handler(callback: CallbackQuery):
    await callback.answer('')
    page = int(callback.data.split("_")[2])

    rates = await db.get_all_rates()
    page += 1
    if page >= len(rates) / Config.n_rate_per_page:
        return

    await callback.bot.edit_message_text(chat_id=callback.from_user.id,
                                         message_id=callback.message.message_id,
                                         text=ADMIN_RATE_TEXT,
                                         parse_mode="HTML",
                                         reply_markup=kb_rates_admin(rates=rates, page=page).as_markup()
                                         )


@admin.callback_query(AdminCheck(), F.data.startswith("change_rate_"))
async def change_rate_handle(callback: CallbackQuery, state: FSMContext):
    rate_name = callback.data.split("_")[2]

    await state.update_data(rate=rate_name)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить количество токенов",
                              callback_data=f"change_tokens")],
        [InlineKeyboardButton(text="Изменить количество секунд на генерацию",
                              callback_data=f"change_gen_sec")],
        [InlineKeyboardButton(text="Изменить количество секунд на транскрипцию",
                              callback_data=f"change_transcribe_sec")],
        [InlineKeyboardButton(text="Изменить цену",
                              callback_data=f"change_price")],
        [InlineKeyboardButton(text="Изменить период оплаты",
                              callback_data=f"change_type")],
    ])

    await callback.answer('')

    await callback.message.answer(text="Чтобы изменить тариф, выберите необходимый пункт и введите или выберете "
                                       f"новое значение параметра тарифа <b>{rate_name}</b>.",
                                  parse_mode="HTML",
                                  reply_markup=kb)


@admin.callback_query(AdminCheck(), F.data.startswith("change_tokens"))
async def change_count_tokens(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChangeRate.waiting_for_n_tokens)
    await callback.answer('')

    await callback.message.answer(text="Введите новое количество токенов для тарифа:")


@admin.message(AdminCheck(), ChangeRate.waiting_for_n_tokens)
async def get_new_n_tokens(message: Message, state: FSMContext):
    try:
        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Обновление данных тарифа остановлено")
            await state.clear()
            return

        n_tokens = int(message.text)

    except:
        await message.answer("❌ Ошибка, количество токенов должно быть целым числом, например: 1000\n"
                             "Введите новое количество токенов или скажите 'отмена'.")

    else:
        data = await state.get_data()
        rate = data["rate"]
        await state.clear()
        await db.set_rate_attribute(rate, "n_tokens", n_tokens)
        await message.answer(text="✅ Данные успешно обновлены!")


@admin.callback_query(AdminCheck(), F.data.startswith("change_price"))
async def change_price(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChangeRate.waiting_for_price)
    await callback.answer('')

    await callback.message.answer(text="Введите новую цену тарифа:")


@admin.message(AdminCheck(), ChangeRate.waiting_for_price)
async def get_change_price(message: Message, state: FSMContext):
    try:
        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Обновление данных тарифа остановлено")
            await state.clear()
            return

        price = int(message.text)

    except:
        await message.answer("❌ Ошибка, цена должна быть целым числом, например: 1000\n"
                             "Введите новую цену или скажите 'отмена'.")

    else:
        data = await state.get_data()
        rate = data["rate"]
        await state.clear()
        await db.set_rate_attribute(rate, "price", price)
        await message.answer(text="✅ Данные успешно обновлены!")


@admin.callback_query(AdminCheck(), F.data.startswith("change_type"))
async def change_type(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChangeRate.waiting_for_type)
    await callback.answer('')

    await callback.message.answer(text="Выберите тип оплаты тарифа:",
                                  reply_markup=get_type_rate())


@admin.message(AdminCheck(), ChangeRate.waiting_for_type)
async def get_change_type(message: Message | CallbackQuery, state: FSMContext):
    try:
        if isinstance(message, Message):
            await message.answer(text="⛔ Обновление данных тарифа остановлено")
            await state.clear()
            return

        type_ = message.data

    except:
        await message.answer("❌ Ошибка при обработке изменения тарифа.")

    else:

        data = await state.get_data()
        rate = data["rate"]
        await state.clear()
        await db.set_rate_attribute(rate, "type", type_)

        await message.message.answer(text="✅ Данные успешно обновлены!")


@admin.callback_query(AdminCheck(), F.data.startswith("change_transcribe_sec"))
async def change_transcribe_sec(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChangeRate.waiting_for_n_transcribed_seconds)
    await callback.answer('')

    await callback.message.answer(text="Введите новое количество секунд на транскрипцию для тарифа:")


@admin.message(AdminCheck(), ChangeRate.waiting_for_n_transcribed_seconds)
async def get_new_change_transcribe_sec(message: Message, state: FSMContext):
    try:
        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Обновление данных тарифа остановлено")
            await state.clear()
            return

        n_tokens = float(message.text)

    except:
        await message.answer(
            "❌ Ошибка, количество секунд на транскрипцию должно быть целым или дробным числом, например: 1000"
            "\nВведите новое количество секунд на транскрипцию или скажите 'отмена'.")

    else:
        data = await state.get_data()
        rate = data["rate"]
        await state.clear()
        await db.set_rate_attribute(rate, "n_transcribed_seconds", n_tokens)
        await message.answer(text="✅ Данные успешно обновлены!")


@admin.callback_query(AdminCheck(), F.data.startswith("change_gen_sec"))
async def change_gen_sec(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ChangeRate.waiting_for_n_generated_seconds)
    await callback.answer('')

    await callback.message.answer(text="Введите новое количество секунд на генерацию для тарифа:")


@admin.message(AdminCheck(), ChangeRate.waiting_for_n_generated_seconds)
async def get_new_change_gen_sec(message: Message, state: FSMContext):
    try:
        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Обновление данных тарифа остановлено")
            await state.clear()
            return

        n_tokens = float(message.text)

    except:
        await message.answer(
            "❌ Ошибка, количество секунд на генерацию должно быть целым или дробным числом, например: 1000"
            "\nВведите новое количество секунд на генерацию или скажите 'отмена'.")

    else:
        data = await state.get_data()
        rate = data["rate"]
        await state.clear()
        await db.set_rate_attribute(rate, "n_generated_seconds", n_tokens)
        await message.answer(text="✅ Данные успешно обновлены!")


@admin.callback_query(AdminCheck(), F.data == "add_rate")
async def add_rate_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.bot.delete_message(chat_id=callback_query.from_user.id,
                                            message_id=callback_query.message.message_id)

    await state.set_state(RateForm.waiting_for_name)
    m = await callback_query.message.answer("Введите название тарифа (название должно быть уникальным):")
    await state.update_data(id_for_delete=[m.message_id])


@admin.message(AdminCheck(), RateForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    try:
        name = message.text
        if name.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание нового тарифа остановлено")
            await state.clear()
            return

        if await db.check_if_rate_exists(name=name):
            raise
    except:
        m = await message.answer("❌ Ошибка, название тарифа должно быть уникальным")
        data = await state.get_data()
        ids = [message.message_id, m.message_id] + data["id_for_delete"]
        await state.update_data(id_for_delete=ids)

    else:
        await state.update_data(name=name)
        await state.set_state(RateForm.waiting_for_n_tokens)
        data = await state.get_data()
        m = await message.answer("Введите количество токенов для тарифа:")
        ids = [message.message_id, m.message_id] + data["id_for_delete"]

        await state.update_data(id_for_delete=ids)


@admin.message(AdminCheck(), RateForm.waiting_for_n_tokens)
async def process_n_tokens(message: Message, state: FSMContext):
    try:
        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание нового тарифа остановлено")
            await state.clear()
            return

        await state.update_data(n_tokens=int(message.text))

    except:
        m = await message.answer("❌ Ошибка, количество токенов должно быть целым числом, например: 10000")
        data = await state.get_data()
        ids = [message.message_id, m.message_id] + data["id_for_delete"]
        await state.update_data(id_for_delete=ids)

    else:
        await state.set_state(RateForm.waiting_for_n_transcribed_seconds)
        data = await state.get_data()
        m = await message.answer("Введите количество секунд на транскрипцию:")
        ids = [message.message_id, m.message_id] + data["id_for_delete"]

        await state.update_data(id_for_delete=ids)


@admin.message(AdminCheck(), RateForm.waiting_for_n_transcribed_seconds)
async def process_n_transcribed_seconds(message: Message, state: FSMContext):
    try:
        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание нового тарифа остановлено")
            await state.clear()
            return

        await state.update_data(n_transcribed_seconds=float(message.text))

    except:
        m = await message.answer("❌ Ошибка, количество секунд на транскрипцию должно быть "
                                 "целым числом или числом с плавающей точкой, например: 10000.0")
        data = await state.get_data()
        ids = [message.message_id, m.message_id] + data["id_for_delete"]
        await state.update_data(id_for_delete=ids)

    else:
        await state.set_state(RateForm.waiting_for_n_generated_seconds)
        data = await state.get_data()
        m = await message.answer("Введите количество секунд на генерацию:")
        ids = [message.message_id, m.message_id] + data["id_for_delete"]

        await state.update_data(id_for_delete=ids)


@admin.message(AdminCheck(), RateForm.waiting_for_n_generated_seconds)
async def process_n_generated_seconds(message: Message, state: FSMContext):
    try:

        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание нового тарифа остановлено")
            await state.clear()
            return

        await state.update_data(n_generated_seconds=float(message.text))

    except:
        m = await message.answer("❌ Ошибка, количество секунд на генерацию должно быть "
                                 "целым числом или числом с плавающей точкой, например: 10000.0")
        data = await state.get_data()
        ids = [message.message_id, m.message_id] + data["id_for_delete"]
        await state.update_data(id_for_delete=ids)

    else:
        await state.set_state(RateForm.waiting_for_price)
        data = await state.get_data()
        m = await message.answer("Введите цену тарифа:")
        ids = [message.message_id, m.message_id] + data["id_for_delete"]
        await state.update_data(id_for_delete=ids)


@admin.message(AdminCheck(), RateForm.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    try:
        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание нового тарифа остановлено")
            await state.clear()
            return

        await state.update_data(price=float(message.text))

    except:
        m = await message.answer("❌ Ошибка, количество токенов должно быть числом")
        data = await state.get_data()
        ids = [message.message_id, m.message_id] + data["id_for_delete"]
        await state.update_data(id_for_delete=ids)


    else:
        await state.set_state(RateForm.waiting_for_type)
        data = await state.get_data()
        m = await message.answer("Выберите тип тарифа ('месячный' или 'годовой'):",
                                 reply_markup=get_type_rate())
        ids = [message.message_id, m.message_id] + data["id_for_delete"]
        await state.update_data(id_for_delete=ids)


@admin.callback_query(AdminCheck(), RateForm.waiting_for_type, F.data.startswith("type_"))
async def process_type(message: CallbackQuery | Message, state: FSMContext):
    try:

        if isinstance(message, Message) and message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание нового тарифа остановлено")
            await state.clear()
            return

        if isinstance(message, CallbackQuery):
            type_ = message.data.split("_")[1]
        else:
            type_ = message.text

    except:
        if isinstance(message, CallbackQuery):
            m = await message.message.answer("❌ Ошибка, тип тарифа долже быть либо 'месячный' либо 'годовой'")
        else:
            m = await message.answer("❌ Ошибка, тип тарифа долже быть либо 'месячный' либо 'годовой'")
        data = await state.get_data()
        ids = [message.message_id, m.message_id] + data["id_for_delete"]
        await state.update_data(id_for_delete=ids)
    else:
        data = await state.get_data()
        await db.add_new_rate(
            name=data['name'],
            n_tokens=data['n_tokens'],
            n_transcribed_seconds=data['n_transcribed_seconds'],
            models="gpt-4o",
            n_generated_seconds=data['n_generated_seconds'],
            price=data['price'],
            type_=type_
        )
        await message.bot.delete_messages(chat_id=message.from_user.id,
                                          message_ids=data["id_for_delete"] + [message.message.message_id])

        await message.message.answer(text=f"✅ Новый тариф <i>{data['name']}</i>  добавлен",
                                     parse_mode="HTML")
        await state.clear()
        rates = await db.get_all_rates()

        await message.message.answer(text=ADMIN_RATE_TEXT,
                                     parse_mode="HTML",
                                     reply_markup=kb_rates_admin(rates).as_markup())


@admin.callback_query(F.data.startswith("edit_rate_"))
async def edit_rate_callback(callback_query: CallbackQuery):
    await callback_query.answer('')
    rate_name = callback_query.data.split("_")[2]
    rate = await db.get_rate_data(rate_name=rate_name)

    await callback_query.bot.edit_message_text(chat_id=callback_query.from_user.id,
                                               message_id=callback_query.message.message_id,
                                               text=await get_rate_data(rate),
                                               reply_markup=get_edit_rate_kb(rate["_id"]).as_markup(),
                                               parse_mode="HTML")


@admin.callback_query(F.data.startswith("delete_rate_"))
async def delete_rate_callback(callback_query: CallbackQuery):
    await callback_query.answer('')
    rate_name = callback_query.data.split("_")[2]
    await db.delete_rate(rate_name=rate_name)

    await callback_query.answer(f"Тариф {rate_name} удален")
    rates = await db.get_all_rates()
    await show_rates_admin(message=callback_query.message,
                           edit_id=callback_query.message.message_id,
                           text=ADMIN_RATE_TEXT,
                           rates=rates,
                           from_menu=True,
                           page=0)


@admin.message(AdminCheck(), Command("knowledge"))
@admin.callback_query(AdminCheck(), F.data == "add_knowledge")
async def adding_knowledge_handler(message: Message | CallbackQuery):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())

    if isinstance(message, Message):
        await message.answer(text=ADMIN_ADD_KNOWLEDGE_TEXT,
                             parse_mode="HTML",
                             reply_markup=kb_knowledge_admin().as_markup())

    else:
        await message.answer('')
        await message.bot.edit_message_text(chat_id=admin_id,
                                            message_id=message.message.message_id,
                                            text=ADMIN_ADD_KNOWLEDGE_TEXT,
                                            parse_mode="HTML",
                                            reply_markup=kb_knowledge_admin().as_markup()
                                            )


@admin.callback_query(AdminCheck(), F.data == "knowledge_youtube")
async def knowledge_youtube_handler(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(AddKnowledge.waiting_for_youtube)
    await callback_query.message.answer("<b>Введите ссылку на ютуб видео или плейлист:</b>",
                                        parse_mode="HTML")


@admin.message(AdminCheck(), AddKnowledge.waiting_for_youtube)
async def process_youtube(message: Message, state: FSMContext):
    try:
        y_link = message.text

        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание новых знаний остановлено")
            await state.clear()
            return

        placeholder_message = await message.answer("⏳ Подождите, запрос обрабатывается...",
                                                   parse_mode="HTML")
        await message.bot.send_chat_action(chat_id=message.from_user.id,
                                           action="typing")

        vs_id = await knowledge_loader.load_knowledge_youtube(url_youtube=y_link)


    except:
        await message.bot.edit_message_text(text="❌ Что-то пошло не так при обработке видео или плейлиста, "
                                                 "проверьте, является ли предоставленная ссылка youtube-ссылкой или "
                                                 "являются ли видео или плейлист публичными.\nОтправьте новую ссылку "
                                                 "или скажите 'Отмена'",
                                            chat_id=message.from_user.id,
                                            message_id=placeholder_message.message_id)

    else:
        await message.bot.edit_message_text(f"✅ Новые знания успешно добавлены!\nID знаний: {vs_id}",
                                            parse_mode="HTML",
                                            chat_id=message.from_user.id,
                                            message_id=placeholder_message.message_id)


@admin.callback_query(AdminCheck(), F.data == "knowledge_gdrive")
async def knowledge_gdrive_handler(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(AddKnowledge.waiting_for_gdrive)
    await callback_query.message.answer("<b>Введите ссылку на общедоступный файл или папку Гугл Диск:</b>",
                                        parse_mode="HTML")


@admin.message(AdminCheck(), AddKnowledge.waiting_for_gdrive)
async def process_gdrive(message: Message, state: FSMContext):
    try:
        g_link = message.text

        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание новых знаний остановлено")
            await state.clear()
            return

        placeholder_message = await message.answer("⏳ Подождите, запрос обрабатывается...",
                                                   parse_mode="HTML")
        await message.bot.send_chat_action(chat_id=message.from_user.id,
                                           action="typing")

        vs_id = await knowledge_loader.load_knowledge_gdrive(gdrive_url=g_link)

    except:
        await message.bot.delete_message(chat_id=message.from_user.id,
                                         message_id=placeholder_message.message_id)
        await message.bot.send_photo(chat_id=message.from_user.id,
                                     photo=FSInputFile(Config.gdrive_example_path),
                                     caption="❌ Произошла ошибка при обработке запроса, "
                                             "отправьте ссылку на общедоступный файл или папку с "
                                             "правами редактора или скажите 'Отмена'")

    else:
        await message.bot.edit_message_text(f"✅ Новые знания успешно добавлены!\nID знаний: {vs_id}",
                                            parse_mode="HTML",
                                            chat_id=message.from_user.id,
                                            message_id=placeholder_message.message_id)


@admin.callback_query(AdminCheck(), F.data == "knowledge_file")
async def knowledge_file_handler(callback_query: CallbackQuery, state: FSMContext):
    await state.set_state(AddKnowledge.waiting_for_file)
    await callback_query.message.answer("<b>Скиньте боту файл, который вы хотите загрузить в базу знаний:</b>",
                                        parse_mode="HTML")


@admin.message(AdminCheck(), AddKnowledge.waiting_for_file)
async def process_file(message: Message, state: FSMContext):
    try:
        file = message.document
        file_id = await message.bot.get_file(file_id=file.id)

        f_path = file_id.file_path
        f_data = io.BytesIO()
        await file.bot.download_file(file_path=f_path,
                                     destination=f_data)
        f_data.seek(0)

        placeholder_message = await message.answer("⏳ Подождите, запрос обрабатывается...",
                                                   parse_mode="HTML")
        await message.bot.send_chat_action(chat_id=message.from_user.id,
                                           action="typing")

        vs_id = await knowledge_loader.load_knowledge_file(file_data=f_data,
                                                           name_of_file=file.file_name)

    except:

        await message.bot.edit_message_text(text="❌ Произошла ошибка при обработке файла, возможно его "
                                                 "расширение не соответствует допустимым.\nПосмотреть допустимые "
                                                 'расширения на данный момент можно '
                                                 '<a href="https://platform.openai.com/docs/assistants/tools/file-search/supported-files">здесь</a> '
                                                 '(нужен VPN).',
                                            parse_mode="HTML",
                                            chat_id=message.from_user.id,
                                            message_id=placeholder_message.message_id)

    else:

        await message.bot.edit_message_text(f"✅ Новые знания успешно добавлены!\nID знаний: {vs_id}",
                                            parse_mode="HTML",
                                            chat_id=message.from_user.id,
                                            message_id=placeholder_message.message_id)


@admin.message(AdminCheck(), Command("partner"))
@admin.callback_query(AdminCheck(), F.data == "partner")
async def knowledge_partner_handler(callback_query: CallbackQuery | Message, state: FSMContext):
    await state.set_state(AddKnowledge.waiting_for_gdrive)
    if isinstance(callback_query, CallbackQuery):
        await callback_query.message.answer("<b>Введите ссылку на общедоступный файл или папку Гугл Диск:</b>",
                                            parse_mode="HTML")
    else:
        await callback_query.answer("<b>Введите ссылку на общедоступный файл или папку Гугл Диск:</b>",
                                    parse_mode="HTML")


@admin.message(AdminCheck(), AddPartner.waiting_for_link)
async def process_partner(message: Message, state: FSMContext):
    try:
        g_link = message.text
        if message.text.lower() in ["отмена", "стоп", "остановить"]:
            await message.answer(text="⛔ Создание новых партнерских знаний остановлено")
            await state.clear()
            return

        placeholder_message = await message.answer("⏳ Подождите, запрос обрабатывается...",
                                                   parse_mode="HTML")
        await message.bot.send_chat_action(chat_id=message.from_user.id,
                                           action="typing")

        vs_id = await knowledge_loader.load_partner(gdrive_url=g_link)

    except:

        await message.bot.delete_message(chat_id=message.from_user.id,
                                         message_id=placeholder_message.message_id)

        await message.answer_photo(photo=FSInputFile(path=Config.gdrive_example_path),
                                   caption="❌ Произошла ошибка при обработке запроса, "
                                           "отправьте ссылку на общедоступный файл или папку с "
                                           "правами редактора или скажите 'Отмена'")


    else:
        await message.bot.edit_message_text(f"✅ Новые знания успешно добавлены!\nID партнерских данных: {vs_id}",
                                            parse_mode="HTML",
                                            chat_id=message.from_user.id,
                                            message_id=placeholder_message.message_id)

        await state.clear()


@admin.message(AdminCheck(), Command("stats"))
@admin.callback_query(AdminCheck(), F.data == "stats")
async def get_admin_stats(message: Message | CallbackQuery):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())

    stats_data = await Stats(admin_id)
    stats_text = stats_data["text_stats"][0]
    data_point = stats_data["data"]

    if isinstance(message, Message):
        await message.answer(text=stats_text,
                             parse_mode="HTML",
                             reply_markup=kb_stats_admin(data_point).as_markup())

    else:
        await message.answer('')
        await message.bot.edit_message_text(chat_id=admin_id,
                                            message_id=message.message.message_id,
                                            text=stats_text,
                                            parse_mode="HTML",
                                            reply_markup=kb_stats_admin(data_point).as_markup()
                                            )


@admin.callback_query(AdminCheck(), F.data.startswith("stats_plot_"))
async def get_stats_plot_admin(message: CallbackQuery):
    admin_id = message.from_user.id

    data_ = message.data.split("_")[2]
    dir_ = f"../stats/plots/{data_}"  # os.path.join(Config.base_plot_path, data_)

    await message.answer(f"Данные на {data_}")

    for f_name in ["token_usage.png", "transcribed_seconds_usage.png",
                   "generate_seconds_usage.png", "subscription_rate.png"]:
        path = os.path.join(dir_, f_name)
        in_file = FSInputFile(path=path,
                              filename=f_name)
        await message.bot.send_document(chat_id=admin_id,
                                        document=in_file)


@admin.message(AdminCheck(), Command("cancel"))
async def cancel_handle_admin(message: Message):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())

    if admin_id in admin_tasks.keys():
        task = admin_tasks[admin_id]
        task.cancel()
    else:
        await message.answer(text="<i>Нечего останавливать...</i>",
                             parse_mode="HTML")


@admin.message(AdminCheck(), Command("retry"))
async def retry_handle_admin(message: Message):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())

    dialog_messages = await db.get_dialog_messages(admin_id, dialog_id=None)

    if len(dialog_messages) == 0:
        await message.answer(text="Нет сообщений для повтора 🤷‍♂️",
                             parse_mode="HTML")
        return

    last_dialog_message = dialog_messages.pop()
    await db.set_dialog_messages(admin_id, dialog_messages, dialog_id=None)

    message.text = last_dialog_message["user"]
    await _message_handle_admin(message=message,
                                use_new_dialog_timeout=False)


async def _voice_admin(message: Message):


    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())
    if await is_previous_message_not_answered_yet(message, admin_tasks):
        return

    voice = message.voice
    voice_file = await message.bot.get_file(voice.file_id)
    voice_path = voice_file.file_path

    buf = io.BytesIO()
    await message.bot.download_file(file_path=voice_path,
                                    destination=buf)
    buf.name = "voice.oga"
    buf.seek(0)

    try:
        transcribed_text = await openai_helper.transcribe(buf)
    except:
        await message.answer("❌ Хьюстон, у нас проблемы!\nЧто-то пошло не так при "
                             "обработке голоса!\nПопробуйте снова или обратитесь в тех. поддержку:",
                             reply_markup=get_help_keyboard(),
                             parse_mode="HTML")
    else:
        text = f"🎤: <code>{transcribed_text}</code>"
        await message.answer(text=text,
                             parse_mode="HTML")

        await db.update_spend(admin_id,
                              n_transcribed_seconds=voice.duration)

        await _message_handle_admin(message=message,
                                    context=text)
        # message handle


async def _file_analyze_admin(message: Message):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())
    if await is_previous_message_not_answered_yet(message, admin_tasks):
        return

    try:
        async with admin_semaphores[admin_id]:
            document = message.document
            file = await message.bot.get_file(document.file_id)
            file_path = file.file_path

            file_extension = os.path.splitext(document.file_name)[-1].lower()

            file_bytes = io.BytesIO()
            await message.bot.download_file(file_path=file_path,
                                            destination=file_bytes)
            file_bytes.seek(0)

            if file_extension == '.txt':
                content = file_bytes.read().decode('utf-8')
            elif file_extension == '.csv':
                content = await asyncio.get_running_loop().run_in_executor(executor, pd.read_csv, file_bytes)
                content = content.to_string()
            elif file_extension == '.docx':
                content = await asyncio.get_running_loop().run_in_executor(executor, extract_docx_text, file_bytes)
            elif file_extension == '.xlsx':
                content = await asyncio.get_running_loop().run_in_executor(executor, extract_xlsx_text, file_bytes)
            elif file_extension == '.pptx':
                content = await asyncio.get_running_loop().run_in_executor(executor, extract_pptx_text, file_bytes)
            elif file_extension == '.pdf':
                content = await asyncio.get_running_loop().run_in_executor(executor, extract_pdf_text, file_bytes)
            else:
                await message.answer("❌ Упс! Не поддерживаемый формат файла.\
                                     (Поддерживаются только '.docx', '.xlsx', '.pptx', '.pdf', '.csv', '.txt')")
                return

    except asyncio.CancelledError:
        await message.answer("✅ Обработка файла остановлена.",
                             parse_mode="HTML")

    except Exception as e:
        await message.answer("❌ Хьюстон, у нас проблемы!\nЧто-то пошло не так при \
                                            обработке файла!\nПопробуйте снова или обратитесь в тех. поддержку:",
                             reply_markup=get_help_keyboard(),
                             parse_mode="HTML")
    else:

        content = f"Данные из файла:\n{content[:4096]}"

        # message handle
        await _message_handle_admin(message=message,
                                    context=content)


async def _video_analyze_admin(message: Message):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())
    if await is_previous_message_not_answered_yet(message, admin_tasks):
        return

    video = message.video
    video_file = await message.bot.get_file(video.file_id)
    video_path = video_file.file_path

    buf = io.BytesIO()
    await message.bot.download_file(file_path=video_path,
                                    destination=buf)
    buf.name = "video.mp4"
    buf.seek(0)

    # message handle
    await _message_handle_admin(message=message,
                                video=buf)


async def _photo_analyze_admin(message: Message):
    admin_id = message.from_user.id
    await register_admin_in_db_as_user(message, admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())
    if await is_previous_message_not_answered_yet(message, admin_tasks):
        return

    photo = message.photo[-1]
    photo_file = await message.bot.get_file(photo.file_id)
    photo_path = photo_file.file_path

    async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix="." + photo_path.split(".")[-1]) as temp_photo:
        name = temp_photo.name

    await message.bot.download_file(file_path=photo_path,
                                    destination=name)
    # buf.name =

    # message handle
    await _message_handle_admin(message=message,
                                image=name)


async def _message_handle_admin(message: Message,
                                image: io.BytesIO = None,
                                video: io.BytesIO = None,
                                context: str = None,
                                use_new_dialog_timeout: bool = True):
    try:

        admin_id = message.from_user.id
        current_model = await db.get_user_attribute(admin_id, "current_model")
        if use_new_dialog_timeout:
            last_message = await db.get_dialog_last(user_id=admin_id)
            if (datetime.now() - last_message).seconds > \
                    Config.new_dialog_timeout and len(await db.get_dialog_messages(user_id=admin_id)) > 0:
                await db.start_new_dialog(admin_id)

                await message.answer(f"Начало нового диалога из-за тайм-аута ✅",
                                     parse_mode="HTML")

        await db.set_user_attribute(admin_id, "last_interaction", datetime.now())

        message_text = message.text
        if message_text == "" and image is None and video is None:
            await message.answer("🥲 Вы отправили <b>пустое сообщение</b>. Попробуйте снова!",
                                 parse_mode="HTML")
            return

        dialog_messages = await db.get_dialog_messages(admin_id, dialog_id=None)

        if context is not None:
            message_text = f"Контекст: {context}\nПользователь: {message_text}"

        placeholder_message = await message.answer("⏳ Подождите, пока нейросеть обработает ваш запрос",
                                                   parse_mode="HTML")
        await message.bot.send_chat_action(chat_id=admin_id,
                                           action="typing")

        answer, (n_input_tokens,
                 n_output_tokens), n_first_dialog_messages_removed, is_voice = await openai_helper.send_message_assistant(
            message=message_text,
            dialog_messages=dialog_messages,
            image_buffer=image,
            video_buffer=video
        )

        await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        # await db.update_n_used_tokens(admin_id, current_model, n_input_tokens, n_output_tokens)
        raise

    except Exception as e:
        logging.exception(e)
        await message.answer("❌  Хьюстон, у нас проблемы!\nЧто-то пошло не так при "
                             "обработке запроса!\nПопробуйте снова или обратитесь в тех. поддержку:",
                             reply_markup=get_help_keyboard(),
                             parse_mode="HTML")
    else:

        if is_voice:

            await message.bot.delete_message(chat_id=admin_id,
                                             message_id=placeholder_message.message_id)

            audio_path, gen_second = await openai_helper.generate_speech(text=answer)

            await message.bot.send_voice(
                chat_id=admin_id,
                voice=audio_path,
                reply_markup=get_feed_kb(user_id=admin_id,
                                         dialog_id=await db.get_user_attribute(user_id=admin_id,
                                                                               key="current_dialog_id")))
            await db.update_spend(user_id=admin_id,
                                  n_generate_seconds=gen_second)

        else:

            await message.bot.edit_message_text(
                text=answer,
                chat_id=admin_id,
                message_id=placeholder_message.message_id,
                parse_mode="HTML",
                reply_markup=get_feed_kb(user_id=admin_id,
                                         dialog_id=await db.get_user_attribute(user_id=admin_id,
                                                                               key="current_dialog_id")))

        new_dialog_message = {"user": [{"type": "text",
                                        "text": message_text}],
                              "bot": answer,
                              "date": datetime.now(),
                              "feed": None}
        dialog_messages = await db.get_dialog_messages(admin_id, dialog_id=None)

        dialog_messages = dialog_messages[n_first_dialog_messages_removed:] + [new_dialog_message]

        await db.set_dialog_messages(
            user_id=admin_id,
            dialog_messages=dialog_messages,
            dialog_id=None
        )
        await db.update_spend(user_id=admin_id,
                              n_used_tokens=n_input_tokens + n_output_tokens)

        old_spend_token = await db.get_user_attribute(admin_id, "n_used_tokens")
        old_spend_token["n_input_tokens"] += n_input_tokens
        old_spend_token["n_output_tokens"] += n_output_tokens

        await db.set_user_attribute(admin_id, "n_used_tokens", old_spend_token)

        # await db.update_n_used_tokens(admin_id, current_model, n_input_tokens, n_output_tokens)

        if n_first_dialog_messages_removed > 0:
            if n_first_dialog_messages_removed == 1:
                text = "📝️ <i>Уведомление:</i> Ваш текущий диалог слишком большой, ваше <b>первое сообщение</b> " \
                       "было удалено из контекста.\n Отправьте команду /new чтобы создать новый диалог."
            else:
                text = f"📝️ <i>Уведомление:</i> Ваш текущий диалог " \
                       f"слишком большой, ваши <b>{n_first_dialog_messages_removed} " \
                       f"первые сообщения</b> были удалены из контекста.\n " \
                       f"Отправьте команду /new чтобы создать новый диалог."
            await message.answer(text, parse_mode="HTML")


@admin.callback_query(AdminCheck(), F.data.startswith("good_"))
async def good_answer_handle(callback: CallbackQuery):
    await callback.answer("Вы пометили этот ответ хорошим\nСпасибо за обратную связь!")

    dialog_id = callback.data.split("_")[1] or None

    await db.set_feedback(user_id=callback.from_user.id,
                          dialog_id=dialog_id,
                          feed=True)


@admin.callback_query(AdminCheck(), F.data.startswith("bad_"))
async def bad_answer_handle(callback: CallbackQuery):
    await callback.answer("Вы пометили этот ответ плохим\nСпасибо за обратную связь!")

    dialog_id = callback.data.split("_")[1] or None

    await db.set_feedback(user_id=callback.from_user.id,
                          dialog_id=dialog_id,
                          feed=True)


@admin.message(AdminCheck(), F.in_([F.text, F.photo, F.video, F.document, F.voice]))
async def main_message_admin_handle(message: Message):
    admin_id = message.from_user.id

    await register_admin_in_db_as_user(message=message,
                                       admin_semaphores=admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())
    if await is_previous_message_not_answered_yet(message, admin_tasks):
        return

    async with admin_semaphores[admin_id]:
        if message.photo:
            task = asyncio.create_task(
                _photo_analyze_admin(message)
            )
        elif message.video:
            task = asyncio.create_task(
                _video_analyze_admin(message)
            )

        elif message.document:
            task = asyncio.create_task(
                _file_analyze_admin(message)
            )

        elif message.voice:
            task = asyncio.create_task(
                _voice_admin(message)
            )
        else:
            task = asyncio.create_task(
                _message_handle_admin(message)
            )

        admin_tasks[admin_id] = task

        try:
            await task
        except asyncio.CancelledError:
            await message.answer("✅ Остановлен",
                                 parse_mode="HTML")
        else:
            pass
        finally:
            if admin_id in admin_tasks:
                del admin_tasks[admin_id]


@admin.message(AdminCheck(), Command("new"))
@admin.callback_query(AdminCheck(), F.data == "clear")
async def clear_dialogs(message: CallbackQuery | Message):
    admin_id = message.from_user.id
    if isinstance(message, CallbackQuery):
        await message.answer('')

    await register_admin_in_db_as_user(message=message,
                                       admin_semaphores=admin_semaphores)

    await db.set_user_attribute(admin_id, "last_interaction", datetime.now())
    if await is_previous_message_not_answered_yet(message, admin_tasks):
        return

    await db.set_user_attribute(admin_id, "current_model", "gpt-4o")

    await db.start_new_dialog(user_id=admin_id)
    await message.bot.send_message(chat_id=admin_id,
                                   text="✅ Начало нового диалога",
                                   parse_mode="HTML")
