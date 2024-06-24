FROM python:3.10

RUN python3 -m ensurepip && \
    pip install --upgrade pip

RUN apt-get update

RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y

# install PyMupdf
RUN pip install pymupdf4llm

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run_bot.py"]