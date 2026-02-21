# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости для matplotlib и sqlite
RUN apt-get update && apt-get install -y \
    gcc \
    libfreetype6-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Создаем директорию для базы данных
RUN mkdir -p /app/data

# Указываем порт (хотя бот не использует HTTP, но для совместимости)
EXPOSE 8080

# Запускаем бота
CMD ["python", "bot.py"]