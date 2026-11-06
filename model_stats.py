
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
import logging
import re

from datetime import datetime, date
from collections import defaultdict


# ============================================================
# НАСТРОЙКИ
# ============================================================

DATA_DIR = os.getenv("DATA_DIR", "/app")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "bot_stats.db")

MOSCOW_TZ = "Europe/Moscow"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OLD_MODEL_STATS")


# ============================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db():
    """Создание таблицы прогнозов без удаления старых данных."""

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

                UNIQUE(model_name, match_key)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_predictions_outcome
            ON model_predictions(outcome)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_predictions_date
            ON model_predictions(match_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_predictions_model
            ON model_predictions(model_name)
        """)

        conn.commit()

    finally:
        conn.close()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _now_ts():
    return int(datetime.now().timestamp())


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", ".").strip()
            value = re.sub(r"[^\d.\-]", "", value)

        return float(value)

    except (ValueError, TypeError):
        return default


def _safe_json(value):
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {"text": value}

    return {"value": str(value)}


def _json_dump(value):
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str
        )
    except Exception:
        return "{}"


def _normalize_team(name):
    if not name:
        return ""

    name = str(name).lower().strip()
    name = re.sub(r"[^a-zа-яё0-9]", "", name)

    return name


def _normalize_date(value):
    if not value:
        return ""

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d")
        except Exception:
            return ""

    value = str(value).strip()

    for fmt in (
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d.%m.%Y %H:%M",
    ):
        try:
            return datetime.strptime(value[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    return value[:10]


def _extract_value(data, names, default=None):
    if not isinstance(data, dict):
        return default

    for name in names:
        if name in data and data[name] is not None:
            return data[name]

    return default


# ============================================================
# СОХРАНЕНИЕ ПРОГНОЗА
# ============================================================

def save_prediction(*args, **kwargs):
    """
    Сохранение прогноза новой модели.

    Поддерживает передачу параметров через именованные аргументы
    и словари, чтобы не привязываться к одному формату вызова.
    """

    init_db()

    data = dict(kwargs)

    # Собираем словари из позиционных аргументов.
    dictionaries = [
        item for item in args
        if isinstance(item, dict)
    ]

    for item in dictionaries:
        for key, value in item.items():
            if key not in data or data[key] is None:
                data[key] = value

    # Название модели.
    model_name = _extract_value(
        data,
        ["model_name", "model", "name", "source"],
        None
    )

    if not model_name:
        for item in args:
            if isinstance(item, str) and (
                "OLD" in item.upper()
                or "CHECKLIST" in item.upper()
                or "GOALS" in item.upper()
            ):
                model_name = item
                break

    if not model_name:
        model_name = "OLD UNKNOWN MODEL"

    model_name = str(model_name)

    # Названия команд.
    home_team = _extract_value(
        data,
        ["home_team", "team1", "home", "team_home"],
        ""
    )

    away_team = _extract_value(
        data,
        ["away_team", "team2", "away", "team_away"],
        ""
    )

    # Дата матча.
    match_date = _extract_value(
        data,
        ["match_date", "date", "start_time", "datetime"],
        ""
    )

    match_date = str(match_date or "")
    normalized_date = _normalize_date(match_date)

    # Лига.
    league = _extract_value(
        data,
        ["league", "competition", "tournament"],
        ""
    )

    # Коэффициент.
    odds = _safe_float(
        _extract_value(
            data,
            ["odds", "odds_over", "coefficient", "k"],
            0
        )
    )

    # Данные прогноза.
    prediction = _extract_value(
        data,
        [
            "prediction",
            "result",
            "forecast",
            "model_result",
            "prediction_data"
        ],
        {}
    )

    prediction = _safe_json(prediction)

    # Данные матча.
    match_data = _extract_value(
        data,
        [
            "match_data",
            "match",
            "event",
            "stats",
            "features"
        ],
        {}
    )

    match_data = _safe_json(match_data)

    # Если команды не пришли отдельными аргументами,
    # пробуем получить их из данных матча.
    if isinstance(match_data, dict):
        home_team = home_team or _extract_value(
            match_data,
            ["home_team", "team1", "home"],
            ""
        )

        away_team = away_team or _extract_value(
            match_data,
            ["away_team", "team2", "away"],
            ""
        )

        league = league or _extract_value(
            match_data,
            ["league", "competition"],
            ""
        )

    # Идентификатор матча.
    match_key = _extract_value(
        data,
        ["match_key", "game_id", "event_id", "id"],
        ""
    )

    if not match_key:
        match_key = (
            f"{_normalize_team(home_team)}_"
            f"{_normalize_team(away_team)}_"
            f"{normalized_date}"
        )

    match_key = str(match_key)

    if not home_team or not away_team:
        logger.warning(
            "Прогноз не сохранён: не удалось определить команды. "
            "Модель: %s",
            model_name
        )
        return None

    start_ts = _safe_float(
        _extract_value(
            data,
            ["start_ts", "timestamp", "unix_time"],
            0
        )
    )

    if not start_ts and isinstance(match_date, str):
        try:
            start_ts = int(
                datetime.fromisoformat(
                    match_date.replace("Z", "+00:00")
                ).timestamp()
            )
        except Exception:
            start_ts = 0

    created_ts = _now_ts()

    conn = get_connection()

    try:
        conn.execute("""
            INSERT INTO model_predictions (
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
                final_score,
                profit,
                created_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', '', 0, ?)

            ON CONFLICT(model_name, match_key)
            DO UPDATE SET
                home_team = excluded.home_team,
                away_team = excluded.away_team,
                league = excluded.league,
                match_date = excluded.match_date,
                start_ts = excluded.start_ts,
                odds = CASE
                    WHEN excluded.odds > 1 THEN excluded.odds
                    ELSE model_predictions.odds
                END,
                prediction_json = excluded.prediction_json,
                match_data_json = excluded.match_data_json
            WHERE model_predictions.outcome = 'PENDING'
        """, (
            model_name,
            match_key,
            str(home_team),
            str(away_team),
            str(league or ""),
            normalized_date,
            int(start_ts),
            odds,
            _json_dump(prediction),
            _json_dump(match_data),
            created_ts
        ))

        conn.commit()

        row = conn.execute("""
            SELECT id
            FROM model_predictions
            WHERE model_name = ? AND match_key = ?
        """, (model_name, match_key)).fetchone()

        prediction_id = row["id"] if row else None

        logger.info(
            "📊 Прогноз сохранён: %s | %s — %s",
            model_name,
            home_team,
            away_team
        )

        return prediction_id

    except Exception as error:
        logger.exception(
            "Ошибка сохранения прогноза %s: %s",
            model_name,
            error
        )
        return None

    finally:
        conn.close()


# ============================================================
# СИНХРОНИЗАЦИЯ РЕЗУЛЬТАТОВ
# ============================================================

def sync_results_from_history():
    """
    Проверяет завершённые матчи из database.match_history.

    Для прогноза ТБ 2.5:
    3 и более голов — WIN.
    0, 1 или 2 гола — LOSE.
    """

    init_db()

    conn = get_connection()

    try:
        # Проверяем наличие таблицы истории.
        table = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'match_history'
        """).fetchone()

        if not table:
            logger.warning(
                "Таблица match_history пока отсутствует."
            )
            return 0

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(match_history)"
            ).fetchall()
        }

        required = {
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "match_date"
        }

        if not required.issubset(columns):
            logger.warning(
                "Структура match_history отличается от ожидаемой: %s",
                columns
            )
            return 0

        history = conn.execute("""
            SELECT
                home_team,
                away_team,
                home_score,
                away_score,
                match_date
            FROM match_history
        """).fetchall()

        predictions = conn.execute("""
            SELECT *
            FROM model_predictions
            WHERE outcome = 'PENDING'
        """).fetchall()

        updated = 0

        for prediction in predictions:
            pred_home = _normalize_team(
                prediction["home_team"]
            )

            pred_away = _normalize_team(
                prediction["away_team"]
            )

            pred_date = _normalize_date(
                prediction["match_date"]
            )

            if not pred_home or not pred_away:
                continue

            for match in history:
                hist_home = _normalize_team(
                    match["home_team"]
                )

                hist_away = _normalize_team(
                    match["away_team"]
                )

                hist_date = _normalize_date(
                    match["match_date"]
                )

                if pred_home != hist_home:
                    continue

                if pred_away != hist_away:
                    continue

                if pred_date and hist_date and pred_date != hist_date:
                    continue

                try:
                    home_score = int(match["home_score"])
                    away_score = int(match["away_score"])
                except (ValueError, TypeError):
                    continue

                total_goals = home_score + away_score

                outcome = (
                    "WIN" if total_goals >= 3
                    else "LOSE"
                )

                odds = _safe_float(
                    prediction["odds"]
                )

                if outcome == "WIN":
                    profit = odds - 1 if odds > 1 else 0
                else:
                    profit = -1

                final_score = (
                    f"{home_score}:{away_score}"
                )

                conn.execute("""
                    UPDATE model_predictions
                    SET
                        outcome = ?,
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
                break

        conn.commit()

        if updated:
            logger.info(
                "✅ MODEL STATS: обновлено результатов: %s",
                updated
            )

        return updated

    except Exception as error:
        logger.exception(
            "Ошибка синхронизации моделей: %s",
            error
        )
        return 0

    finally:
        conn.close()


# ============================================================
# ОБЩАЯ СТАТИСТИКА МОДЕЛЕЙ
# ============================================================

def get_all_model_stats():
    init_db()

    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT
                model_name,
                outcome,
                odds,
                profit
            FROM model_predictions
        """).fetchall()

        result = defaultdict(lambda: {
            "total": 0,
            "wins": 0,
            "loses": 0,
            "pending": 0,
            "accuracy": 0,
            "profit": 0,
            "roi": 0,
            "average_odds": 0
        })

        odds_data = defaultdict(list)

        for row in rows:
            name = row["model_name"]
            stats = result[name]

            stats["total"] += 1

            outcome = row["outcome"]

            if outcome == "WIN":
                stats["wins"] += 1

            elif outcome == "LOSE":
                stats["loses"] += 1

            else:
                stats["pending"] += 1

            stats["profit"] += _safe_float(
                row["profit"]
            )

            odds = _safe_float(row["odds"])

            if odds > 1:
                odds_data[name].append(odds)

        for name, stats in result.items():
            settled = stats["wins"] + stats["loses"]

            if settled:
                stats["accuracy"] = round(
                    stats["wins"] / settled * 100,
                    2
                )

                stats["roi"] = round(
                    stats["profit"] / settled * 100,
                    2
                )

            if odds_data[name]:
                stats["average_odds"] = round(
                    sum(odds_data[name]) / len(odds_data[name]),
                    3
                )

            stats["profit"] = round(
                stats["profit"],
                2
            )

        return dict(result)

    finally:
        conn.close()


# ============================================================
# ПОСЛЕДНИЕ ПРОГНОЗЫ ДЛЯ САЙТА
# ============================================================

def get_recent_predictions(limit=100):
    init_db()

    limit = max(1, min(int(limit), 1000))

    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT *
            FROM model_predictions
            ORDER BY created_ts DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        predictions = []

        for row in rows:
            prediction_data = _safe_json(
                row["prediction_json"]
            )

            match_data = _safe_json(
                row["match_data_json"]
            )

            predictions.append({
                "id": row["id"],
                "created_at": row["created_ts"] or 0,
                "model_name": row["model_name"],

                "team1": row["home_team"],
                "team2": row["away_team"],

                "home_team": row["home_team"],
                "away_team": row["away_team"],

                "match_date": row["match_date"],
                "league": row["league"],

                "odds_over": row["odds"] or 0,

                "prediction": prediction_data,
                "match_data": match_data,

                "final_score": row["final_score"] or "",
                "outcome": row["outcome"],

                "profit": row["profit"] or 0
            })

        return predictions

    finally:
        conn.close()


# ============================================================
# СЛУЖЕБНАЯ ПРОВЕРКА
# ============================================================

if __name__ == "__main__":
    init_db()

    print("===================================")
    print("OLD MODEL STATS")
    print("===================================")
    print("База:", DB_PATH)
    print("Статистика:", get_all_model_stats())
    print("Последние прогнозы:")
    print(get_recent_predictions(5))
    print("===================================")
