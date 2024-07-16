from src.config import Config
from src.database import DataBase as db
import openai
import io
import logging
import httpx
from moviepy.editor import VideoFileClip
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiofiles
import aiofiles.os
from typing import List
import os
from pytube import YouTube, Playlist
import uuid
from bs4 import BeautifulSoup
import re
import aiohttp


class KnowledgeLoader:

    def __init__(self):
        proxy = Config.proxies
        if proxy is not None:
            self.http_client_openai = httpx.AsyncClient(proxies=proxy)
            self.client = openai.AsyncOpenAI(api_key=Config.openai_api_key, http_client=self.http_client_openai)
        else:
            self.client = openai.AsyncOpenAI(api_key=Config.openai_api_key)

        self.executor_pool = ThreadPoolExecutor()
        self.http_client = httpx.AsyncClient()

    async def transcribe(self, file: io.BytesIO):

        try:
            # with open(file, "rb") as audio:
            file.seek(0)  # Reset the file pointer to the beginning
            file.name = "temp.mp3"
            audio_content = file.read()
            prompt_text = Config.whisper_prompt
            result = await self.client.audio.transcriptions.create(model="whisper-1",
                                                                   file=("temp." + "mp3", audio_content, "audio/mp3"),
                                                                   prompt=prompt_text)
            # print(result.text)
            return result.text

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

    async def _get_audio_from_video(self, video_data: str) -> io.BytesIO:
        try:
            # Create a BytesIO object to hold the audio data
            # audio_data = io.BytesIO()
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
                name = temp_audio.name

            def _get_audio(path_video):
                clip = VideoFileClip(path_video)
                clip.audio.write_audiofile(name, codec="mp3", bitrate="32k")
                clip.audio.close()
                clip.close()

                with open(name, "rb") as audio_tfile:
                    audio_data = io.BytesIO(audio_tfile.read())
                    audio_data.seek(0)

                return audio_data
                # _data.seek(0)

            audio_data = await asyncio.get_event_loop().run_in_executor(self.executor_pool, _get_audio, video_data)
            await aiofiles.os.remove(video_data)
            await aiofiles.os.remove(name)

            return audio_data

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

    async def download_video(self, url, output_path="videos"):

        def _download():
            yt = YouTube(url)
            stream = yt.streams.filter(progressive=True, file_extension='mp4').get_lowest_resolution()
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            file_path = stream.download(output_path)
            return file_path

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor_pool, _download)

    async def download_playlist(self, playlist_url, output_path="videos"):
        playlist = Playlist(playlist_url)
        tasks = [self.download_video(video_url, output_path) for video_url in playlist.video_urls]
        return await asyncio.gather(*tasks)

    async def process_video(self, url, output_path="videos"):

        file_path = await self.download_video(url, output_path)

        audio = await self._get_audio_from_video(file_path)

        transcription = await self.transcribe(audio)

        transcription = io.BytesIO(transcription.encode("utf-8"))
        fname = f'{file_path.split("/")[-1].split(".")[0]}.txt'  # f"agronomical_video_{str(uuid.uuid4())}.txt"
        async with aiofiles.open(fname, "wb") as f:
            await f.write(transcription.getbuffer())

        data = open(fname, "rb")
        data.close()
        await aiofiles.os.remove(fname)
        return data  # await aiofiles.open(fname, "rb")

    async def process_playlist(self, playlist_url, output_path="videos"):
        file_paths = await self.download_playlist(playlist_url, output_path)
        tasks = [self.process_video(file_path) for file_path in file_paths]
        await asyncio.gather(*tasks)

    async def load_knowledge_youtube(self, url_youtube,
                                     output_path: str = "videos",
                                     vectorstore_name: str = f"agro_store_{str(uuid.uuid4())}"):

        try:

            transcriptions = []
            if "playlist" in url_youtube:
                transcriptions = await self.process_playlist(url_youtube, output_path)
            else:
                transcription = await self.process_video(url_youtube, output_path)
                transcriptions = [transcription]

            vector_store = await self.client.beta.vector_stores.create(name=vectorstore_name)
            batch = await self.client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=transcriptions
            )

            await db.add_new_vs(vector_store.id)

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e
        else:
            return vector_store.id

    async def load_knowledge_file(self, file_data: io.BytesIO,
                                  name_of_file: str | None = None,
                                  vectorstore_name: str = f"agro_store_{str(uuid.uuid4())}"):
        try:

            if name_of_file is None:
                name_of_file = f"text_data_{str(uuid.uuid4())}.txt"

            async with aiofiles.open(name_of_file, "wb") as f:
                await f.write(file_data.getbuffer())

            vector_store = await self.client.beta.vector_stores.create(name=vectorstore_name)
            data = open(name_of_file, "rb")
            batch = await self.client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=[data]
            )
            data.close()
            await aiofiles.os.remove(name_of_file)
            await db.add_new_vs(vector_store.id)

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e
        else:
            return vector_store.id

    async def download_file_gdrive(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:

                if 'Content-Disposition' in response.headers:
                    content_disposition = response.headers['Content-Disposition']
                    fname = re.findall('filename=(.+)', content_disposition)[0].replace('"', '')

                else:
                    logging.warning("Content-Disposition header not found. Cannot determine filename.")
                    fname = f"unnamed_gdrive_data_{str(uuid.uuid4())}.txt"
                r_content = await response.read()
                buf = io.BytesIO(r_content)
                async with aiofiles.open(fname, "wb") as f:
                    await f.write(buf.getbuffer())

            data = open(fname, "rb")
            data.close()
            await aiofiles.os.remove(fname)
            return data

    async def gather_files_from_gfolder(self, folder_url):
        async with self.http_client as client:
            response = await client.get(folder_url, )
            response.raise_for_status()

            ids = []

            def _get_ids(page):
                nonlocal ids
                soup = BeautifulSoup(page, 'html.parser')
                file_links = soup.find_all("div", class_="WYuW0e Ss7qXc")
                ids = [u['data-id'] for u in file_links]

            loop = asyncio.get_event_loop()
            content = response.read()
            text = content.decode("utf-8")
            await loop.run_in_executor(self.executor_pool, _get_ids, text)

            return await self.process_gurl(file_ids=ids)

    @staticmethod
    async def process_gurl(gdrive_url: str | None = None, file_ids: List[str] | None = None):
        base_url = "https://drive.google.com/uc?export=download&id="
        if gdrive_url is not None:
            return f"{base_url}{gdrive_url.split('/')[-2]}"
        if file_ids is not None:
            return [f"{base_url}{id}" for id in file_ids]

    async def load_knowledge_gdrive(self, gdrive_url: str,
                                    vectorstore_name: str = f"agro_store_{str(uuid.uuid4())}"):
        try:


            if "drive.google.com" in gdrive_url:
                if "folder" in gdrive_url:
                    file_urls = await self.gather_files_from_gfolder(gdrive_url)
                else:
                    url = await self.process_gurl(gdrive_url)
                    file_urls = [url]

            elif "docs.google.com" in gdrive_url:
                if "folder" in gdrive_url:
                    file_urls = await self.gather_files_from_gfolder(gdrive_url)
                else:
                    url = await self.process_gurl(gdrive_url)
                    file_urls = [url]

            else:
                raise ValueError("⚠️Need only google drive links!")

            contents = [await self.download_file_gdrive(url) for url in file_urls]

            vector_store = await self.client.beta.vector_stores.create(name=vectorstore_name)

            batch = await self.client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=contents
            )
            await db.add_new_vs(vector_store.id)

        except Exception as e:

            logging.exception(e)
            raise Exception(f"⚠️ _'error'._   ⚠️\n{str(e)}") from e

        else:
            return vector_store.id

    async def load_partner(self, gdrive_url: str,
                           vectorstore_name: str = f"partner_store_{str(uuid.uuid4())}"):
        try:

            if "drive.google.com" in gdrive_url:
                if "folder" in gdrive_url:
                    file_urls = await self.gather_files_from_gfolder(gdrive_url)
                else:
                    url = await self.process_gurl(gdrive_url)
                    file_urls = [url]

            elif "docs.google.com" in gdrive_url:
                if "folder" in gdrive_url:
                    file_urls = await self.gather_files_from_gfolder(gdrive_url)
                else:
                    url = await self.process_gurl(gdrive_url)
                    file_urls = [url]

            else:
                raise ValueError("⚠️Need only google drive links!")

            contents = [await self.download_file_gdrive(url) for url in file_urls]

            vector_store = await self.client.beta.vector_stores.create(name=vectorstore_name)
            batch = await self.client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=contents
            )
            await db.add_new_partner(vector_store.id)

        except Exception as e:

            logging.exception(e)
            raise Exception(f"⚠️ _'error'._   ⚠️\n{str(e)}") from e

        else:
            return vector_store.id
