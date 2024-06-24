import aiohttp
import asyncio
from bs4 import BeautifulSoup
import aiofiles
import requests
import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO
from src.config import Config


def is_in(a, b):
    if a is not None and b is not None:
        return a in b
    else:
        return False


def display_images_with_captions(image_urls, captions):
    if len(image_urls) != len(captions):
        print("Количество изображений и подписей должно совпадать.")
        return

    plt.figure(figsize=(10, len(image_urls) * 5))

    for i, (image_url, caption) in enumerate(zip(image_urls, captions), start=1):
        response = requests.get(image_url)
        image = Image.open(BytesIO(response.content))

        plt.subplot(len(image_urls), 1, i)
        plt.imshow(image)
        plt.title(caption)
        plt.axis('off')

    plt.tight_layout()
    plt.show()


async def get_text_image(response):
    soup = BeautifulSoup(response, "html.parser")
    text = soup.get_text(separator="\n")
    images = soup.find_all(style=lambda value: is_in("background-image", value))
    img_urls = [style['style'].split('url("')[1].split('")')[0] for style in images]
    return text, img_urls


async def async_post_with_files(url, data, files):
    async with aiohttp.ClientSession() as session:
        form_data = aiohttp.FormData()
        for key, value in data.items():
            form_data.add_field(key, value)
        for file_name, file_content in files.items():
            form_data.add_field(file_name, file_content, filename=file_name)

        async with session.post(url, data=form_data) as response:
            return await response.text()


async def get_diseases_colab(filepath: str, *, prompt: str = "", lang: str = "ru"):

    url = Config.diseases_url
    data = {"text_desc": prompt, "pdd": "2", "lang": lang}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(filepath) as resp:
                if resp.status == 200:
                    file_content = await resp.read()
                    files = {"xfile1": file_content}
    except:
        file_content = await aiofiles.open(filepath, "rb")
        files = {"xfile1": file_content}

    response_text = await async_post_with_files(url, data, files)
    text, images = await get_text_image(response_text)
    cap = ["Ваше изображение"] + ["Пример болезни"]*(len(images)-1)
    display_images_with_captions(images, cap)
    print(text)


async def get_diseases_tg(file:BytesIO, *, prompt: str = "", lang: str = "ru"):
    url = Config.diseases_url
    data = {"text_desc": prompt, "pdd": "2", "lang": lang}
    files = {"xfile1": file}
    response_text = await async_post_with_files(url, data, files)
    text, images = await get_text_image(response_text)

    return text, images
