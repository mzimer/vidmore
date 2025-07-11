# backend/models.py

from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

class UserStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class TaskStatus(enum.Enum):
    # Указываем все необходимые статусы, которые будут использоваться в проекте и воркерах
    queued = "queued"          # Задача в очереди на обработку
    downloading = "downloading" # Задача скачивается
    processing = "processing"   # Идет обработка (например, конвертация)
    uploading = "uploading"     # Загрузка на платформу
    completed = "completed"     # Всё успешно завершено
    failed = "failed"           # Ошибка при выполнении

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    status = Column(Enum(UserStatus), default=UserStatus.pending, nullable=False)
    tasks = relationship("Task", back_populates="user")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    video_url = Column(String, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.queued, nullable=False)
    action = Column(String, nullable=True)  # download / upload / etc.
    user = relationship("User", back_populates="tasks")
