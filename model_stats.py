
# -*- coding: utf-8 -*-

import os
import json
import sqlite3

from datetime import datetime

import database as db


# ============================================================
# НАСТРОЙКИ
# ============================================================

MODEL_NAMES = (
    "OLD CHECKLIST 10",
    "OLD GOALS MODEL",
)

DB_PATH = db.DB_PATH


# ============================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# ============================================================

def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")

    return conn


# ============================================================
# ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ
# ============================================================

def init_db():

    os.makedirs(
        os.path.dirname(DB_PATH) or ".",
        exist_ok=True
    )

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_predictions (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                model_name TEXT NOT NULL,
                match_key TEXT NOT NULL,

                team1 TEXT NOT NULL,
                team2 TEXT NOT NULL,
                league TEXT,

                start_ts INTEGER,
                match_date TEXT,

                odds_over REAL,
                odds_under REAL,

                prediction_json TEXT NOT NULL,
                match_data_json TEXT NOT NULL,

                outcome TEXT DEFAULT 'PENDING',
                final_score TEXT,

                profit REAL DEFAULT 0,

                created_at INTEGER NOT NULL,
                result_updated_at INTEGER,

                UNIQUE(model_name, match_key)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_model_predictions_name
            ON model_predictions(model_name)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_model_predictions_outcome
            ON model_predictions(outcome)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_model_predictions_start
            ON model_predictions(start_ts)
        """)

        conn.commit()

    print(
        "✅ OLD MODEL STATS: таблица готова",
        flush=True
    )


# ============================================================
# БЕЗОПАСНОЕ ПРЕОБРАЗОВАНИЕ ДАННЫХ
# ============================================================

def safe_float(value):

    try:
        if value is None:
            return None

        result = float(value)

        if result != result:
            return None

        return result

    except (TypeError, ValueError, OverflowError):
        return None


def safe_json(data):

    try:
        return json.dumps(
            data,
            ensure_ascii=False,
            default=str
        )

    except Exception:
        return "{}"


def make_match_key(match_data):

    start_ts = match_data.get("start_ts")

    team1 = str(
        match_data.get("team1") or ""
    ).strip().lower()

    team2 = str(
        match_data.get("team2") or ""
    ).strip().lower()

    if start_ts and team1 and team2:

        return (
            f"{int(start_ts)}:"
            f"{team1}:"
            f"{team2}"
        )

    return (
        f"{team1}:"
        f"{team2}:"
        f"{match_data.get('start_time', '')}"
    )


# ============================================================
# СОХРАНЕНИЕ ПРОГНОЗА
# ============================================================

def save_prediction(
    model_name,
    match_data,
    prediction
):

    if model_name not in MODEL_NAMES:
        print(
            f"⚠️ Неизвестная модель: {model_name}",
            flush=True
        )
        return False

    if not isinstance(match_data, dict):
        return False

    if not isinstance(prediction, dict):
        return False

    team1 = str(
        match_data.get("team1") or ""
    ).strip()

    team2 = str(
        match_data.get("team2") or ""
    ).strip()

    if not team1 or not team2:
        return False

    try:
        start_ts = int(
            match_data.get("start_ts") or 0
        )
    except (TypeError, ValueError):
        start_ts = 0

    match_key = make_match_key(match_data)

    odds = match_data.get("odds") or {}

    odds_over = safe_float(
        odds.get("over_2_5")
    )

    odds_under = safe_float(
        odds.get("under_2_5")
    )

    match_date = None

    if start_ts:
        match_date = datetime.fromtimestamp(
            start_ts
        ).strftime("%Y-%m-%d")

    now_ts = int(datetime.now().timestamp())

    try:

        with get_connection() as conn:

            cursor = conn.execute("""
                INSERT OR IGNORE INTO model_predictions (

                    model_name,
                    match_key,

                    team1,
                    team2,
                    league,

                    start_ts,
                    match_date,

                    odds_over,
                    odds_under,

                    prediction_json,
                    match_data_json,

                    outcome,
                    profit,

                    created_at

                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, ?)
            """, (

                model_name,
                match_key,

                team1,
                team2,
                match_data.get("league"),

                start_ts or None,
                match_date,

                odds_over,
                odds_under,

                safe_json(prediction),
                safe_json(match_data),

                now_ts

            ))

            conn.commit()

            return cursor.rowcount > 0

    except Exception as e:

        print(
            f"❌ Ошибка сохранения прогноза "
            f"{model_name}: {e}",
            flush=True
        )

        return False


# ============================================================
# ПОЛУЧЕНИЕ СТАТИСТИКИ МОДЕЛИ
# ============================================================

def get_model_stats(model_name):

    result = {
        "model_name": model_name,
        "total": 0,
        "wins": 0,
        "loses": 0,
        "pending": 0,
        "settled": 0,
        "accuracy": 0.0,
        "profit": 0.0,
        "roi": 0.0,
        "average_odds": 0.0
    }

    try:

        with get_connection() as conn:

            rows = conn.execute("""
                SELECT
                    outcome,
                    odds_over,
                    profit
                FROM model_predictions
                WHERE model_name = ?
            """, (model_name,)).fetchall()

        result["total"] = len(rows)

        odds_values = []

        for row in rows:

            outcome = row["outcome"]

            if outcome == "WIN":
                result["wins"] += 1

            elif outcome == "LOSE":
                result["loses"] += 1

            elif outcome == "PENDING":
                result["pending"] += 1

            if outcome in ("WIN", "LOSE"):

                result["settled"] += 1

                result["profit"] += float(
                    row["profit"] or 0
                )

            odds = safe_float(
                row["odds_over"]
            )

            if odds and odds > 1:
                odds_values.append(odds)

        settled = result["settled"]

        if settled:

            result["accuracy"] = round(
                result["wins"] / settled * 100,
                2
            )

            result["roi"] = round(
                result["profit"] / settled * 100,
                2
            )

        if odds_values:

            result["average_odds"] = round(
                sum(odds_values) / len(odds_values),
                3
            )

        result["profit"] = round(
            result["profit"],
            2
        )

        return result

    except Exception as e:

        print(
            f"⚠️ Ошибка статистики {model_name}: {e}",
            flush=True
        )

        return result


# ============================================================
# ПОСЛЕДНИЕ ПРОГНОЗЫ
# ============================================================

def get_recent_predictions(
    limit=30,
    model_name=None
):

    try:

        limit = max(
            1,
            min(int(limit), 500)
        )

        with get_connection() as conn:

            if model_name:

                rows = conn.execute("""
                    SELECT *
                    FROM model_predictions
                    WHERE model_name = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (
                    model_name,
                    limit
                )).fetchall()

            else:

                rows = conn.execute("""
                    SELECT *
                    FROM model_predictions
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()

        result = []

        for row in rows:

            item = dict(row)

            try:
                item["prediction"] = json.loads(
                    item.get("prediction_json") or "{}"
                )
            except Exception:
                item["prediction"] = {}

            try:
                item["match_data"] = json.loads(
                    item.get("match_data_json") or "{}"
                )
            except Exception:
                item["match_data"] = {}

            result.append(item)

        return result

    except Exception as e:

        print(
            f"⚠️ Ошибка получения прогнозов моделей: {e}",
            flush=True
        )

        return []


# ============================================================
# СВОДКА ДВУХ МОДЕЛЕЙ
# ============================================================

def get_all_model_stats():

    return {
        name: get_model_stats(name)
        for name in MODEL_NAMES
    }


# ============================================================
# ОБНОВЛЕНИЕ РЕЗУЛЬТАТА
# ============================================================

def set_prediction_result(
    prediction_id,
    outcome,
    final_score=None
):

    if outcome not in (
        "WIN",
        "LOSE",
        "VOID"
    ):
        return False

    try:

        with get_connection() as conn:

            row = conn.execute("""
                SELECT odds_over
                FROM model_predictions
                WHERE id = ?
            """, (prediction_id,)).fetchone()

            if not row:
                return False

            odds = safe_float(
                row["odds_over"]
            )

            if outcome == "WIN":

                profit = (
                    max(0, odds - 1)
                    if odds and odds > 1
                    else 0
                )

            elif outcome == "LOSE":
                profit = -1.0

            else:
                profit = 0.0

            conn.execute("""
                UPDATE model_predictions
                SET
                    outcome = ?,
                    final_score = ?,
                    profit = ?,
                    result_updated_at = ?
                WHERE id = ?
            """, (
                outcome,
                final_score,
                profit,
                int(datetime.now().timestamp()),
                prediction_id
            ))

            conn.commit()

        return True

    except Exception as e:

        print(
            f"❌ Ошибка обновления результата модели: {e}",
            flush=True
        )

        return False
