import os
import sys
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Добавляем корень проекта в sys.path, чтобы импортировать backend
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from backend.models import Task, TaskStatus

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://vidmore:strongpass@postgres:5432/vidmore")
DOWNLOAD_DIR = "/downloads"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def download_video(video_url, output_path):
    import yt_dlp
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

def main_loop():
    print("Download worker started")
    while True:
        with Session() as session:
            task = session.query(Task).filter_by(status=TaskStatus.queued, action='download').first()
            if not task:
                time.sleep(3)
                continue

            print(f"Found task id={task.id}, url={task.video_url}")
            # Статус — downloading
            task.status = TaskStatus.downloading
            session.commit()

            output_path = os.path.join(DOWNLOAD_DIR, f"{task.id}.mp4")
            try:
                download_video(task.video_url, output_path)
                task.status = TaskStatus.completed
                print(f"Task {task.id} completed")
            except Exception as e:
                print(f"Task {task.id} failed: {e}")
                task.status = TaskStatus.failed
            session.commit()
        time.sleep(2)

if __name__ == "__main__":
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    main_loop()
