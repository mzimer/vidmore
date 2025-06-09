FROM python:3.11-slim

WORKDIR /app

# Устанавливаем ffmpeg (добавили одну строку!)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

COPY download_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY download_worker/download_worker.py .
COPY backend ./backend

# CMD можно оставить без изменений
CMD ["python", "download_worker.py"]
