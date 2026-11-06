
from config import MOSCOW_TZ
import os
import re
import json
import sqlite3
import logging

from datetime import datetime, timezone

import database as db


# ============================================================
# НАСТРОЙКИ
# ============================================================

logger = logging.getLogger(__name__)

MODEL_NAMES = (
    "OLD CHECKLIST 10",
    "OLD GOALS MODEL",
)

# Используем существующую БД бота, но создаём отдельную таблицу.
# Таблицы live-бота не изменяются.
TABLE_NAME = "model_predictions"


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def now_ts():
    return int(datetime.now(timezone.utc).timestamp())


def normalize_team(name):
    """Нормализация названия команды для осторожной сверки."""
    if not name:
        return ""

    name = str(name).lower().strip()
    name = re.sub(r"[^\w\s]", " ", name, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name)

    return name.strip()


def safe_json(data):
    try:
        return json.dumps(
            data,
            ensure_ascii=False,
            default=str
        )
    except Exception:
        return "{}"


def get_match_date(match_data):
    """Получаем дату матча из start_ts или start_time."""
    start_ts = match_data.get("start_ts")

    if start_ts:
        try:
            return datetime.fromtimestamp(
                float(start_ts),
                timezone.utc
            ).astimezone().strftime("%Y-%m-%d")
        except Exception:
            pass

    start_time = match_data.get("start_time")

    if start_time:
        try:
            return datetime.fromisoformat(
                str(start_time).replace("Z", "+00:00")
            ).astimezone().strftime("%Y-%m-%d")
        except Exception:
            pass

    return None


def get_match_key(match_data):
    """
    Стабильный ключ матча.
    Повторное сканирование не создаёт новые прогнозы.
    """
    event_id = match_data.get("event_id")

    if event_id:
        return f"id:{event_id}"

    home = normalize_team(match_data.get("team1"))
    away = normalize_team(match_data.get("team2"))
    start_ts = match_data.get("start_ts")

    return f"{home}|{away}|{start_ts}"


def get_connection():
    return db.get_connection()


# ============================================================
# СОЗДАНИЕ ТАБЛИЦЫ
# ============================================================

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

                created_ts INTEGER,
                result_ts INTEGER,

                UNIQUE(model_name, match_key)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_predictions_date
            ON model_predictions(match_date)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_predictions_outcome
            ON model_predictions(outcome)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_predictions_model
            ON model_predictions(model_name)
        """)

        conn.commit()

        logger.info("Таблица model_predictions готова")

    finally:
        conn.close()


# ============================================================
# СОХРАНЕНИЕ ПРОГНОЗА
# ============================================================

def save_prediction(model_name, match_data, prediction):
    """
    Сохраняет прогноз модели.

    Один матч одной модели записывается только один раз.
    Уже сохранённый прогноз не перезаписывается при повторном
    сканировании.
    """

    if model_name not in MODEL_NAMES:
        logger.warning(
            "Неизвестная модель для сохранения: %s",
            model_name
        )
        return False

    if not isinstance(match_data, dict):
        return False

    if not isinstance(prediction, dict):
        return False

    home = match_data.get("team1")
    away = match_data.get("team2")

    if not home or not away:
        return False

    match_key = get_match_key(match_data)

    if not match_key:
        return False

    match_date = get_match_date(match_data)

    if not match_date:
        logger.warning(
            "Не удалось определить дату матча: %s - %s",
            home,
            away
        )
        return False

    odds_data = match_data.get("odds") or {}

    try:
        odds = float(odds_data.get("over_2_5") or 0)
    except (TypeError, ValueError):
        odds = 0.0

    start_ts = match_data.get("start_ts")

    try:
        start_ts = int(start_ts) if start_ts else None
    except (TypeError, ValueError):
        start_ts = None

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
                created_ts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
        """, (
            model_name,
            match_key,
            str(home),
            str(away),
            str(match_data.get("league") or ""),
            match_date,
            start_ts,
            odds if odds > 1 else None,
            safe_json(prediction),
            safe_json(match_data),
            now_ts()
        ))

        conn.commit()

        saved = cursor.rowcount > 0

        if saved:
            logger.info(
                "[%s] Сохранён прогноз: %s - %s",
                model_name,
                home,
                away
            )

        return saved

    except Exception:
        logger.exception(
            "Ошибка сохранения прогноза модели %s",
            model_name
        )
        return False

    finally:
        conn.close()


# ============================================================
# СВЕРКА С ИСТОРИЕЙ РЕЗУЛЬТАТОВ
# ============================================================

def sync_results_from_history():
    """
    Сверяет ожидающие прогнозы с match_history.

    Важное условие:
    - дата должна совпасть;
    - обе команды должны совпасть;
    - счёт берётся только из match_history.

    Если точного совпадения нет, прогноз остаётся PENDING.
    """

    conn = get_connection()

    updated = 0

    try:
        pending = conn.execute("""
            SELECT
                id,
                home_team,
                away_team,
                match_date
            FROM model_predictions
            WHERE outcome = 'PENDING'
        """).fetchall()

        for prediction in pending:
            prediction_id = prediction[0]
            home = normalize_team(prediction[1])
            away = normalize_team(prediction[2])
            match_date = prediction[3]

            if not home or not away or not match_date:
                continue

            history = conn.execute("""
                SELECT
                    home_team,
                    away_team,
                    home_score,
                    away_score
                FROM match_history
                WHERE match_date = ?
            """, (match_date,)).fetchall()

            found_result = None

            for row in history:
                history_home = normalize_team(row[0])
                history_away = normalize_team(row[1])

                if (
                    history_home == home
                    and history_away == away
                ):
                    found_result = row
                    break

            if found_result is None:
                continue

            try:
                home_score = int(found_result[2])
                away_score = int(found_result[3])
            except (TypeError, ValueError):
                continue

            total_goals = home_score + away_score

            # Обе модели на этом этапе оценивают ТБ 2.5.
            # Счёт 3+ означает WIN, 0-2 означает LOSE.
            outcome = "WIN" if total_goals >= 3 else "LOSE"

            final_score = f"{home_score}:{away_score}"

            cursor = conn.execute("""
                UPDATE model_predictions
                SET
                    outcome = ?,
                    final_score = ?,
                    result_ts = ?
                WHERE id = ?
                  AND outcome = 'PENDING'
            """, (
                outcome,
                final_score,
                now_ts(),
                prediction_id
            ))

            if cursor.rowcount:
                updated += 1

        conn.commit()

        if updated:
            logger.info(
                "Обновлено результатов новых моделей: %s",
                updated
            )

        return updated

    except Exception:
        logger.exception("Ошибка сверки результатов моделей")
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
                odds
            FROM model_predictions
            WHERE model_name = ?
        """, (model_name,)).fetchall()

        total = len(rows)

        wins = 0
        losses = 0
        pending = 0
        void = 0

        settled_odds = []
        profit = 0.0

        for row in rows:
            outcome = row[0]
            odds = row[1]

            if outcome == "PENDING":
                pending += 1
                continue

            if outcome == "VOID":
                void += 1
                continue

            if outcome == "WIN":
                wins += 1

                if odds and odds > 1:
                    profit += odds - 1
                    settled_odds.append(float(odds))
                else:
                    profit += 0

            elif outcome == "LOSE":
                losses += 1
                profit -= 1

                if odds and odds > 1:
                    settled_odds.append(float(odds))

        settled = wins + losses

        accuracy = (
            wins / settled * 100
            if settled else 0.0
        )

        roi = (
            profit / settled * 100
            if settled else 0.0
        )

        average_odds = (
            sum(settled_odds) / len(settled_odds)
            if settled_odds else 0.0
        )

        return {
            "model_name": model_name,
            "total": total,
            "settled": settled,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "void": void,
            "accuracy": round(accuracy, 2),
            "profit": round(profit, 2),
            "roi": round(roi, 2),
            "average_odds": round(average_odds, 3)
        }

    finally:
        conn.close()


# ============================================================
# ОБЩАЯ СТАТИСТИКА ДВУХ МОДЕЛЕЙ
# ============================================================

def get_all_stats():
    return {
        model_name: get_model_stats(model_name)
        for model_name in MODEL_NAMES
    }


# ============================================================
# ПОСЛЕДНИЕ ПРОГНОЗЫ
# ============================================================

def get_recent_predictions(model_name, limit=30):
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT
                id,
                home_team,
                away_team,
                league,
                match_date,
                odds,
                prediction_json,
                outcome,
                final_score,
                created_ts
            FROM model_predictions
            WHERE model_name = ?
            ORDER BY created_ts DESC
            LIMIT ?
        """, (
            model_name,
            int(limit)
        )).fetchall()

        result = []

        for row in rows:
            try:
                prediction_data = json.loads(row[6] or "{}")
            except Exception:
                prediction_data = {}

            result.append({
                "id": row[0],
                "home_team": row[1],
                "away_team": row[2],
                "league": row[3],
                "match_date": row[4],
                "odds": row[5],
                "prediction": prediction_data,
                "outcome": row[7],
                "final_score": row[8],
                "created_ts": row[9]
            })

        return result

    finally:
        conn.close()


# ============================================================
# СЛУЖЕБНАЯ ПРОВЕРКА
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    init_db()

    print(json.dumps(
        get_all_stats(),
        ensure_ascii=False,
        indent=2
    ))
