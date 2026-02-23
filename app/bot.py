from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from vkbottle import PhotoMessageUploader
from sqlalchemy import func, and_
import logging
from datetime import datetime, timedelta
import io
import matplotlib
import numpy as np
import os
import sys

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Session, User, GlucoseReading
from config import VK_GROUP_TOKEN, ADMIN_IDS

matplotlib.use('Agg')
import matplotlib.pyplot as plt

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
    keyboard.add(Text("📊 Моя статистика"), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Text("📅 За неделю"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("📅 За месяц"), color=KeyboardButtonColor.PRIMARY)

    return keyboard


def create_admin_keyboard():
    """Клавиатура для администратора"""
    keyboard = create_main_keyboard()
    keyboard.row()
    keyboard.add(Text("👥 Список клиентов"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("📊 Админ панель"), color=KeyboardButtonColor.SECONDARY)
    return keyboard


# ============= ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ =============
def get_or_create_user(vk_id: int, name: str = None):
    """Получить или создать пользователя в базе"""
    session = Session()
    try:
        user = session.query(User).filter_by(vk_id=vk_id).first()

        if not user:
            # Проверяем, является ли пользователь администратором
            is_admin = vk_id in ADMIN_IDS
            user = User(
                vk_id=vk_id,
                name=name or f"User_{vk_id}",
                is_admin=is_admin
            )
            session.add(user)
            session.commit()
            logger.info(f"Создан новый пользователь: {user.name} (admin={is_admin})")

        return user
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка в get_or_create_user: {e}")
        raise
    finally:
        session.close()


def is_admin(vk_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    session = Session()
    try:
        user = session.query(User).filter_by(vk_id=vk_id).first()
        return user and user.is_admin
    finally:
        session.close()


def get_all_users():
    """Получить список всех пользователей (кроме администраторов)"""
    session = Session()
    try:
        users = session.query(User).filter_by(is_admin=False).order_by(User.name).all()
        return users
    finally:
        session.close()


def get_user_readings(user_id: int, days: int = None):
    """
    Получить показания пользователя
    :param user_id: ID пользователя
    :param days: количество дней (None = все дни)
    """
    session = Session()
    try:
        query = session.query(GlucoseReading).filter_by(user_id=user_id)

        if days is not None:
            cutoff_date = datetime.now() - timedelta(days=days)
            query = query.filter(GlucoseReading.timestamp >= cutoff_date)

        return query.order_by(GlucoseReading.timestamp).all()
    finally:
        session.close()


def get_user_statistics(user_id: int):
    """Получить полную статистику пользователя за всё время"""
    session = Session()
    try:
        readings = session.query(GlucoseReading).filter_by(user_id=user_id).all()

        if not readings:
            return {
                'total': 0,
                'avg': 0,
                'min': 0,
                'max': 0,
                'by_period': {},
                'first_date': None,
                'last_date': None
            }

        values = [r.value for r in readings]

        # Статистика по периодам
        periods = {}
        for reading in readings:
            if reading.period not in periods:
                periods[reading.period] = []
            periods[reading.period].append(reading.value)

        period_stats = {}
        for period, vals in periods.items():
            period_stats[period] = {
                'count': len(vals),
                'avg': sum(vals) / len(vals),
                'min': min(vals),
                'max': max(vals)
            }

        return {
            'total': len(readings),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
            'by_period': period_stats,
            'first_date': min(r.timestamp for r in readings),
            'last_date': max(r.timestamp for r in readings)
        }
    finally:
        session.close()


def save_glucose_reading(user_id: int, value: float, period: str):
    """Сохранить показание глюкозы"""
    session = Session()
    try:
        reading = GlucoseReading(
            user_id=user_id,
            value=value,
            period=period,
            timestamp=datetime.now()
        )
        session.add(reading)
        session.commit()
        logger.info(f"Сохранено показание: {value} для пользователя {user_id}")

        # Получаем общее количество записей пользователя
        total = session.query(GlucoseReading).filter_by(user_id=user_id).count()
        return reading, total
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка сохранения: {e}")
        raise
    finally:
        session.close()


# ============= ОБРАБОТЧИКИ КОМАНД =============
@bot.on.message(text=["/start", "старт", "начало", "меню"])
async def start_handler(message: Message):
    """Обработчик команды старт"""
    try:
        # Получаем имя пользователя из VK
        user_info = await bot.api.users.get(message.from_id)
        user_name = f"{user_info[0].first_name} {user_info[0].last_name}" if user_info else f"User_{message.from_id}"

        user = get_or_create_user(message.from_id, user_name)
        logger.info(f"Пользователь {user.name} запустил бота")

        # Выбираем клавиатуру
        keyboard = create_admin_keyboard() if user.is_admin else create_main_keyboard()

        # Приветственное сообщение
        await message.answer(
            f"👋 Здравствуйте, {user.name}!\n"
            f"📊 Всего записей: {session.query(GlucoseReading).filter_by(user_id=message.from_id).count()}\n\n"
            f"Выберите период измерения:",
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
        f"📝 Введите показатель глюкозы для периода: *{period_text}*\n"
        f"(число от 1.0 до 30.0, например: 5.6)",
        keyboard=create_main_keyboard().get_json()
    )


@bot.on.message(text=["📊 График"])
async def plot_handler(message: Message):
    """График за всё время"""
    await message.answer("⏳ Генерирую график за всё время...")

    try:
        readings = get_user_readings(message.from_id, days=None)

        if len(readings) < 2:
            await message.answer(
                "📭 Недостаточно данных. Нужно минимум 2 замера.",
                keyboard=create_main_keyboard().get_json()
            )
            return

        await generate_and_send_plot(message, readings, message.from_id)

    except Exception as e:
        logger.error(f"Ошибка в plot_handler: {e}")
        await message.answer(
            f"❌ Ошибка при создании графика",
            keyboard=create_main_keyboard().get_json()
        )


@bot.on.message(text=["📅 За неделю"])
async def week_plot_handler(message: Message):
    """График за последнюю неделю"""
    await message.answer("⏳ Генерирую график за последнюю неделю...")

    try:
        readings = get_user_readings(message.from_id, days=7)

        if len(readings) < 2:
            await message.answer(
                "📭 Недостаточно данных за последнюю неделю",
                keyboard=create_main_keyboard().get_json()
            )
            return

        await generate_and_send_plot(message, readings, message.from_id, "за последнюю неделю")

    except Exception as e:
        logger.error(f"Ошибка в week_plot_handler: {e}")
        await message.answer(
            f"❌ Ошибка при создании графика",
            keyboard=create_main_keyboard().get_json()
        )


@bot.on.message(text=["📅 За месяц"])
async def month_plot_handler(message: Message):
    """График за последний месяц"""
    await message.answer("⏳ Генерирую график за последний месяц...")

    try:
        readings = get_user_readings(message.from_id, days=30)

        if len(readings) < 2:
            await message.answer(
                "📭 Недостаточно данных за последний месяц",
                keyboard=create_main_keyboard().get_json()
            )
            return

        await generate_and_send_plot(message, readings, message.from_id, "за последний месяц")

    except Exception as e:
        logger.error(f"Ошибка в month_plot_handler: {e}")
        await message.answer(
            f"❌ Ошибка при создании графика",
            keyboard=create_main_keyboard().get_json()
        )


@bot.on.message(text=["📊 Моя статистика"])
async def my_stats_handler(message: Message):
    """Показать статистику пользователя"""
    stats = get_user_statistics(message.from_id)

    if stats['total'] == 0:
        await message.answer(
            "📭 У вас пока нет записей",
            keyboard=create_main_keyboard().get_json()
        )
        return

    # Формируем сообщение со статистикой
    text = f"📊 **ВАША СТАТИСТИКА**\n\n"
    text += f"📈 Всего записей: {stats['total']}\n"
    text += f"📉 Среднее: {stats['avg']:.1f} ммоль/л\n"
    text += f"⬇️ Мин: {stats['min']:.1f}\n"
    text += f"⬆️ Макс: {stats['max']:.1f}\n"

    if stats['first_date']:
        text += f"📅 Первая запись: {stats['first_date'].strftime('%d.%m.%Y')}\n"
        text += f"📅 Последняя: {stats['last_date'].strftime('%d.%m.%Y')}\n\n"

    text += f"📊 **По периодам:**\n"
    for period, pstats in stats['by_period'].items():
        text += f"• {period}: {pstats['count']} зап., "
        text += f"ср. {pstats['avg']:.1f} "
        text += f"({pstats['min']:.1f}-{pstats['max']:.1f})\n"

    keyboard = create_admin_keyboard() if is_admin(message.from_id) else create_main_keyboard()
    await message.answer(text, keyboard=keyboard.get_json())


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

    keyboard = create_admin_keyboard()
    await message.answer(stats_text, keyboard=keyboard.get_json())


@bot.on.message(text=["🔙 Назад"])
async def back_handler(message: Message):
    """Вернуться в главное меню"""
    keyboard = create_admin_keyboard() if is_admin(message.from_id) else create_main_keyboard()
    await message.answer("Главное меню:", keyboard=keyboard.get_json())


# ============= УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК =============
@bot.on.message()
async def universal_handler(message: Message):
    """Единый универсальный обработчик"""
    logger.info(f"Универсальный обработчик: '{message.text}'")

    # СЛУЧАЙ 1: Обработка кнопок меню
    if message.text == "📊 Моя статистика":
        await my_stats_handler(message)
        return

    if message.text == "📊 График":
        await plot_handler(message)
        return

    if message.text == "📅 За неделю":
        await week_plot_handler(message)
        return

    if message.text == "📅 За месяц":
        await month_plot_handler(message)
        return

    # СЛУЧАЙ 2: Мы ждем ввод глюкозы
    if message.from_id in user_states and user_states[message.from_id].get('waiting_for_value'):
        try:
            # Заменяем запятую на точку для корректного преобразования
            value = float(message.text.replace(',', '.'))

            if value < 1.0 or value > 30.0:
                await message.answer("⚠️ Значение должно быть от 1.0 до 30.0 ммоль/л")
                return

            period = user_states[message.from_id]['period']
            clean_period = period.split(' ', 1)[1] if ' ' in period else period

            # Сохраняем в базу
            reading, total = save_glucose_reading(message.from_id, value, clean_period)

            del user_states[message.from_id]

            keyboard = create_admin_keyboard() if is_admin(message.from_id) else create_main_keyboard()

            await message.answer(
                f"✅ Сохранено: {value} ммоль/л\n"
                f"Период: {clean_period}\n"
                f"Всего записей: {total}",
                keyboard=keyboard.get_json()
            )
            return

        except ValueError:
            await message.answer("❌ Введите число (пример: 5,6 или 5.6)")
            return

    # СЛУЧАЙ 3: Админ выбирает клиента (сообщение начинается с цифр и содержит двоеточие)
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

    # СЛУЧАЙ 4: Всё остальное - неизвестная команда
    keyboard = create_admin_keyboard() if is_admin(message.from_id) else create_main_keyboard()
    await message.answer(
        "❓ Используйте кнопки меню",
        keyboard=keyboard.get_json()
    )


# ============= ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ ГРАФИКА =============
async def generate_and_send_plot(message: Message, readings: list, user_id: int, period_text: str = "за всё время"):
    """Универсальная функция для создания и отправки графика"""
    try:
        session = Session()
        user = session.query(User).filter_by(vk_id=user_id).first()
        user_name = user.name if user else f"User_{user_id}"
        session.close()

        logger.info(f"Создание графика для {user_name}, записей: {len(readings)}")

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
        ax.set_title(f'График глюкозы: {user_name} ({period_text})',
                     fontsize=16, fontweight='bold')
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

        keyboard = create_admin_keyboard() if is_admin(message.from_id) else create_main_keyboard()
        await message.answer(
            f"📊 График {period_text}:",
            attachment=photo,
            keyboard=keyboard.get_json()
        )

    except Exception as e:
        logger.error(f"Ошибка генерации графика: {e}")
        raise


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА ДЛЯ КОНТРОЛЯ ГЛЮКОЗЫ")
    logger.info(f"📁 База данных: {os.path.abspath('data/glucose.db')}")
    logger.info("=" * 50)
    bot.run_forever()