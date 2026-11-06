
# -*- coding: utf-8 -*-

import os
import re
import json
import sqlite3
import logging
from datetime import datetime, date

from config import MOSCOW_TZ

logger = logging.getLogger("OLD_MODEL_STATS")

DATA_DIR = os.getenv("DATA_DIR", "/app")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "bot_stats.db")

MODEL_NAMES = (
    "OLD CHECKLIST 10",
    "OLD GOALS MODEL",
)


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _columns(conn, table):
    rows = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return {row["name"] for row in rows}


def init_db():
    conn = get_connection()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                match_key TEXT NOT NULL,
                home_team TEXT,
                away_team TEXT,
                league TEXT,
                match_date TEXT,
                start_ts INTEGER,
                odds REAL,
                prediction_json TEXT,
                match_data_json TEXT,
                outcome TEXT DEFAULT 'PENDING',
                final_score TEXT,
                profit REAL DEFAULT 0,
                created_ts INTEGER,
                result_ts INTEGER,
                telegram_message_id INTEGER,
                telegram_text TEXT,
                telegram_sent INTEGER DEFAULT 0,
                UNIQUE(model_name, match_key)
            )
        """)

        existing = _columns(conn, "model_predictions")

        migrations = {
            "profit": "REAL DEFAULT 0",
            "created_ts": "INTEGER",
            "result_ts": "INTEGER",
            "telegram_message_id": "INTEGER",
            "telegram_text": "TEXT",
            "telegram_sent": "INTEGER DEFAULT 0",
        }

        for column, definition in migrations.items():
            if column not in existing:
                conn.execute(
                    f"ALTER TABLE model_predictions "
                    f"ADD COLUMN {column} {definition}"
                )

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_model_predictions_date
            ON model_predictions(match_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_model_predictions_outcome
            ON model_predictions(outcome)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_model_predictions_model
            ON model_predictions(model_name)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_model_predictions_telegram
            ON model_predictions(telegram_sent, outcome)
        """)

        conn.commit()

        logger.info(
            "✅ Таблица статистики моделей проверена"
        )

    finally:
        conn.close()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _now_ts():
    return int(datetime.now(MOSCOW_TZ).timestamp())


def _normalize_team(name):
    value = str(name or "").lower().strip()
    value = value.replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9]+", "", value)
    return value


def _make_match_key(match_data):
    event_id = match_data.get("event_id")

    if event_id:
        return f"event:{event_id}"

    home = _normalize_team(match_data.get("team1"))
    away = _normalize_team(match_data.get("team2"))

    start_ts = match_data.get("start_ts")

    if start_ts:
        return f"{home}:{away}:{start_ts}"

    match_date = str(
        match_data.get("start_time", "")
    )[:16]

    return f"{home}:{away}:{match_date}"


def _safe_json(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str
        )
    except Exception:
        return "{}"


def _decode_json(value):
    try:
        return json.loads(value or "{}")
    except Exception:
        return {}


def _extract_odds(match_data, prediction):
    odds = None

    if isinstance(match_data, dict):
        odds_data = match_data.get("odds") or {}

        if isinstance(odds_data, dict):
            odds = odds_data.get("over_2_5")

    if odds is None and isinstance(prediction, dict):
        odds = prediction.get("odds_over_2_5")

    try:
        odds = float(odds)
        if odds <= 1:
            return None
        return odds
    except (TypeError, ValueError):
        return None


# ============================================================
# СОХРАНЕНИЕ ПРОГНОЗА
# ============================================================

def save_prediction(
    model_name,
    match_data,
    prediction
):
    if not isinstance(match_data, dict):
        return False

    if not isinstance(prediction, dict):
        return False

    home = match_data.get("team1")
    away = match_data.get("team2")

    if not home or not away:
        return False

    if model_name not in MODEL_NAMES:
        logger.warning(
            "Неизвестная модель: %s",
            model_name
        )

    match_key = _make_match_key(match_data)

    if not match_key:
        return False

    start_ts = match_data.get("start_ts")

    try:
        start_ts = int(start_ts) if start_ts else None
    except (TypeError, ValueError):
        start_ts = None

    match_date = None

    if start_ts:
        match_date = datetime.fromtimestamp(
            start_ts,
            MOSCOW_TZ
        ).strftime("%Y-%m-%d")
    else:
        match_date = str(
            match_data.get("start_time", "")
        )[:10]

    odds = _extract_odds(
        match_data,
        prediction
    )

    conn = get_connection()

    try:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO model_predictions (
                model_name,
                match_key,
                home_team,
                away_team,
                league,
                match_date,
                start_ts,
                odds,
                prediction_json,
                match_data_json,
                outcome,
                profit,
                created_ts,
                telegram_sent
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, ?, 0)
        """, (
            model_name,
            match_key,
            home,
            away,
            match_data.get("league"),
            match_date,
            start_ts,
            odds,
            _safe_json(prediction),
            _safe_json(match_data),
            _now_ts()
        ))

        inserted = cursor.rowcount > 0

        row = conn.execute("""
            SELECT id
            FROM model_predictions
            WHERE model_name = ?
              AND match_key = ?
        """, (
            model_name,
            match_key
        )).fetchone()

        conn.commit()

        if inserted:
            logger.info(
                "📊 Прогноз сохранён: %s | %s — %s",
                model_name,
                home,
                away
            )

        return row["id"] if row else False

    except Exception as e:
        logger.exception(
            "Ошибка сохранения прогноза: %s",
            e
        )
        return False

    finally:
        conn.close()


# ============================================================
# ПРИВЯЗКА TELEGRAM-СООБЩЕНИЯ
# ============================================================

def set_telegram_message(
    prediction_id,
    message_id,
    message_text
):
    if not prediction_id or not message_id:
        return False

    conn = get_connection()

    try:
        cursor = conn.execute("""
            UPDATE model_predictions
            SET telegram_message_id = ?,
                telegram_text = ?,
                telegram_sent = 1
            WHERE id = ?
        """, (
            int(message_id),
            message_text,
            int(prediction_id)
        ))

        conn.commit()

        return cursor.rowcount > 0

    except Exception as e:
        logger.exception(
            "Ошибка сохранения Telegram message_id: %s",
            e
        )
        return False

    finally:
        conn.close()


def get_prediction(prediction_id):
    conn = get_connection()

    try:
        row = conn.execute("""
            SELECT *
            FROM model_predictions
            WHERE id = ?
        """, (int(prediction_id),)).fetchone()

        if not row:
            return None

        return dict(row)

    finally:
        conn.close()


# ============================================================
# ОБНОВЛЕНИЕ TELEGRAM ПОСЛЕ РЕЗУЛЬТАТА
# ============================================================

def _edit_telegram_result(row):
    message_id = row["telegram_message_id"]

    if not message_id:
        return False

    try:
        from telegram_bot import edit_telegram

        base_text = row["telegram_text"] or ""

        score = row["final_score"] or "не указан"

        if row["outcome"] == "WIN":
            result_line = (
                f"✅ <b>РЕЗУЛЬТАТ: ЗАШЛО</b>\n"
                f"⚽ Счёт: {score}"
            )
        else:
            result_line = (
                f"❌ <b>РЕЗУЛЬТАТ: НЕ ЗАШЛО</b>\n"
                f"⚽ Счёт: {score}"
            )

        text = (
            f"{base_text.rstrip()}\n\n"
            f"{result_line}"
        )

        return edit_telegram(
            message_id,
            text
        )

    except Exception as e:
        logger.exception(
            "Ошибка обновления Telegram: %s",
            e
        )
        return False


# ============================================================
# СВЕРКА РЕЗУЛЬТАТОВ С ИСТОРИЕЙ
# ============================================================

def sync_results_from_history():
    conn = get_connection()

    updated = 0

    try:
        pending = conn.execute("""
            SELECT *
            FROM model_predictions
            WHERE outcome = 'PENDING'
        """).fetchall()

        for prediction in pending:
            home = prediction["home_team"]
            away = prediction["away_team"]
            match_date = prediction["match_date"]

            if not home or not away or not match_date:
                continue

            history = conn.execute("""
                SELECT
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    match_date
                FROM match_history
                WHERE LOWER(home_team) = LOWER(?)
                  AND LOWER(away_team) = LOWER(?)
                  AND substr(match_date, 1, 10) = ?
                ORDER BY id DESC
                LIMIT 1
            """, (
                home,
                away,
                match_date
            )).fetchone()

            if not history:
                continue

            try:
                home_score = int(history["home_score"])
                away_score = int(history["away_score"])
            except (TypeError, ValueError):
                continue

            total_goals = home_score + away_score

            outcome = (
                "WIN" if total_goals >= 3
                else "LOSE"
            )

            odds = prediction["odds"]

            if outcome == "WIN":
                profit = (
                    float(odds) - 1
                    if odds and float(odds) > 1
                    else 0
                )
            else:
                profit = -1

            final_score = (
                f"{home_score}:{away_score}"
            )

            conn.execute("""
                UPDATE model_predictions
                SET outcome = ?,
                    final_score = ?,
                    profit = ?,
                    result_ts = ?
                WHERE id = ?
                  AND outcome = 'PENDING'
            """, (
                outcome,
                final_score,
                profit,
                _now_ts(),
                prediction["id"]
            ))

            updated += 1

        conn.commit()

        # После сохранения результата обновляем Telegram.
        if updated:
            completed = conn.execute("""
                SELECT *
                FROM model_predictions
                WHERE result_ts >= ?
                  AND outcome IN ('WIN', 'LOSE')
                  AND telegram_message_id IS NOT NULL
            """, (
                _now_ts() - 120
            )).fetchall()

            for row in completed:
                _edit_telegram_result(row)

        if updated:
            logger.info(
                "🏁 Обновлено результатов моделей: %s",
                updated
            )

        return updated

    except sqlite3.OperationalError as e:
        if "no such table: match_history" in str(e):
            logger.warning(
                "Таблица match_history пока отсутствует"
            )
            return 0

        logger.exception(
            "Ошибка сверки результатов: %s",
            e
        )
        return 0

    except Exception as e:
        logger.exception(
            "Ошибка сверки результатов: %s",
            e
        )
        return 0

    finally:
        conn.close()


# ============================================================
# СТАТИСТИКА ОДНОЙ МОДЕЛИ
# ============================================================

def get_model_stats(model_name):
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT
                outcome,
                profit,
                odds
            FROM model_predictions
            WHERE model_name = ?
        """, (model_name,)).fetchall()

        total = len(rows)

        wins = sum(
            1 for row in rows
            if row["outcome"] == "WIN"
        )

        loses = sum(
            1 for row in rows
            if row["outcome"] == "LOSE"
        )

        pending = sum(
            1 for row in rows
            if row["outcome"] == "PENDING"
        )

        settled = wins + loses

        profit = sum(
            float(row["profit"] or 0)
            for row in rows
        )

        accuracy = (
            wins / settled * 100
            if settled else 0
        )

        roi = (
            profit / settled * 100
            if settled else 0
        )

        odds_values = [
            float(row["odds"])
            for row in rows
            if row["odds"] and float(row["odds"]) > 1
        ]

        average_odds = (
            sum(odds_values) / len(odds_values)
            if odds_values else 0
        )

        return {
            "model_name": model_name,
            "total": total,
            "wins": wins,
            "loses": loses,
            "pending": pending,
            "accuracy": round(accuracy, 2),
            "profit": round(profit, 2),
            "roi": round(roi, 2),
            "average_odds": round(average_odds, 2)
        }

    finally:
        conn.close()


def get_all_model_stats():
    return {
        name: get_model_stats(name)
        for name in MODEL_NAMES
    }


def get_all_stats():
    return get_all_model_stats()


# ============================================================
# ПОСЛЕДНИЕ ПРОГНОЗЫ
# ============================================================

def get_recent_predictions(limit=100):
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT *
            FROM model_predictions
            ORDER BY created_ts DESC, id DESC
            LIMIT ?
        """, (int(limit),)).fetchall()

        result = []

        for row in rows:
            item = dict(row)

            item["prediction"] = _decode_json(
                item.get("prediction_json")
            )

            item["match_data"] = _decode_json(
                item.get("match_data_json")
            )

            item["created_at"] = item.get(
                "created_ts"
            )

            item["team1"] = item.get("home_team")
            item["team2"] = item.get("away_team")

            item["odds_over"] = item.get("odds")

            result.append(item)

        return result

    finally:
        conn.close()


# ============================================================
# ПРОГНОЗЫ БЕЗ ОТПРАВКИ В TELEGRAM
# ============================================================

def get_unsent_predictions(limit=100):
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT *
            FROM model_predictions
            WHERE telegram_sent = 0
            ORDER BY created_ts ASC
            LIMIT ?
        """, (int(limit),)).fetchall()

        result = []

        for row in rows:
            item = dict(row)
            item["prediction"] = _decode_json(
                item.get("prediction_json")
            )
            item["match_data"] = _decode_json(
                item.get("match_data_json")
            )
            result.append(item)

        return result

    finally:
        conn.close()


# ============================================================
# СТАРТОВАЯ ИНИЦИАЛИЗАЦИЯ
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("OLD MODEL STATS: OK")
