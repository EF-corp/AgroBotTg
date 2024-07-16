from src.config import Config
import openai
import tiktoken
from src.database import DataBase as db
import io
import logging
from src.nn.get_diseases import get_diseases_tg
import httpx
from moviepy.editor import VideoFileClip
import cv2
from concurrent.futures import ThreadPoolExecutor
import asyncio
import base64
import aiofiles
import aiofiles.os
from typing import List, Optional
import json
from tinytag import TinyTag


class OpenAIHelper:
    def __init__(self) -> None:
        proxy = Config.proxies
        if proxy is not None:
            self.http_client = httpx.AsyncClient(proxies=proxy)
            self.client = openai.AsyncOpenAI(api_key=Config.openai_api_key, http_client=self.http_client)
        else:
            self.client = openai.AsyncOpenAI(api_key=Config.openai_api_key)
        self.executor_pool = ThreadPoolExecutor()
        self.OPENAI_COMPLETION_OPTIONS = {
            'temperature': 0.55,
            'top_p': 1,
            'frequency_penalty': 0,
            'presence_penalty': 0,
            'request_timeout': 60.0
        }
        self.assistant_id = Config.assistant_id
        self.assistant_partner = Config.assistant_partner_id
        self.serp_api_key = Config.serp_api_key
        self.tools_dict = {
            "get_answer_web": self.get_answer_web,
        }
        self.partner_extend_prompt = Config.partner_extend_prompt

    async def search_google(self, queries: List[str]):
        async with httpx.AsyncClient() as client:
            tasks = []
            for query in queries:
                params = {
                    "engine": "google",
                    "q": query,
                    "api_key": self.serp_api_key,
                    "num": 10
                }
                tasks.append(client.get("https://serpapi.com/search", params=params, timeout=None))

            responses = await asyncio.gather(*tasks)

            results = []
            for response in responses:
                response.raise_for_status()
                results.append(response.json().get('organic_results', []))

            return results

    async def get_answer_web(self, query: List[str]):
        search_results_list = await self.search_google(query)
        context = ""

        for search_results in search_results_list:
            for result in search_results:
                url = result.get('link')
                title = result.get('title')
                snippet = result.get('snippet')
                context += f"Заголовок: {title}\nИнформация: {snippet}\nРесурс [URL]: {url}\n\n"

        search_prompt = "Ты бот для ответа на вопросы при помощи поиска в интернете. " \
                        "Тебе дан контекст, а ты должен максимально подробно и " \
                        "точно ответить на вопрос пользователя и дать ссылку на товар или услугу."

        context = f"{search_prompt} Контекст: \n{context}"
        return context

    async def generate_speech(self, text: str):

        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice="onyx",
                input=text,
                response_format='opus'
            )

            temp_file = io.BytesIO()
            temp_file.write(response.read())
            temp_file.seek(0)

            async with aiofiles.tempfile.NamedTemporaryFile(suffix=".opus", delete=False) as tmp:
                await tmp.write(temp_file.read())
                temp_file.seek(0)
                temp_file_path = tmp.name

            audio_segment = await asyncio.get_running_loop().run_in_executor(self.executor_pool, TinyTag.get,
                                                                             temp_file_path)

            audio_length_seconds = float(audio_segment.duration)

            return temp_file_path, round(audio_length_seconds, 1)

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

    async def transcribe(self, file: io.BytesIO):

        try:
            # with open(file, "rb") as audio:
            file.seek(0)  # Reset the file pointer to the beginning
            file.name = "temp.mp3"
            audio_content = file.read()
            prompt_text = ""
            result = await self.client.audio.transcriptions.create(model="whisper-1",
                                                                   file=("temp." + "mp3", audio_content, "audio/mp3"),
                                                                   prompt=prompt_text)
            # print(result.text)
            return result.text

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

    async def _get_frames_audio_from_video(self, video_data: io.BytesIO, seconds_per_frame: int = 1):
        try:
            base64Frames = []
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
                await temp_video.write(video_data.getvalue())
                name = temp_video.name

            video = cv2.VideoCapture(name)

            total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = video.get(cv2.CAP_PROP_FPS)
            frames_to_skip = int(fps * seconds_per_frame)
            curr_frame = 0

            loop = asyncio.get_event_loop()
            while curr_frame < total_frames - 1:
                video.set(cv2.CAP_PROP_POS_FRAMES, curr_frame)
                success, frame = await loop.run_in_executor(self.executor_pool, video.read)
                if not success:
                    break
                _, buffer = cv2.imencode(".jpg", frame)
                base64Frames.append(base64.b64encode(buffer).decode("utf-8"))
                curr_frame += frames_to_skip
            video.release()
            audio_data = io.BytesIO()

            def _get_audio(path_video, _data: io.BytesIO):
                clip = VideoFileClip(path_video)
                clip.audio.write_audiofile(_data, codec="mp3", bitrate="32k")
                clip.audio.close()
                clip.close()
                _data.seek(0)

            await loop.run_in_executor(self.executor_pool, _get_audio, name, audio_data)
            await aiofiles.os.remove(name)

            return base64Frames, audio_data

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

    @staticmethod
    async def is_need_voice_message(message: str):

        message = [
            {
                "role": "system",
                "content": """Ты высокоскоростной ассистент, твоя задача определять, 
подразумевает ли пользователь ответ голосом или нет.\n
В результате своей работы ты должен возвращать 0 или 1 в 
зависимости требуется или нет ответ голосом.\n
Например на сообщений 'Как избавиться от клеща, ответь голосом' 
ты должен вернуть '1', а на сообщение 'Как избавиться от клеща' верни '0'."""},
            {
                "role": "user",
                "content": message if message is not None else "Нет сообщения"
            }
        ]
        return message

    async def is_need_voice(self, message: str, model: str = "gpt-3.5-turbo"):
        answer = None
        while answer is None:
            try:

                if message == "":
                    return False

                message = await self.is_need_voice_message(message)
                print(message)

                r = await self.client.chat.completions.create(
                    model=model,
                    messages=message,
                    temperature=0.0
                )
                answer = r.choices[0].message.content

                return bool(int(answer)) if answer in ["0", "1"] else False

                # n_input_tokens, n_output_tokens = r_gen.usage.prompt_tokens, r_gen.usage.completion_tokens

            except Exception as e:
                logging.exception(e)
                raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

    async def analyze_video(self, video: io.BytesIO, message: str = "", model: str = "gpt-4o"):

        frames, audio_buf = await self._get_frames_audio_from_video(video)
        text_from_audio = await self.transcribe(audio_buf)
        is_voice = False

        if message is not None:
            is_voice = await self.is_need_voice(message)
        messages = [
            {"role": "system",
             "content": "Ты передовой бот для анализа и ответа на вопросы на основе видео. Отвечай в формате Markdown"},
            {"role": "user", "content": [
                "Вот кадры из видео:",
                *map(lambda x: {"type": "image_url",
                                "image_url": {"url": f'data:image/jpg;base64,{x}', "detail": "low"}}, frames),
                {"type": "text", "text": f"Текст из видео: {text_from_audio}"},
                {"type": "text", "text": f"Пользователь: {message}"}
            ],
             }
        ]

        r = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            **self.OPENAI_COMPLETION_OPTIONS
        )
        n_input_tokens, n_output_tokens = r.usage.prompt_tokens, r.usage.completion_tokens
        return r.choices[0].message.content, (n_input_tokens, n_output_tokens), is_voice

    async def get_video_prompt(self, video: io.BytesIO, message: str = ""):
        frames, audio_buf = await self._get_frames_audio_from_video(video)
        text_from_audio = await self.transcribe(audio_buf)
        message_video = [
            {"role": "user", "content": [
                "Вот кадры из видео:",
                *map(lambda x: {"type": "image_url",
                                "image_url": {"url": f'data:image/jpg;base64,{x}', "detail": "low"}}, frames),
                {"type": "text", "text": f"Текст из видео: {text_from_audio}"},
                {"type": "text", "text": f"Пользователь: {message}\nОтвечай в формате Markdown"}
            ],
             }]
        return message_video

    @staticmethod
    async def get_diseases_web(image=None, prompt: str = "", lang: str = "ru"):

        try:
            text, images = await get_diseases_tg(image, prompt, lang)
            return text, images[-1]
        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

    def _generate_prompt_messages(self, message, dialog_messages, image_buffer: io.BytesIO = None):

        # prompt = Config.prompt_start

        messages = []  # {"role": "system", "content": prompt}

        for dialog_message in dialog_messages:
            messages.append({"role": "user", "content": dialog_message["user"]})
            messages.append({"role": "assistant", "content": dialog_message["bot"]})

        if image_buffer is not None:
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Пользователь: {message}\nОтвечай в формате Markdown",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{self._encode_image(image_buffer)}"
                            }
                        }
                    ]
                }

            )
        else:
            messages.extend({"role": "user", "content": f"Пользователь: {message}"})  # \nОтвечай в формате Markdown

        return messages

    async def _generate_prompt_messages_assistant(self, message,
                                                  dialog_messages: Optional[list] = None,
                                                  image_path: Optional[str] = None,
                                                  video_buffer: Optional[io.BytesIO] = None):

        messages = []
        if dialog_messages is not None:
            for dialog_message in dialog_messages[3:]:
                print(dialog_message["feed"])
                if dialog_message["feed"] or dialog_message["feed"] is None:
                    messages.append({"role": "user", "content": dialog_message["user"]})
                    messages.append({"role": "assistant", "content": dialog_message["bot"]})

        if image_path is not None:
            image_data = open(image_path, "rb")
            image_file = await self.client.files.create(
                file=image_data,
                purpose="vision"
            )

            image_data.close()

            await aiofiles.os.remove(image_path)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": message if message is not None else "Нет сообщения",
                        },
                        {
                            "type": "image_file",
                            "image_file": {"file_id": image_file.id},
                        }
                    ]
                }
            )
            print(messages)
            return messages

        if video_buffer is not None:
            messages.append(await self.get_video_prompt(video=video_buffer,
                                                        message=message))
            print(messages)
            return messages
        messages.append({"role": "user", "content": message})
        print(messages)
        return messages

    @staticmethod
    def _encode_image(image_buffer: io.BytesIO) -> str:
        return base64.b64encode(image_buffer.read()).decode("utf-8")

    @staticmethod
    def _count_tokens_from_prompt(prompt, answer, model="gpt-4o"):
        encoding = tiktoken.encoding_for_model(model)

        n_input_tokens = len(encoding.encode(prompt)) + 1
        n_output_tokens = len(encoding.encode(answer))

        return n_input_tokens, n_output_tokens

    @staticmethod
    def _postprocess_answer(answer):
        answer = answer.strip()
        return answer

    async def partner_answer_assistant(self, message: str,
                                       image_buffer: io.BytesIO = None,
                                       video_buffer: io.BytesIO = None
                                       ):
        partner_vs = await db.get_all_partners()
        is_voice = await self.is_need_voice(message)

        if partner_vs == []:
            return message, 0, 0, is_voice

        answer = None
        while answer is None:
            try:
                message += self.partner_extend_prompt

                messages = await self._generate_prompt_messages_assistant(message=message,
                                                                          video_buffer=video_buffer,
                                                                          image_path=image_buffer)
                thread = await self.client.beta.threads.create(tool_resources={
                    "file_search": {"vector_store_ids": partner_vs}},
                    messages=messages)

                run = await self.client.beta.threads.runs.create_and_poll(thread_id=thread.id,
                                                                          assistant_id=self.assistant_id)

                async def _wait_on_run(_run, _thread):

                    while _run.status in ["queued", "in_progress"]:
                        _run = await self.client.beta.threads.runs.retrieve(
                            thread_id=_thread.id,
                            run_id=_run.id
                        )
                        await asyncio.sleep(0.5)
                    return _run

                run = await _wait_on_run(run, thread)

                if run.status == "completed":
                    messages = list(await self.client.beta.threads.messages.list(
                        thread_id=thread.id,
                        run_id=run.id
                    ))
                    message_content = messages[0].content[0].text
                    annotations = message_content.annotations
                    citations = []

                    for i, annotation in enumerate(annotations):
                        message_content.value = message_content.value.replace(annotation.text, f"[{i}]")
                        if file_citation := getattr(annotation, "file_citation", None):
                            file_ = await self.client.files.retrieve(file_citation.file_id)
                            citations.append(f"[{i}]: {file_.filename}")

                    n_input_tokens, n_output_tokens = run.usage.prompt_tokens, run.usage.completion_tokens


            except Exception as e:
                logging.exception(e)
                raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

            else:
                citation = '\n'.join(citations)
                return f"{answer}\n{citation}", n_input_tokens, n_output_tokens, is_voice

    async def send_message_assistant(self, message,
                                     dialog_messages: List = [],
                                     image_buffer: io.BytesIO = None,
                                     video_buffer: io.BytesIO = None):
        vs_ids = await db.get_all_vs()
        n_dialog_messages_before = len(dialog_messages)
        answer = None

        while answer is None:
            try:
                #is_voice = await self.is_need_voice(message)
                answer_partner, n_input_tokens_p, n_output_tokens_p, is_voice = await self.partner_answer_assistant(
                    message=message,
                    image_buffer=image_buffer,
                    video_buffer=video_buffer
                )

                messages = await self._generate_prompt_messages_assistant(message,
                                                                          dialog_messages,
                                                                          image_buffer,
                                                                          video_buffer)
                thread = await self.client.beta.threads.create(tool_resources={
                    "file_search": {"vector_store_ids": vs_ids}},
                    messages=messages)

                run = await self.client.beta.threads.runs.create_and_poll(thread_id=thread.id,
                                                                          assistant_id=self.assistant_id)

                async def _wait_on_run(_run, _thread):

                    while _run.status in ["queued", "in_progress"]:
                        _run = await self.client.beta.threads.runs.retrieve(
                            thread_id=_thread.id,
                            run_id=_run.id
                        )
                        await asyncio.sleep(0.5)
                    return _run

                run = await _wait_on_run(run, thread)

                if run.status == "completed":
                    messages = list(await self.client.beta.threads.messages.list(
                        thread_id=thread.id,
                        run_id=run.id
                    ))
                    # print(messages)
                    message_content = messages[0][1][0].content[0].text
                    annotations = message_content.annotations
                    citations = []

                    for i, annotation in enumerate(annotations):
                        message_content.value = message_content.value.replace(annotation.text, f"[{i}]")
                        if file_citation := getattr(annotation, "file_citation", None):
                            file_ = await self.client.files.retrieve(file_citation.file_id)
                            citations.append(f"[{i}]: {file_.filename}")
                    answer = message_content.value
                    n_input_tokens, n_output_tokens = run.usage.prompt_tokens, run.usage.completion_tokens
                    n_first_dialog_messages_removed = n_dialog_messages_before - len(dialog_messages)

                elif run.status == "requires_action":
                    tool_call = run.required_action.submit_tool_outputs.tool_calls[0]
                    func_name = tool_call.function.name
                    arg = json.loads(tool_call.function.arguments)
                    function = self.tools_dict[func_name]
                    context = await function(**arg)

                    run = await self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread.id,
                        run_id=run.id,
                        tool_outputs=[
                            {
                                "tool_call_id": tool_call.id,
                                "output": json.dumps(context)
                            }
                        ]
                    )

                    run = await _wait_on_run(run, thread)

                    messages = list(await self.client.beta.threads.messages.list(
                        thread_id=thread.id,
                        run_id=run.id
                    ))
                    message_content = messages[0][1][0].content[0].text
                    annotations = message_content.annotations
                    citations = []

                    for i, annotation in enumerate(annotations):
                        message_content.value = message_content.value.replace(annotation.text, f"[{i}]")
                        if file_citation := getattr(annotation, "file_citation", None):
                            file_ = await self.client.files.retrieve(file_citation.file_id)
                            citations.append(f"[{i}]: {file_.filename}")
                    answer = message_content.value
                    n_input_tokens, n_output_tokens = run.usage.prompt_tokens, run.usage.completion_tokens
                    n_first_dialog_messages_removed = n_dialog_messages_before - len(dialog_messages)

            except Exception as e:
                logging.exception(e)
                raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

            else:
                citation = '\n'.join(citations)
                return f"{answer}\n\n{citation}", (n_input_tokens+n_input_tokens_p, n_output_tokens+n_output_tokens_p), \
                       n_first_dialog_messages_removed, is_voice

    @staticmethod
    def _count_tokens_from_messages(messages, answer, model="gpt-4o"):
        encoding = tiktoken.encoding_for_model(model)

        if model == "gpt-3.5-turbo-16k":
            tokens_per_message = 4
            tokens_per_name = -1
        elif model == "gpt-3.5-turbo":
            tokens_per_message = 4
            tokens_per_name = -1
        elif model == "gpt-4":
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-4-1106-preview":
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-4-vision-preview":
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-4-turbo":
            tokens_per_message = 3
            tokens_per_name = 1
        elif model == "gpt-4o":
            tokens_per_message = 3
            tokens_per_name = 1
        else:
            raise ValueError(f"Unknown model: {model}")

        # input
        n_input_tokens = 0
        for message in messages:
            n_input_tokens += tokens_per_message
            if isinstance(message["content"], list):
                for sub_message in message["content"]:
                    if "type" in sub_message:
                        if sub_message["type"] == "text":
                            n_input_tokens += len(encoding.encode(sub_message["text"]))
                        elif sub_message["type"] == "image_url":
                            pass
            else:
                if "type" in message:
                    if message["type"] == "text":
                        n_input_tokens += len(encoding.encode(message["text"]))
                    elif message["type"] == "image_url":
                        pass

        n_input_tokens += 2

        # output
        n_output_tokens = 1 + len(encoding.encode(answer))

        return n_input_tokens, n_output_tokens
