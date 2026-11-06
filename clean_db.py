import sqlite3
import os

# Путь к твоей базе (как в database.py)
DB_PATH = "bot_stats.db" # Если база лежит в другой папке, укажи полный путь

if not os.path.exists(DB_PATH):
    print(f"❌ Файл {DB_PATH} не найден!")
    exit()

print("⏳ Подключаемся к базе...")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # 1. Удаляем старую историю матчей (старше 30 дней)
    cursor.execute("DELETE FROM match_history WHERE match_date < date('now', '-30 days')")
    print(f"🗑 Удалено старых матчей из истории: {cursor.rowcount}")

    # 2. Удаляем старые прематч-сигналы (старше 7 дней)
    cursor.execute("DELETE FROM signals WHERE sent_at < strftime('%s', 'now', '-7 days')")
    print(f"🗑 Удалено старых прематч-сигналов: {cursor.rowcount}")

    # 3. Удаляем старые лайв-сигналы (завершенные WIN/LOSE старше 7 дней)
    # PENDING не трогаем, бот сам их доработает
    cursor.execute("""
        DELETE FROM live_signals 
        WHERE status IN ('WIN', 'LOSE') 
        AND sent_at < strftime('%s', 'now', '-7 days')
    """)
    print(f"🗑 Удалено старых лайв-сигналов: {cursor.rowcount}")

    # Подтверждаем изменения
    conn.commit()
    print("✅ Данные удалены.")

    # 4. СЖАТИЕ БАЗЫ (VACUUM) - чтобы файл уменьшился в размере
    print("⏳ Сжимаем базу данных (VACUUM)... Это может занять пару секунд.")
    cursor.execute("VACUUM")
    print("✅ База данных успешно сжата!")

except Exception as e:
    print(f"❌ Произошла ошибка: {e}")
    conn.rollback()
finally:
    conn.close()
    print("🔒 Соединение закрыто. Готово!")