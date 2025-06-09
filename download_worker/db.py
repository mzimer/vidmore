from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Эта строка берёт url к базе из переменной окружения (у тебя наверняка уже есть, если ты запускал alembic)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@postgres:5432/postgres")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
