from src.config import Config
import openai
from src.database import DataBase as db
import io
import logging
import httpx
from moviepy.editor import VideoFileClip
from concurrent.futures import ThreadPoolExecutor
import asyncio
import base64
import aiofiles
from pydub import AudioSegment
from typing import List
import json
import os
from pytube import YouTube, Playlist
import ffmpeg
import uuid


class KnowledgeLoader:

    def __init__(self):
        self.http_client_ = httpx.AsyncClient(proxies=Config.proxies)
        self.client = openai.AsyncOpenAI(api_key=Config.openai_api_key, http_client=self.http_client_)
        self.executor_pool = ThreadPoolExecutor()
        self.http_client = httpx.AsyncClient()

    async def transcribe(self, file: io.BytesIO):

        try:
            # with open(file, "rb") as audio:
            prompt_text = Config.whisper_prompt
            result = await self.client.audio.transcriptions.create(model="whisper-1",
                                                                   file=file.read(),
                                                                   prompt=prompt_text)
            return result.text

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

    @staticmethod
    async def _get_audio_from_video(video_data: str) -> io.BytesIO:
        try:
            # Create a BytesIO object to hold the audio data
            audio_data = io.BytesIO()

            # Load the video clip
            # clip = VideoFileClip(video_data)
            # video_temp_path = "temp_video.mp4"
            # clip.write_videofile(video_temp_path, codec="libx264")

            # Use ffmpeg to extract audio and write to BytesIO object
            process = (
                ffmpeg
                .input(video_data)
                .output('pipe:', format='mp3', acodec='libmp3lame', audio_bitrate='32k')
                .run_async(pipe_stdout=True, pipe_stderr=True)
            )

            # Read the output from the process and write it to the BytesIO object
            audio_data.write(process.stdout.read())
            audio_data.seek(0)

            # Clean up
            process.stdout.close()
            process.wait()
            clip.close()

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e

        else:
            return audio_data

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

        # async with aiofiles.open(file_path, "rb") as f:
        #     video = io.BytesIO(await f.read())
        #     video.name = "youtube.mp4"
        #     video.seek(0)

        audio = await self._get_audio_from_video(file_path)
        transcription = await self.transcribe(audio)
        transcription = io.BytesIO(transcription.encode("utf-8")).read()

        return transcription

    async def process_playlist(self, playlist_url, output_path="videos"):
        file_paths = await self.download_playlist(playlist_url, output_path)
        tasks = [self.process_video(file_path) for file_path in file_paths]
        await asyncio.gather(*tasks)

    async def load_knowledge_youtube(self, url_youtube,
                                     output_path: str = "videos",
                                     vectorstore_name: str = f"agro_store_{str(uuid.uuid4())}"):

        try:
            vector_store = await self.client.beta.vector_stores.create(name=vectorstore_name)

            if "playlist" in url_youtube:
                transcriptions = await self.process_playlist(url_youtube, output_path)
            else:
                transcription = await self.process_video(url_youtube, output_path)
                transcriptions = [transcription]

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

            vector_store = await self.client.beta.vector_stores.create(name=vectorstore_name)

            if name_of_file is not None:
                file_data.name = name_of_file

            batch = await self.client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store.id,
                files=[file_data.read()]
            )

            await db.add_new_vs(vector_store.id)

        except Exception as e:
            logging.exception(e)
            raise Exception(f"⚠️ _'error'._ ⚠️\n{str(e)}") from e
        else:
            return vector_store.id

    async def download_file_gdrive(self, url):
        async with self.http_client as client:
            response = await client.get(url)
            response.raise_for_status()
            # await client.aclose()
            return io.BytesIO(response.content)

    async def gather_files_from_gfolder(self, folder_url):
        async with self.http_client as client:
            response = await client.get(folder_url)
            response.raise_for_status()
            urls = response.json().get("file_urls", [])
            # await client.aclose()
            return urls

    async def load_knowledge_gdrive(self, gdrive_url: str,
                                    vectorstore_name: str = f"agro_store_{str(uuid.uuid4())}"):
        try:
            vector_store = await self.client.beta.vector_stores.create(name=vectorstore_name)

            if "drive.google.com" in gdrive_url:
                if "folder" in gdrive_url:
                    file_urls = await self.gather_files_from_gfolder(gdrive_url)
                else:
                    url = f"https://drive.google.com/uc?export=download&id={gdrive_url.split('/')[-2]}"
                    file_urls = [url]

            elif "docs.google.com" in gdrive_url:
                if "folder" in gdrive_url:
                    file_urls = await self.gather_files_from_gfolder(gdrive_url)
                else:
                    url = f"https://drive.google.com/uc?export=download&id={gdrive_url.split('/')[-2]}"
                    file_urls = [url]

            else:
                raise ValueError("⚠️Need only google drive links!")

            contents: list = []

            async with self.http_client as client:
                for url in file_urls:
                    response = await client.get(url)
                    response.raise_for_status()
                    content = io.BytesIO(response.content)
                    contents.append(content)

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

    async def load_partner(self, url: str,
                           vectorstore_name: str = f"partner_store_{str(uuid.uuid4())}"):
        try:
            vector_store = await self.client.beta.vector_stores.create(name=vectorstore_name)

            if "drive.google.com" in url:
                if "folder" in url:
                    file_urls = await self.gather_files_from_gfolder(url)
                else:
                    url = f"https://drive.google.com/uc?export=download&id={url.split('/')[-2]}"
                    file_urls = [url]

            else:
                raise ValueError("⚠️Need only google drive links!")

            contents: list = []

            for _url in file_urls:
                content = await self.download_file_gdrive(url=_url)
                contents.append(content)

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
