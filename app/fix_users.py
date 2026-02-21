"""
Скрипт для просмотра и исправления пользователей в базе данных
"""
from database import Session, User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def list_all_users():
    """Показать всех пользователей"""
    session = Session()
    users = session.query(User).all()

    print("\n" + "=" * 80)
    print(f"{'ID':<5} {'VK ID':<15} {'Имя':<30} {'Админ':<8} {'Замеры':<8}")
    print("=" * 80)

    for user in users:
        readings_count = len(user.readings)
        print(f"{user.id:<5} {user.vk_id:<15} {user.name:<30} {user.is_admin:<8} {readings_count:<8}")

    print("=" * 80)
    print(f"Всего пользователей: {len(users)}")
    session.close()


def fix_user_name(vk_id: int, new_name: str):
    """Исправить имя пользователя"""
    session = Session()
    user = session.query(User).filter_by(vk_id=vk_id).first()

    if user:
        old_name = user.name
        user.name = new_name
        session.commit()
        print(f"Имя пользователя {vk_id} изменено с '{old_name}' на '{new_name}'")
    else:
        print(f"Пользователь с VK ID {vk_id} не найден")

    session.close()


def set_admin(vk_id: int, is_admin: bool = True):
    """Назначить или снять администратора"""
    session = Session()
    user = session.query(User).filter_by(vk_id=vk_id).first()

    if user:
        user.is_admin = is_admin
        session.commit()
        print(f"Пользователь {user.name} теперь {'администратор' if is_admin else 'обычный пользователь'}")
    else:
        print(f"Пользователь с VK ID {vk_id} не найден")

    session.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        # Просто показать список
        list_all_users()
    elif sys.argv[1] == "list":
        list_all_users()
    elif sys.argv[1] == "fix" and len(sys.argv) == 4:
        # fix 12345678 "Новое Имя"
        vk_id = int(sys.argv[2])
        new_name = sys.argv[3]
        fix_user_name(vk_id, new_name)
    elif sys.argv[1] == "admin" and len(sys.argv) == 3:
        # admin 12345678
        vk_id = int(sys.argv[2])
        set_admin(vk_id, True)
    elif sys.argv[1] == "unadmin" and len(sys.argv) == 3:
        # unadmin 12345678
        vk_id = int(sys.argv[2])
        set_admin(vk_id, False)
    else:
        print("Использование:")
        print("  python fix_users.py              - показать всех пользователей")
        print("  python fix_users.py list         - показать всех пользователей")
        print("  python fix_users.py fix VK_ID ИМЯ - исправить имя пользователя")
        print("  python fix_users.py admin VK_ID   - сделать пользователя администратором")
        print("  python fix_users.py unadmin VK_ID - снять права администратора")