import os
from sqlalchemy import create_engine, Column, Integer, Float, DateTime, String, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Путь к базе данных
#DB_PATH = '/app/data/glucose.db' if os.path.exists('/app') else 'data/glucose.db'
#os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Настройка базы данных
#engine = create_engine(f'sqlite:///{DB_PATH}?check_same_thread=False')
#Session = sessionmaker(bind=engine)
#Base = declarative_base()

# Явно указываем путь к папке проекта на Windows
PROJECT_PATH = r'E:\BotVK\app'  # <-- Укажите ваш реальный путь
DB_PATH = os.path.join(PROJECT_PATH, 'data', 'glucose.db')
# Создаем директорию для базы данных
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Настройка базы данных
engine = create_engine(f'sqlite:///{DB_PATH}?check_same_thread=False')
Session = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    """Таблица пользователей (клиентов)"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    vk_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    registered_at = Column(DateTime, default=datetime.now)

    # Связь с замерами
    readings = relationship("GlucoseReading", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(vk_id={self.vk_id}, name={self.name}, is_admin={self.is_admin})>"


class GlucoseReading(Base):
    __tablename__ = 'glucose_readings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.vk_id'), nullable=False, index=True)
    value = Column(Float, nullable=False)
    period = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)

    # Связь с пользователем
    user = relationship("User", back_populates="readings")

    def __repr__(self):
        return f"<GlucoseReading(user={self.user_id}, value={self.value}, period={self.period})>"


# Создание таблиц
Base.metadata.create_all(engine)
logger.info("База данных инициализирована")