import os
import time
import database as db

def run_cleanup():
    print("🧹 Запуск разовой очистки базы данных...", flush=True)
    try:
        with db.get_connection() as conn:
            # 1. Удаляем старую историю (старше 30 дней)
            conn.execute("DELETE FROM match_history WHERE match_date < date('now', '-30 days')")
            # 2. Удаляем старые прематч-сигналы (старше 7 дней)
            conn.execute("DELETE FROM signals WHERE sent_at < strftime('%s', 'now', '-7 days')")
            # 3. Удаляем старые лайв-сигналы (завершенные старше 7 дней)
            conn.execute("DELETE FROM live_signals WHERE status IN ('WIN', 'LOSE') AND sent_at < strftime('%s', 'now', '-7 days')")
            
            # ВАЖНО: Сохраняем удаления перед сжатием
            conn.commit() 
            
            # 4. Сжимаем базу (VACUUM)
            conn.execute("VACUUM")
        
        print("✅ База данных успешно очищена и сжата!", flush=True)
        
        # Создаем файл-флаг
        with open(".db_cleaned", "w") as f:
            f.write(str(time.time()))
            
    except Exception as e:
        print(f"❌ Ошибка при очистке базы: {e}", flush=True)