import sqlite3
import os
from datetime import datetime

DATA_DIR = os.getenv('DATA_DIR', '/app/data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'bot_stats.db')

def init_db():
    """Создает таблицы при первом запуске."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_slug TEXT UNIQUE,
            match_name TEXT,
            league TEXT,
            start_time INTEGER,
            odds REAL,
            score INTEGER,
            xg_home REAL,
            xg_away REAL,
            home_team TEXT,
            away_team TEXT,
            status TEXT DEFAULT 'PENDING',
            profit REAL DEFAULT 0.0,
            sent_at INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def save_signal(data):
    """Сохраняет новый сигнал в БД."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    home_xg = data.get('home_stats', {}).get('avg_xg', 0.0)
    away_xg = data.get('away_stats', {}).get('avg_xg', 0.0)
    
    try:
        c.execute('''
            INSERT OR IGNORE INTO signals (match_slug, match_name, league, start_time, odds, score, xg_home, xg_away, home_team, away_team, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('match_slug', ''),
            data.get('match', ''),
            data.get('league', ''),
            data.get('start_ts', 0),
            data.get('odd_tb25', 0.0),
            data.get('score', 0),
            home_xg,
            away_xg,
            data.get('team1', ''),
            data.get('team2', ''),
            int(datetime.now().timestamp())
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error: {e}")
        return False
    finally:
        conn.close()

def get_all_signals():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM signals ORDER BY sent_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pending_signals():
    """Возвращает сигналы, которые еще не проверены."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM signals WHERE status = 'PENDING'")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_result(match_slug, goals_total):
    """Обновляет результат матча. Если голов > 2.5, то WIN."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    status = 'WIN' if goals_total > 2.5 else 'LOSE'
    
    # Берем коэффициент для расчета профита
    c.execute("SELECT odds FROM signals WHERE match_slug = ? AND status = 'PENDING'", (match_slug,))
    row = c.fetchone()
    
    if row:
        odds = row[0]
        profit = (odds - 1.0) if status == 'WIN' else -1.0 # Ставка 1 у.е.
        
        c.execute('''
            UPDATE signals 
            SET status = ?, profit = ?
            WHERE match_slug = ? AND status = 'PENDING'
        ''', (status, profit, match_slug))
        conn.commit()
        print(f"✅ БД обновлена: {match_slug} -> {status} (Профит: {profit})", flush=True)
        
    conn.close()

def get_stats():
    """Для вывода в консоль бота."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM signals")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM signals WHERE status = 'WIN'")
    wins = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM signals WHERE status = 'LOSE'")
    loses = c.fetchone()[0]
    conn.close()
    return {'total': total, 'wins': wins, 'loses': loses}
