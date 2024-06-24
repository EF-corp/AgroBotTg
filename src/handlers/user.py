import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from src.database import DataBase as db
from src.config import Config
from src.filters import UserCheck
from src.nn import OpenAIHelper
from src.utils import HELP_MESSAGE, is_previous_message_not_answered_yet, \
    Stats, register_user, \
    MENU_TEXT, get_user_balance, \
    get_rate_data, RATE_TEXT, \
    ADD_SUBSCRIBE, is_phone, \
    process_phone
from src.utils.general import extract_docx_text, extract_pdf_text, \
    extract_pptx_text, extract_xlsx_text
from src.keyboards import get_help_keyboard, get_document_kb, \
    get_feed_kb, get_user_menu_kb, \
    get_user_sub_menu, get_user_stats_kb, \
    get_user_balance_kb, get_user_rate_kb, \
    get_adds_kb
from src.commands.user import set_user_commands_menu
from src.handlers.states import UserPhone
from src.web_callback.payment.accept_payment import accept_new_rec_pay

from datetime import datetime
import asyncio
import io
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

user = Router()

user_tasks = {}
user_semaphores = {}

openai_helper = OpenAIHelper()
executor = ThreadPoolExecutor()


@user.message(UserCheck(), CommandStart())
async def start_user_handle(message: Message):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)
    await db.start_new_dialog(user_id)

    await set_user_commands_menu(bot=message.bot,
                                 user_id=user_id)

    reply_text = "👋 Привет! Я АгроБот 🌱, твой помощник в мире растений! \n\n"
    reply_text += HELP_MESSAGE

    await message.answer(text=reply_text,
                         parse_mode="HTML",
                         reply_markup=get_document_kb())


@user.message(UserCheck(), Command("help"))
@user.callback_query(UserCheck(), F.data == "user_help")
async def help_user_handle(message: Message | CallbackQuery):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)

    if isinstance(message, CallbackQuery):
        await message.answer('')
        await message.bot.send_message(chat_id=user_id,
                                       text=HELP_MESSAGE,
                                       parse_mode="HTML",
                                       reply_markup=get_help_keyboard())
    else:
        await message.answer(text=HELP_MESSAGE,
                             parse_mode="HTML",
                             reply_markup=get_help_keyboard())


@user.message(UserCheck(), Command("offer"))
@user.callback_query(UserCheck(), F.data == "doc_ofert")
async def offer_user_handler(message: Message | CallbackQuery):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)

    if isinstance(message, CallbackQuery):
        await message.answer('')

    document = FSInputFile(path=Config.offer_doc_path)

    await message.bot.send_document(chat_id=user_id,
                                    document=document,
                                    caption="Договор Оферты")


@user.message(UserCheck(), Command("menu"))
@user.callback_query(UserCheck(), F.data == "user_menu")
async def user_menu_handle(message: Message | CallbackQuery):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)

    if isinstance(message, CallbackQuery):
        await message.answer('')

        await message.bot.edit_message_text(
            text=MENU_TEXT,
            chat_id=user_id,
            message_id=message.message.message_id,
            parse_mode="HTML",
            reply_markup=get_user_menu_kb().as_markup()
        )

    else:
        await message.bot.send_message(
            text=MENU_TEXT,
            chat_id=user_id,
            parse_mode="HTML",
            reply_markup=get_user_menu_kb().as_markup()
        )


@user.message(UserCheck(), Command("stats"))
@user.callback_query(UserCheck(), F.data == "user_stats_menu")
async def user_stats_handle(message: Message | CallbackQuery):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)

    stats_text = await Stats(user_id)

    if isinstance(message, CallbackQuery):
        await message.answer('')
        await message.bot.edit_message_text(
            text=stats_text,
            chat_id=user_id,
            message_id=message.message.message_id,
            parse_mode="HTML",
            reply_markup=get_user_stats_kb().as_markup()
        )

    else:
        await message.bot.send_message(
            text=stats_text,
            chat_id=user_id,
            parse_mode="HTML",
            reply_markup=get_user_stats_kb().as_markup()
        )


@user.message(UserCheck(), Command("balance"))
@user.callback_query(UserCheck(), F.data == "user_balance_menu")
async def user_stats_handle(message: Message | CallbackQuery):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)

    balance_data = await get_user_balance(user_id=user_id)
    user_rate = await db.get_user_attribute(user_id, "rate")

    if isinstance(message, CallbackQuery):
        await message.answer('')
        await message.bot.edit_message_text(
            text=balance_data,
            chat_id=message.message.chat.id,
            message_id=message.message.message_id,
            parse_mode="HTML",
            reply_markup=get_user_balance_kb(user_rate=user_rate).as_markup()
        )

    else:
        await message.bot.send_message(
            text=balance_data,
            chat_id=message.chat.id,
            parse_mode="HTML",
            reply_markup=get_user_balance_kb(user_rate=user_rate).as_markup()
        )


@user.message(UserCheck(), Command("my_tariff"))
@user.callback_query(UserCheck(), F.data.startswith("buy_rate_"))
async def user_buy_rate_handle(message: Message | CallbackQuery):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)
    user_rate = await db.get_user_attribute(user_id=user_id,
                                            key="rate")
    if isinstance(message, Message):

        user_has_premium = user_rate != "free"
    else:
        user_rate_callback = message.data.split("_")[2]
        user_has_premium = (user_rate == user_rate_callback)
        user_rate = user_rate_callback

    rate_data = await db.get_rate_data(rate_name=user_rate)
    rate_text = await get_rate_data(rate_data=rate_data)

    if isinstance(message, Message):

        await message.bot.send_message(
            text=rate_text,
            chat_id=user_id,
            parse_mode="HTML",
            reply_markup=get_user_rate_kb(rate_name=user_rate,
                                          has_premium=user_has_premium).as_markup()
        )

    else:
        await message.answer('')
        await message.bot.edit_message_text(
            text=rate_text,
            chat_id=user_id,
            message_id=message.message.message_id,
            parse_mode="HTML",
            reply_markup=get_user_rate_kb(rate_name=user_rate,
                                          has_premium=user_has_premium).as_markup()
        )


@user.message(UserCheck(), Command("tariffs"))
@user.callback_query(UserCheck(), F.data == "sub_user")
async def user_sub_handle(message: Message | CallbackQuery):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)

    rates = await db.get_all_rates()

    if isinstance(message, Message):
        await message.bot.send_message(
            chat_id=user_id,
            text=RATE_TEXT,
            parse_mode="HTML",
            reply_markup=get_user_sub_menu(rates=rates,
                                           from_menu=True).as_markup()
        )

    else:
        await message.answer('')
        await message.bot.edit_message_text(
            text=RATE_TEXT,
            chat_id=user_id,
            message_id=message.message.message_id,
            parse_mode="HTML",
            reply_markup=get_user_sub_menu(rates=rates,
                                           from_menu=True).as_markup()
        )


@user.callback_query(UserCheck(), F.data.startswith("prev_rate_"))
async def rate_prev_page_handler(callback: CallbackQuery):
    await callback.answer('')
    page = int(callback.data.split("_")[2])

    rates = await db.get_all_rates()
    page -= 1
    if page < 0:
        return

    await callback.bot.edit_message_text(chat_id=callback.from_user.id,
                                         message_id=callback.message.message_id,
                                         text=RATE_TEXT,
                                         parse_mode="HTML",
                                         reply_markup=get_user_sub_menu(rates=rates,
                                                                        page=page,
                                                                        from_menu=True).as_markup()
                                         )


@user.callback_query(UserCheck(), F.data.startswith("next_rate_"))
async def rate_next_page_handler(callback: CallbackQuery):
    await callback.answer('')
    page = int(callback.data.split("_")[2])

    rates = await db.get_all_rates()
    page += 1
    if page >= len(rates) / Config.n_rate_per_page:
        return

    await callback.bot.edit_message_text(chat_id=callback.from_user.id,
                                         message_id=callback.message.message_id,
                                         text=RATE_TEXT,
                                         parse_mode="HTML",
                                         reply_markup=get_user_sub_menu(rates=rates,
                                                                        page=page,
                                                                        from_menu=True).as_markup()
                                         )


@user.callback_query(UserCheck(), F.data.startswith("buying_rate_"))
async def user_buying_rate_handle(callback: CallbackQuery, state: FSMContext):
    await callback.answer('')

    user_id = callback.from_user.id
    rate = callback.data[2]

    if await db.get_user_attribute(user_id, "phone") is None:
        await state.set_state(UserPhone.waiting_for_user_phone)
        await state.update_data(rate=rate)
        await callback.message.answer(text="Введите свой номер телефона:")
        return
    try:
        await accept_new_rec_pay(message=callback.message,
                                 rate_name=rate)
    except:
        await callback.message.answer(text="Что-то пошло не так при обработке оплаты, "
                                           "попробуйте заново, или обратитесь в тех. поддержку ниже:",
                                      reply_markup=get_help_keyboard())


@user.message(UserCheck(), UserPhone.waiting_for_user_phone)
async def get_user_phone(message: Message, state: FSMContext):
    try:
        phone = message.text
        user_id = message.from_user.id
        if await is_phone(phone):
            phone = await process_phone(phone)
            await db.set_user_attribute(user_id, "phone", phone)
        else:
            raise

    except:
        await message.answer(text="Введите корректный номер телефона для регистрации")

    else:
        state_data = await state.get_data()
        rate = state_data["rate"]
        await state.clear()

        try:
            await accept_new_rec_pay(message=message,
                                     rate_name=rate)
        except:
            await message.answer(text="Что-то пошло не так при обработке оплаты, попробуйте заново, или "
                                      "обратитесь в тех. поддержку ниже:",
                                 reply_markup=get_help_keyboard())


@user.callback_query(UserCheck(), F.data.startswith("cancel_rate"))
async def user_cancel_rate_handle(callback: CallbackQuery):
    await callback.answer('')

    user_id = callback.from_user.id
    await register_user(message=callback, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)

    if await is_previous_message_not_answered_yet(callback, user_tasks):
        return

    await db.set_user_attribute(user_id, "rate", "free")

    await callback.bot.send_message(
        chat_id=user_id,
        text="Ваш тарифный план успешно отменён!"
    )

    await db.update_user(user_id=user_id)


@user.message(UserCheck(), Command("new"))
@user.callback_query(UserCheck(), F.data == "clear")
async def clear_dialogs(message: CallbackQuery | Message):
    user_id = message.from_user.id

    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)
    if await is_previous_message_not_answered_yet(message, user_tasks):
        return

    await db.set_user_attribute(user_id, "current_model", "gpt-4o")

    await db.start_new_dialog(user_id=user_id)
    if isinstance(message, CallbackQuery):
        await message.answer('')
        await message.bot.send_message(chat_id=user_id,
                                       text="🔄 Начало нового диалога",
                                       parse_mode="HTML")
    else:
        await message.answer(text="🔄 Начало нового диалога",
                             parse_mode="HTML")


async def _voice_user(message: Message):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)
    if await is_previous_message_not_answered_yet(message, user_tasks):
        return

    voice = message.voice
    voice_file = await message.bot.get_file(voice.file_id)
    voice_path = voice_file.file_path

    if await db.get_user_attribute(user_id=user_id, key="n_transcribed_seconds") < voice.duration:
        await message.answer(
            text=ADD_SUBSCRIBE,
            parse_mode="HTML",
            reply_markup=get_adds_kb()
        )
        return

    buf = io.BytesIO()
    await message.bot.download_file(file_path=voice_path,
                                    destination=buf)
    buf.name = "voice.oga"
    buf.seek(0)

    try:
        transcribed_text = openai_helper.transcribe(buf)
    except:
        await message.answer("❌  Хьюстон, у нас проблемы!\nЧто-то пошло не так при \
                                            обработке голоса!\nПопробуйте снова или обратитесь в тех. поддержку:",
                             reply_markup=get_help_keyboard(),
                             parse_mode="HTML")
    else:
        text = f"🎤: <i>{transcribed_text}</i>"
        await message.answer(text=text,
                             parse_mode="HTML")

        await db.update_spend(user_id=user_id,
                              n_transcribed_seconds=voice.duration)
        # message handle
        await _message_handle_user(message=message,
                                   context=text)


async def _file_analyze_user(message: Message):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)
    if await is_previous_message_not_answered_yet(message, user_tasks):
        return

    try:
        async with user_semaphores[user_id]:
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
                await message.answer("❌  Упс! Не поддерживаемый формат файла.\
                                     (Поддерживаются только '.docx', '.xlsx', '.pptx', '.pdf', '.csv', '.txt')")
                return

    except asyncio.CancelledError:
        await message.answer("⛔ Обработка файла остановлена.",
                             parse_mode="HTML")

    except Exception as e:
        await message.answer("❌  Хьюстон, у нас проблемы!\nЧто-то пошло не так при \
                                            обработке файла!\nПопробуйте снова или обратитесь в тех. поддержку:",
                             reply_markup=get_help_keyboard(),
                             parse_mode="HTML")
    else:

        content = f"Данные из файла:\n{content[:4096]}"

        # message handle
        await _message_handle_user(message=message,
                                   context=content)


async def _video_analyze_user(message: Message):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)
    if await is_previous_message_not_answered_yet(message, user_tasks):
        return

    video = message.video
    video_file = await message.bot.get_file(video.file_id)
    video_path = video_file.file_path

    if video.duration > 60:
        await message.answer(text="❌  Извините, видео слишком большое, обрежьте видео или отправьте другое.")
        return

    buf = io.BytesIO()
    await message.bot.download_file(file_path=video_path,
                                    destination=buf)
    buf.name = "video.mp4"
    buf.seek(0)

    # message handle
    await _message_handle_user(message=message,
                               video=buf)


async def _photo_analyze_user(message: Message):
    user_id = message.from_user.id
    await register_user(message=message, user_semaphores=user_semaphores)

    await db.update_user(user_id=user_id)
    if await is_previous_message_not_answered_yet(message, user_tasks):
        return

    photo = message.photo[-1]
    photo_file = await message.bot.get_file(photo.file_id)
    photo_path = photo_file.file_path

    buf = io.BytesIO()
    await message.bot.download_file(file_path=photo_path,
                                    destination=buf)
    buf.name = "photo.jpg"
    buf.seek(0)

    # message handle
    await _message_handle_user(message=message,
                               image=buf)


async def _message_handle_user(message: Message,
                               image: io.BytesIO = None,
                               video: io.BytesIO = None,
                               context: str = None,
                               use_new_dialog_timeout: bool = True):
    try:

        user_id = message.from_user.id
        current_model = await db.get_user_attribute(user_id, "current_model")
        if use_new_dialog_timeout:
            if (datetime.now() - await db.get_user_attribute(user_id, "last_interaction")).seconds > \
                    Config.new_dialog_timeout and len(await db.get_dialog_messages(user_id=user_id)) > 0:
                await db.start_new_dialog(user_id)

                await message.answer(f"🔄 Начало нового диалога из-за тайм-аута ",
                                     parse_mode="HTML")

        await db.update_user(user_id=user_id)

        message_text = "" or message.text
        if message_text == "" and image is None and video is None and context is None:
            await message.answer("🥲 Вы отправили <b>пустое сообщение</b>. Попробуйте снова!",
                                 parse_mode="HTML")
            return

        dialog_messages = await db.get_dialog_messages(user_id, dialog_id=None)

        if context is not None:
            message_text = f"Контекст: {context}\nПользователь: {message_text}"

        placeholder_message = await message.answer("⏳ Подождите, пока нейросеть обработает ваш запрос...",
                                                   parse_mode="HTML")
        await message.bot.send_chat_action(chat_id=user_id,
                                           action="typing")

        answer, (n_input_tokens, n_output_tokens), n_first_dialog_messages_removed, is_voice = await openai_helper.send_message_assistant(
            message=message_text,
            dialog_messages=dialog_messages,
            image_buffer=image,
            video_buffer=video
        )

        await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        # await db.update_n_used_tokens(user_id, current_model, n_input_tokens, n_output_tokens)
        raise

    except Exception as e:

        await message.answer("❌  Хьюстон, у нас проблемы!\nЧто-то пошло не так при \
                            обработке запроса!\nПопробуйте снова или обратитесь в тех. поддержку:",
                             reply_markup=get_help_keyboard(),
                             parse_mode="HTML")
    else:

        if is_voice:

            if await db.get_user_attribute(user_id=user_id, key="n_generate_seconds") <= 0:
                await message.answer(
                    text=ADD_SUBSCRIBE,
                    parse_mode="HTML",
                    reply_markup=get_adds_kb()
                )
                await message.bot.edit_message_text(
                    text=f"💬 Текстовый ответ: \n{answer}",
                    chat_id=user_id,
                    message_id=placeholder_message.message_id,
                    parse_mode="MARKDOWN",
                    reply_markup=get_feed_kb(user_id=user_id,
                                             dialog_id=await db.get_user_attribute(user_id=user_id,
                                                                                   key="current_dialog_id")))
            else:
                await message.bot.delete_message(chat_id=user_id,
                                                 message_id=placeholder_message.message_id)

                audio_path, gen_second = await openai_helper.generate_speech(text=answer)

                await message.bot.send_voice(
                    chat_id=user_id,
                    voice=audio_path,
                    reply_markup=get_feed_kb(user_id=user_id,
                                             dialog_id=await db.get_user_attribute(user_id=user_id,
                                                                                   key="current_dialog_id")))
                await db.update_spend(user_id=user_id,
                                      n_generate_seconds=gen_second)

        else:

            await message.bot.edit_message_text(
                text=answer,
                chat_id=user_id,
                message_id=placeholder_message.message_id,
                parse_mode="MARKDOWN",
                reply_markup=get_feed_kb(user_id=user_id,
                                         dialog_id=await db.get_user_attribute(user_id=user_id,
                                                                               key="current_dialog_id")))

        new_dialog_message = {"user": [{"type": "text",
                                        "text": message_text}],
                              "bot": answer,
                              "date": datetime.now(),
                              "feed": None}

        await db.set_dialog_messages(
            user_id=user_id,
            dialog_messages=await db.get_dialog_messages(user_id,
                                                         dialog_id=None)[n_first_dialog_messages_removed:].append(
                new_dialog_message),
            dialog_id=None
        )
        await db.update_spend(user_id=user_id,
                              n_used_tokens=n_input_tokens + n_output_tokens)
        # await db.update_n_used_tokens(user_id, current_model, n_input_tokens, n_output_tokens)

        if n_first_dialog_messages_removed > 0:
            if n_first_dialog_messages_removed == 1:
                text = "📝️ <i>Уведомление:</i> Ваш текущий диалог слишком большой, ваше <b>первое сообщение</b> \
                было удалено из контекста.\n Отправьте команду /new чтобы создать новый диалог."
            else:
                text = f"📝️ <i>Уведомление:</i> Ваш текущий диалог \
                слишком большой, ваши <b>{n_first_dialog_messages_removed} \
                первые сообщения</b> были удалены из контекста.\n Отправьте команду /new чтобы создать новый диалог."
            await message.answer(text, parse_mode="HTML")


@user.callback_query(UserCheck(), F.data.startswith("good_"))
async def good_answer_handle(callback: CallbackQuery):
    await callback.answer("👍 Вы пометили этот ответ хорошим\nСпасибо за обратную связь!")

    dialog_id = callback.data.split("_")[1] or None

    await db.set_feedback(user_id=callback.from_user.id,
                          dialog_id=dialog_id,
                          feed=True)


@user.callback_query(UserCheck(), F.data.startswith("bad_"))
async def bad_answer_handle(callback: CallbackQuery):
    await callback.answer("👎 Вы пометили этот ответ плохим\nСпасибо за обратную связь!")

    dialog_id = callback.data.split("_")[1] or None

    await db.set_feedback(user_id=callback.from_user.id,
                          dialog_id=dialog_id,
                          feed=True)


@user.message(UserCheck(), F.in_([F.text, F.photo, F.video, F.document, F.voice]))
async def main_message_user_handle(message: Message):
    user_id = message.from_user.id

    await register_user(message=message,
                        user_semaphores=user_semaphores)

    await db.set_user_attribute(user_id, "last_interaction", datetime.now())
    if await is_previous_message_not_answered_yet(message, user_tasks):
        return

    if await db.get_user_attribute(user_id, "n_tokens") <= 0:
        await message.answer(
            text=ADD_SUBSCRIBE,
            parse_mode="HTML",
            reply_markup=get_adds_kb()
        )
        return

    async with user_semaphores[user_id]:
        if message.photo:
            task = asyncio.create_task(
                _photo_analyze_user(message)
            )
        elif message.video:
            task = asyncio.create_task(
                _video_analyze_user(message)
            )

        elif message.document:
            task = asyncio.create_task(
                _file_analyze_user(message)
            )

        elif message.voice:
            task = asyncio.create_task(
                _voice_user(message)
            )
        else:
            task = asyncio.create_task(
                _message_handle_user(message)
            )

        user_tasks[user_id] = task

        try:
            await task
        except asyncio.CancelledError:
            await message.answer("⛔ Обработка запроса остановлена",
                                 parse_mode="HTML")
        else:
            pass
        finally:
            if user_id in user_tasks:
                del user_tasks[user_id]


@user.message(UserCheck(), Command("cancel"))
async def cancel_handle_admin(message: Message):
    user_id = message.from_user.id
    await register_user(message, user_semaphores)

    await db.set_user_attribute(user_id, "last_interaction", datetime.now())

    if user_id in user_tasks.keys():
        task = user_tasks[user_id]
        task.cancel()
    else:
        await message.answer(text="<i>Нечего останавливать...</i>",
                             parse_mode="HTML")
