"""
Скрипт для миграции существующей базы данных
Добавляет таблицу users и переносит существующих пользователей
"""
from database import Session, engine, Base, User, GlucoseReading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Миграция существующих пользователей"""

    # Создаем новые таблицы
    Base.metadata.create_all(engine)
    logger.info("Таблицы созданы")

    session = Session()

    # Получаем всех уникальных пользователей из замеров
    user_ids = session.query(GlucoseReading.user_id).distinct().all()

    for (vk_id,) in user_ids:
        # Проверяем, есть ли уже такой пользователь
        existing = session.query(User).filter_by(vk_id=vk_id).first()
        if not existing:
            # Создаем пользователя с именем по умолчанию
            user = User(vk_id=vk_id, name=f"User_{vk_id}", is_admin=False)
            session.add(user)
            logger.info(f"Создан пользователь для VK ID {vk_id}")

    session.commit()
    session.close()

    logger.info("Миграция завершена")


if __name__ == "__main__":
    migrate()