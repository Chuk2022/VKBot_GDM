from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from database import Session, User, GlucoseReading
from config import VK_GROUP_TOKEN, ADMIN_IDS
import logging
from datetime import datetime
import traceback
import io
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from vkbottle import PhotoMessageUploader
from sqlalchemy import func

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=VK_GROUP_TOKEN)

# Состояния для ожидания ввода показателей
user_states = {}


def create_main_keyboard():
    """Создание основной клавиатуры с кнопками"""
    keyboard = Keyboard(one_time=False, inline=False)

    # Первый ряд
    keyboard.add(Text("🍽 Перед завтраком"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("🍽 Перед обедом"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("🍽 Перед ужином"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()

    # Второй ряд
    keyboard.add(Text("🌙 Перед сном"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("🌃 Ночью"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()

    # Третий ряд
    keyboard.add(Text("⏱ Через час после еды"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("📊 График"), color=KeyboardButtonColor.SECONDARY)

    return keyboard


# ============= ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ =============
async def get_or_create_user(vk_id: int, name: str = None):
    """Получить или создать пользователя в базе"""
    session = None
    try:
        session = Session()
        user = session.query(User).filter_by(vk_id=vk_id).first()

        if not user:
            if not name:
                try:
                    user_info = await bot.api.users.get(vk_id)
                    if user_info and len(user_info) > 0:
                        name = f"{user_info[0].first_name} {user_info[0].last_name}"
                    else:
                        name = f"User_{vk_id}"
                except:
                    name = f"User_{vk_id}"

            is_admin = vk_id in ADMIN_IDS
            user = User(vk_id=vk_id, name=name, is_admin=is_admin)
            session.add(user)
            session.commit()
            logger.info(f"Создан новый пользователь: {name} (admin={is_admin})")

        return user
    except Exception as e:
        logger.error(f"Ошибка в get_or_create_user: {e}")
        return User(vk_id=vk_id, name=name or f"User_{vk_id}", is_admin=vk_id in ADMIN_IDS)
    finally:
        if session:
            session.close()


def is_admin(vk_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    session = Session()
    user = session.query(User).filter_by(vk_id=vk_id).first()
    session.close()
    return user and user.is_admin


def get_all_users():
    """Получить список всех пользователей (кроме администраторов)"""
    session = Session()
    users = session.query(User).filter_by(is_admin=False).order_by(User.name).all()
    session.close()
    return users


# ============= ОБРАБОТЧИКИ КОМАНД =============
@bot.on.message(text=["/start", "старт", "начало", "меню"])
async def start_handler(message: Message):
    """Обработчик команды старт"""
    try:
        user_name = None
        try:
            user_info = await bot.api.users.get(message.from_id)
            if user_info and len(user_info) > 0:
                user_name = f"{user_info[0].first_name} {user_info[0].last_name}"
        except Exception as e:
            logger.warning(f"Не удалось получить имя: {e}")

        user = await get_or_create_user(message.from_id, user_name)
        logger.info(f"Пользователь {user.name} запустил бота")

        keyboard = create_main_keyboard()

        if user.is_admin:
            keyboard.row()
            keyboard.add(Text("👥 Список клиентов"), color=KeyboardButtonColor.PRIMARY)
            keyboard.add(Text("📊 Админ панель"), color=KeyboardButtonColor.SECONDARY)

        await message.answer(
            f"👋 Здравствуйте, {user.name}!\n"
            "Выберите период измерения:",
            keyboard=keyboard.get_json()
        )
    except Exception as e:
        logger.error(f"Ошибка в start_handler: {e}")
        await message.answer(
            "👋 Добро пожаловать!",
            keyboard=create_main_keyboard().get_json()
        )


@bot.on.message(text=[
    "🍽 Перед завтраком", "🍽 Перед обедом", "🍽 Перед ужином",
    "🌙 Перед сном", "🌃 Ночью", "⏱ Через час после еды"
])
async def measurement_time_handler(message: Message):
    """Обработчик выбора времени измерения"""
    logger.info(f"Выбран период: {message.text}")

    user_states[message.from_id] = {
        'period': message.text,
        'waiting_for_value': True
    }

    period_text = message.text.split(' ', 1)[1] if ' ' in message.text else message.text

    await message.answer(
        f"📝 Введите показатель глюкозы для периода: *{period_text}*",
        keyboard=create_main_keyboard().get_json()
    )


# ============= АДМИНИСТРАТИВНЫЕ ОБРАБОТЧИКИ =============
@bot.on.message(text=["👥 Список клиентов"])
async def list_clients_handler(message: Message):
    """Показать список всех клиентов"""
    if not is_admin(message.from_id):
        await message.answer("❌ Нет прав администратора")
        return

    users = get_all_users()

    if not users:
        await message.answer("📭 Нет зарегистрированных клиентов")
        return

    keyboard = Keyboard(one_time=True, inline=False)

    for user in users:
        session = Session()
        readings_count = session.query(GlucoseReading).filter_by(user_id=user.vk_id).count()
        session.close()

        button_text = f"{user.vk_id}:{user.name} ({readings_count} зап.)"
        keyboard.add(Text(button_text), color=KeyboardButtonColor.PRIMARY)
        keyboard.row()

    keyboard.add(Text("🔙 Назад"), color=KeyboardButtonColor.SECONDARY)

    await message.answer(
        "👥 Список клиентов:",
        keyboard=keyboard.get_json()
    )


@bot.on.message(text=["📊 Админ панель"])
async def admin_panel_handler(message: Message):
    """Административная панель"""
    if not is_admin(message.from_id):
        return

    session = Session()
    total_users = session.query(User).count()
    total_readings = session.query(GlucoseReading).count()
    today = datetime.now().date()
    today_readings = session.query(GlucoseReading).filter(
        func.date(GlucoseReading.timestamp) == today
    ).count()
    session.close()

    keyboard = Keyboard(inline=False)
    keyboard.add(Text("👥 Список клиентов"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("📊 Общая статистика"), color=KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("🔙 Назад"), color=KeyboardButtonColor.SECONDARY)

    await message.answer(
        f"📊 Админ панель\n\n"
        f"Клиентов: {total_users}\n"
        f"Замеров: {total_readings}\n"
        f"Замеров сегодня: {today_readings}",
        keyboard=keyboard.get_json()
    )


@bot.on.message(text=["📊 Общая статистика"])
async def overall_stats_handler(message: Message):
    """Показать общую статистику"""
    if not is_admin(message.from_id):
        return

    session = Session()
    users = session.query(User).filter_by(is_admin=False).all()

    stats_text = "📊 Общая статистика:\n\n"

    for user in users:
        readings = session.query(GlucoseReading).filter_by(user_id=user.vk_id).all()
        if readings:
            values = [r.value for r in readings]
            stats_text += f"👤 {user.name}:\n"
            stats_text += f"   Замеров: {len(readings)}\n"
            stats_text += f"   Среднее: {np.mean(values):.1f}\n\n"

    session.close()
    await message.answer(stats_text, keyboard=create_main_keyboard().get_json())


@bot.on.message(text=["🔙 Назад"])
async def back_handler(message: Message):
    """Вернуться в главное меню"""
    keyboard = create_main_keyboard()

    if is_admin(message.from_id):
        keyboard.row()
        keyboard.add(Text("👥 Список клиентов"), color=KeyboardButtonColor.PRIMARY)
        keyboard.add(Text("📊 Админ панель"), color=KeyboardButtonColor.SECONDARY)

    await message.answer("Главное меню:", keyboard=keyboard.get_json())


# ============= ОБРАБОТЧИК ГРАФИКА (ДЛЯ СЕБЯ) =============
@bot.on.message(text=["📊 График"])
async def plot_handler(message: Message):
    """График для самого пользователя"""
    await message.answer("⏳ Генерирую график...")

    try:
        session = Session()
        readings = session.query(GlucoseReading).filter_by(user_id=message.from_id).all()
        session.close()

        if len(readings) < 2:
            await message.answer("📭 Недостаточно данных")
            return

        # Здесь код генерации графика (можно вынести в отдельную функцию)
        await generate_and_send_plot(message, readings, message.from_id)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка")


# ============= УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК =============
@bot.on.message()
async def universal_handler(message: Message):
    """Единый универсальный обработчик"""
    logger.info(f"Универсальный обработчик: '{message.text}'")

    # СЛУЧАЙ 1: Мы ждем ввод глюкозы
    if message.from_id in user_states and user_states[message.from_id].get('waiting_for_value'):
        try:
            value = float(message.text.replace(',', '.'))

            if value < 1.0 or value > 30.0:
                await message.answer("⚠️ Значение должно быть от 1.0 до 30.0 ммоль/л")
                return

            period = user_states[message.from_id]['period']
            clean_period = period.split(' ', 1)[1] if ' ' in period else period

            session = Session()
            reading = GlucoseReading(
                user_id=message.from_id,
                value=value,
                period=clean_period,
                timestamp=datetime.now()
            )
            session.add(reading)
            session.commit()

            total_readings = session.query(GlucoseReading).filter_by(user_id=message.from_id).count()
            session.close()

            del user_states[message.from_id]

            await message.answer(
                f"✅ Сохранено: {value} ммоль/л\n"
                f"Период: {clean_period}\n"
                f"Всего записей: {total_readings}",
                keyboard=create_main_keyboard().get_json()
            )
            return

        except ValueError:
            await message.answer("❌ Введите число (пример: 5,6)")
            return

    # СЛУЧАЙ 2: Админ выбирает клиента (сообщение начинается с цифр и содержит двоеточие)
    if (is_admin(message.from_id) and
            message.text and
            message.text[0].isdigit() and
            ':' in message.text):

        try:
            vk_id = int(message.text.split(':')[0].strip())

            session = Session()
            user = session.query(User).filter_by(vk_id=vk_id).first()
            readings = session.query(GlucoseReading).filter_by(user_id=vk_id).all()
            session.close()

            if not user:
                await message.answer("❌ Клиент не найден")
                return

            if len(readings) < 2:
                await message.answer(f"📭 У клиента {user.name} недостаточно данных")
                return

            await message.answer(f"⏳ График для {user.name}...")
            await generate_and_send_plot(message, readings, vk_id, user.name)
            return

        except Exception as e:
            logger.error(f"Ошибка выбора клиента: {e}")

    # СЛУЧАЙ 3: Всё остальное - неизвестная команда
    await message.answer(
        "❓ Используйте кнопки меню",
        keyboard=create_main_keyboard().get_json()
    )


# ============= ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ ГРАФИКА =============
async def generate_and_send_plot(message: Message, readings: list, user_id: int, user_name: str = None):
    """Универсальная функция для создания и отправки графика"""
    try:
        if not user_name:
            session = Session()
            user = session.query(User).filter_by(vk_id=user_id).first()
            user_name = user.name if user else f"User_{user_id}"
            session.close()

        fig, ax = plt.subplots(figsize=(14, 8))

        all_periods = [
            'Перед завтраком', 'Перед обедом', 'Перед ужином',
            'Перед сном', 'Ночью', 'Через час после еды'
        ]

        periods_data = {period: [] for period in all_periods}
        for reading in readings:
            if reading.period in periods_data:
                periods_data[reading.period].append(reading.value)

        x_positions = range(len(all_periods))
        all_values = []

        for i, period in enumerate(all_periods):
            values = periods_data[period]
            if values:
                all_values.extend(values)
                x_jitter = np.random.normal(i, 0.05, len(values))
                color = 'orange' if period == 'Через час после еды' else 'blue'

                ax.scatter(x_jitter, values, color=color, s=150,
                           zorder=5, edgecolors='black', linewidth=2, alpha=0.8)

                for j, (x, y) in enumerate(zip(x_jitter, values)):
                    ax.annotate(f'{y:.1f}', (x, y), xytext=(0, 15),
                                textcoords='offset points', ha='center', fontsize=9,
                                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.9))

        ax.axhline(y=5.1, color='green', linewidth=2, linestyle='-', alpha=0.7, label='Цель 5.1')
        ax.axhline(y=7.0, color='red', linewidth=2, linestyle='-', alpha=0.7, label='Граница 7.0')
        ax.axhspan(5.1, 7.0, alpha=0.15, color='green')

        ax.set_xticks(x_positions)
        ax.set_xticklabels(all_periods, rotation=45, ha='right', fontsize=11)
        ax.set_ylabel('Глюкоза (ммоль/л)', fontsize=12)
        ax.set_title(f'График глюкозы: {user_name}', fontsize=16, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--', axis='y')
        ax.legend(loc='upper right')

        if all_values:
            stats_text = f"Всего замеров: {len(readings)}\n"
            stats_text += f"Среднее: {np.mean(all_values):.1f}\n"
            stats_text += f"Мин: {np.min(all_values):.1f}\n"
            stats_text += f"Макс: {np.max(all_values):.1f}"

            ax.text(1.02, 0.98, stats_text, transform=ax.transAxes,
                    fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        photo_uploader = PhotoMessageUploader(bot.api)
        photo = await photo_uploader.upload(
            file_source=buffer.getvalue(),
            peer_id=message.peer_id
        )

        await message.answer(
            f"📊 График:",
            attachment=photo,
            keyboard=create_main_keyboard().get_json()
        )

    except Exception as e:
        logger.error(f"Ошибка генерации графика: {e}")
        raise


if __name__ == "__main__":
    logger.info("Запуск бота...")
    bot.run_forever()