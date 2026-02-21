# plots.py
import matplotlib

# Устанавливаем бэкенд Agg ДО ВСЕХ остальных импортов matplotlib
matplotlib.use('Agg')  # Важно: ДО import matplotlib.pyplot
import matplotlib.pyplot as plt
import io
import numpy as np
from datetime import datetime
from typing import List, Dict
import logging
import os

logger = logging.getLogger(__name__)

# Дополнительная проверка
logger.info(f"Matplotlib backend: {matplotlib.get_backend()}")


def generate_glucose_plot(readings: List, history: List[Dict]) -> io.BytesIO:
    """
    Генерация графика уровня глюкозы с историей
    """
    logger.info("=" * 50)
    logger.info("НАЧАЛО ГЕНЕРАЦИИ ГРАФИКА")
    logger.info(f"Matplotlib backend: {matplotlib.get_backend()}")
    logger.info(f"Получено readings: {len(readings)}")

    try:
        # Подготовка данных
        periods = []
        values = []
        colors = []

        # Сортируем по времени
        sorted_readings = sorted(readings, key=lambda x: x.timestamp)

        # Порядок периодов для читаемости
        period_order = {
            'Перед завтраком': 1,
            'Перед обедом': 2,
            'Перед ужином': 3,
            'Через час после еды': 4,
            'Перед сном': 5,
            'Ночью': 6
        }

        # Сортируем по времени и группируем по периодам
        for r in sorted_readings:
            if r.period in period_order:
                periods.append(r.period)
                values.append(r.value)
                if r.period == 'Через час после еды':
                    colors.append('orange')
                else:
                    colors.append('blue')

        logger.info(f"Подготовлено точек: {len(periods)}")

        if len(periods) < 2:
            logger.error("Недостаточно данных для графика")
            raise ValueError("Нужно минимум 2 замера")

        # Создаем фигуру
        fig = plt.figure(figsize=(15, 7))

        # Создаем два подграфика: основной и историю
        gs = fig.add_gridspec(1, 2, width_ratios=[2, 1], wspace=0.3)
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1])
        ax2.axis('off')

        # Основной график
        x_pos = range(len(periods))

        # Рисуем точки
        for i, (x, y, color) in enumerate(zip(x_pos, values, colors)):
            ax1.scatter(x, y, color=color, s=200, edgecolor='black',
                        linewidth=2, zorder=5)
            # Добавляем значение над точкой
            ax1.annotate(f'{y:.1f}', (x, y), xytext=(0, 10),
                         textcoords='offset points', ha='center',
                         fontsize=9, fontweight='bold')

        # Соединяем точки линией
        ax1.plot(x_pos, values, 'gray', linestyle='--', linewidth=2, alpha=0.7)

        # Целевые линии
        ax1.axhline(y=4.0, color='green', linewidth=2, linestyle='-',
                    alpha=0.7, label='Цель 4.0')
        ax1.axhline(y=7.0, color='red', linewidth=2, linestyle='-',
                    alpha=0.7, label='Цель 7.0')

        # Зона нормальных значений
        ax1.fill_between(x_pos, 4.0, 7.0, alpha=0.2, color='green')

        # Настройка осей
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(periods, rotation=45, ha='right', fontsize=10)
        ax1.set_ylabel('Глюкоза (ммоль/л)', fontsize=12, fontweight='bold')
        ax1.set_title('Динамика уровня глюкозы', fontsize=14, fontweight='bold', pad=20)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.legend(loc='upper right')

        # Автоматические пределы Y с запасом
        y_min = max(min(values) - 1.5, 2.0)
        y_max = max(max(values) + 1.5, 8.0)
        ax1.set_ylim(y_min, y_max)

        # Правая панель с историей
        ax2.text(0.1, 0.95, '📋 Последние записи:',
                 transform=ax2.transAxes, fontsize=12, fontweight='bold')

        y_pos = 0.85
        for record in history[:8]:
            color = 'orange' if record['period'] == 'Через час после еды' else 'black'
            # Сокращаем период для экономии места
            period_short = record['period']
            if len(period_short) > 15:
                period_short = period_short[:12] + '...'

            text = f"• {record['time']}  {record['value']:.1f}  ({period_short})"
            ax2.text(0.1, y_pos, text, transform=ax2.transAxes,
                     fontsize=9, color=color)
            y_pos -= 0.07

        # Статистика
        y_pos = 0.25
        ax2.text(0.1, y_pos, '📊 Статистика:',
                 transform=ax2.transAxes, fontsize=11, fontweight='bold')
        y_pos -= 0.06

        stats = [
            f"Среднее: {np.mean(values):.1f}",
            f"Мин: {np.min(values):.1f}",
            f"Макс: {np.max(values):.1f}",
            f"Всего: {len(values)}"
        ]

        for stat in stats:
            ax2.text(0.1, y_pos, stat, transform=ax2.transAxes, fontsize=9)
            y_pos -= 0.05

        # Сохраняем в буфер
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)

        # Проверяем размер
        buffer_size = buffer.getbuffer().nbytes
        logger.info(f"График создан, размер: {buffer_size} байт")

        if buffer_size < 100:
            logger.error("Буфер слишком маленький!")
            raise ValueError("Созданный график имеет слишком малый размер")

        # Для отладки сохраняем на диск
        debug_path = os.path.join(os.path.dirname(__file__), 'debug_plot.png')
        with open(debug_path, 'wb') as f:
            f.write(buffer.getvalue())
        logger.info(f"Отладочная копия сохранена: {debug_path}")

        return buffer

    except Exception as e:
        logger.error(f"Ошибка в generate_glucose_plot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise