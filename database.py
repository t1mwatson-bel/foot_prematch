# =====================================================================
# DATABASE (SQLite)
# =====================================================================
import sqlite3
import json
from datetime import datetime

DB_PATH = "prematch.db"


def init_db():
    """Создаёт таблицы, если их нет."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Сигналы
    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            league TEXT,
            team1 TEXT,
            team2 TEXT,
            match TEXT,
            start_ts INTEGER,
            score INTEGER,
            odd_tb25 REAL,
            home_stats TEXT,
            away_stats TEXT,
            reasons TEXT,
            result TEXT,
            result_score TEXT,
            created_at INTEGER,
            checked_at INTEGER
        )
    """)

    # Статистика команд (кэш)
    c.execute("""
        CREATE TABLE IF NOT EXISTS team_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            league TEXT,
            team TEXT,
            data TEXT,
            updated_at INTEGER
        )
    """)

    conn.commit()
    conn.close()


def save_signal(signal):
    """Сохраняет сигнал в БД."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO signals (
            game_id, league, team1, team2, match, start_ts,
            score, odd_tb25, home_stats, away_stats, reasons,
            result, result_score, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        signal.get("game_id"),
        signal.get("league"),
        signal.get("team1"),
        signal.get("team2"),
        signal.get("match"),
        signal.get("start_ts"),
        signal.get("score"),
        signal.get("odd_tb25"),
        json.dumps(signal.get("home_stats"), ensure_ascii=False),
        json.dumps(signal.get("away_stats"), ensure_ascii=False),
        json.dumps(signal.get("reasons"), ensure_ascii=False),
        None,  # result
        None,  # result_score
        int(datetime.now().timestamp()),
    ))
    conn.commit()
    signal_id = c.lastrowid
    conn.close()
    return signal_id


def get_pending_signals():
    """Возвращает сигналы без результата."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM signals WHERE result IS NULL ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows


def update_result(signal_id, result, result_score):
    """Обновляет результат сигнала."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE signals
        SET result = ?, result_score = ?, checked_at = ?
        WHERE id = ?
    """, (result, result_score, int(datetime.now().timestamp()), signal_id))
    conn.commit()
    conn.close()


def get_stats():
    """Возвращает общую статистику."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM signals")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM signals WHERE result = 'win'")
    wins = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM signals WHERE result = 'lose'")
    loses = c.fetchone()[0]
    conn.close()
    return {"total": total, "wins": wins, "loses": loses}