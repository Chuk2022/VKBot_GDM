import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Токен группы VK
VK_GROUP_TOKEN = os.getenv('VK_GROUP_TOKEN')

# Список администраторов (их VK ID)
# Можно указать несколько ID через запятую
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

if not VK_GROUP_TOKEN:
    raise ValueError("❌ Не указан VK_GROUP_TOKEN в файле .env")