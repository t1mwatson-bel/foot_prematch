
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
import time
import re

from datetime import datetime

from config import MOSCOW_TZ


# ============================================================
# НАСТРОЙКИ
# ============================================================

DATA_DIR = os.getenv("DATA_DIR", "/app")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "bot_stats.db")

MODELS = (
    "OLD CHECKLIST 10",
    "OLD GOALS MODEL",
)


# ============================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def now_ts():
    return int(time.time())


def json_dump(data):
    return json.dumps(data or {}, ensure_ascii=False, default=str)


def json_load(value):
    try:
        return json.loads(value) if value else {}
    except Exception:
        return {}


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_team(value):
    return " ".join(str(value or "").strip().lower().split())


# ============================================================
# ИНИЦИАЛИЗАЦИЯ И МИГРАЦИЯ
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
                profit REAL DEFAULT 0,
                created_ts INTEGER,
                result_ts INTEGER,
                telegram_message_id INTEGER,
                telegram_text TEXT,
                telegram_sent INTEGER DEFAULT 0,
                UNIQUE(model_name, match_key)
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(model_predictions)"
            ).fetchall()
        }

        migrations = {
            "home_team": "TEXT",
            "away_team": "TEXT",
            "league": "TEXT",
            "match_date": "TEXT",
            "start_ts": "INTEGER",
            "odds": "REAL",
            "prediction_json": "TEXT",
            "match_data_json": "TEXT",
            "outcome": "TEXT DEFAULT 'PENDING'",
            "final_score": "TEXT",
            "profit": "REAL DEFAULT 0",
            "created_ts": "INTEGER",
            "result_ts": "INTEGER",
            "telegram_message_id": "INTEGER",
            "telegram_text": "TEXT",
            "telegram_sent": "INTEGER DEFAULT 0",
        }

        for name, definition in migrations.items():
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE model_predictions "
                    f"ADD COLUMN {name} {definition}"
                )

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_predictions_name
            ON model_predictions(model_name)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_predictions_outcome
            ON model_predictions(outcome)
        """)

        conn.commit()

        print(f"✅ MODEL STATS: база готова: {DB_PATH}")

    finally:
        conn.close()


# ============================================================
# ПОДГОТОВКА ДАННЫХ МАТЧА
# ============================================================

def get_teams(match_data, prediction=None):
    match_data = match_data or {}
    prediction = prediction or {}

    # ВАЖНО:
    # main.py передаёт команды как team1 и team2.
    # Также поддерживаем старые названия полей.

    home = (
        match_data.get("team1")
        or match_data.get("home")
        or match_data.get("home_team")
        or prediction.get("team1")
        or prediction.get("home_team")
        or ""
    )

    away = (
        match_data.get("team2")
        or match_data.get("away")
        or match_data.get("away_team")
        or prediction.get("team2")
        or prediction.get("away_team")
        or ""
    )

    return str(home).strip(), str(away).strip()


def get_match_key(match_data):
    match_data = match_data or {}

    event_id = (
        match_data.get("event_id")
        or match_data.get("id")
        or match_data.get("I")
    )

    # ID события надёжнее названий и даты.
    if event_id:
        return f"event:{str(event_id).strip()}"

    home, away = get_teams(match_data)

    match_date = (
        match_data.get("start_time")
        or match_data.get("date")
        or match_data.get("match_date")
        or ""
    )

    return (
        f"{normalize_team(home)}|"
        f"{normalize_team(away)}|"
        f"{str(match_date).strip()}"
    )


def get_odds(match_data, prediction):
    odds_data = match_data.get("odds") or {}

    value = (
        odds_data.get("over_2_5")
        or prediction.get("odds_over_2_5")
        or prediction.get("odds")
        or 0
    )

    return safe_float(value)


def get_start_ts(match_data):
    value = match_data.get("start_ts")

    try:
        if value:
            return int(value)
    except (TypeError, ValueError):
        pass

    start_time = (
        match_data.get("start_time")
        or match_data.get("date")
        or match_data.get("match_date")
    )

    if start_time:
        try:
            parsed = datetime.fromisoformat(
                str(start_time).replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=MOSCOW_TZ)

            return int(parsed.timestamp())

        except Exception:
            pass

    return 0


# ============================================================
# СОХРАНЕНИЕ ПРОГНОЗА
# ============================================================

def save_prediction(model_name, match_data, prediction):
    if model_name not in MODELS:
        print(f"⚠️ Неизвестная модель: {model_name}")
        return False

    match_data = match_data or {}
    prediction = prediction or {}

    home, away = get_teams(match_data, prediction)

    if not home or not away:
        print(
            "⚠️ Не удалось сохранить прогноз: "
            "не найдены team1/team2"
        )
        return False

    match_key = get_match_key(match_data)
    odds = get_odds(match_data, prediction)

    league = (
        match_data.get("league")
        or match_data.get("liga")
        or match_data.get("league_name")
        or ""
    )

    match_date = (
        match_data.get("start_time")
        or match_data.get("date")
        or match_data.get("match_date")
        or ""
    )

    start_ts = get_start_ts(match_data)

    conn = get_connection()

    try:
        conn.execute("""
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
            home,
            away,
            str(league),
            str(match_date),
            start_ts,
            odds,
            json_dump(prediction),
            json_dump(match_data),
            now_ts(),
        ))

        conn.commit()

        row = conn.execute("""
            SELECT id
            FROM model_predictions
            WHERE model_name = ?
              AND match_key = ?
        """, (
            model_name,
            match_key,
        )).fetchone()

        if row:
            return row["id"]

        return False

    except Exception as e:
        print(f"❌ Ошибка сохранения прогноза: {e}")
        return False

    finally:
        conn.close()


# ============================================================
# TELEGRAM
# ============================================================

def set_telegram_message(prediction_id, message_id, message_text):
    conn = get_connection()

    try:
        conn.execute("""
            UPDATE model_predictions
            SET telegram_message_id = ?,
                telegram_text = ?,
                telegram_sent = 1
            WHERE id = ?
        """, (
            int(message_id),
            str(message_text),
            int(prediction_id),
        ))

        conn.commit()
        return True

    except Exception as e:
        print(f"❌ Ошибка сохранения Telegram ID: {e}")
        return False

    finally:
        conn.close()


def get_unsent_predictions():
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT *
            FROM model_predictions
            WHERE telegram_sent = 0
            ORDER BY id ASC
        """).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


# ============================================================
# ПОЛУЧЕНИЕ ПРОГНОЗА
# ============================================================

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

        result = dict(row)

        result["prediction"] = json_load(
            result.get("prediction_json")
        )

        result["match_data"] = json_load(
            result.get("match_data_json")
        )

        return result

    finally:
        conn.close()


# ============================================================
# РАСЧЁТ ПРИБЫЛИ
# ============================================================

def calculate_profit(outcome, odds):
    odds = safe_float(odds)

    if outcome == "WIN":
        return round(odds - 1, 4)

    if outcome == "LOSE":
        return -1.0

    return 0.0


# ============================================================
# ЧТЕНИЕ СЧЁТА ИЗ ИСТОРИИ
# ============================================================

def parse_score(home_score=None, away_score=None, score=None):
    # Сначала используем отдельные поля счёта.
    if home_score is not None and away_score is not None:
        try:
            return int(home_score), int(away_score)
        except (TypeError, ValueError):
            pass

    # Затем пробуем общее поле.
    value = str(score or "").strip()

    if not value:
        return None

    numbers = re.findall(r"\d+", value)

    if len(numbers) >= 2:
        try:
            return int(numbers[0]), int(numbers[1])
        except (TypeError, ValueError):
            pass

    return None


def date_part(value):
    if not value:
        return ""

    value = str(value).strip()

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        return parsed.date().isoformat()
    except Exception:
        pass

    return value[:10] if len(value) >= 10 else ""


# ============================================================
# СИНХРОНИЗАЦИЯ РЕЗУЛЬТАТОВ
# ============================================================

def sync_results_from_history():
    """
    Сверяет прогнозы Over 2.5 с таблицей match_history.

    3 и более голов = WIN.
    0, 1 или 2 гола = LOSE.

    Поддерживает home_score/away_score,
    а также final_score и score.
    """

    conn = get_connection()
    updated = []

    try:
        rows = conn.execute("""
            SELECT *
            FROM model_predictions
            WHERE outcome = 'PENDING'
        """).fetchall()

        try:
            history_columns = {
                row["name"]
                for row in conn.execute(
                    "PRAGMA table_info(match_history)"
                ).fetchall()
            }

            if not history_columns:
                return 0

        except sqlite3.OperationalError:
            return 0

        if "home_team" not in history_columns:
            return 0

        if "away_team" not in history_columns:
            return 0

        history_rows = conn.execute("""
            SELECT *
            FROM match_history
        """).fetchall()

        for row in rows:
            prediction = dict(row)

            target_home = normalize_team(
                prediction.get("home_team")
            )

            target_away = normalize_team(
                prediction.get("away_team")
            )

            if not target_home or not target_away:
                continue

            target_date = date_part(
                prediction.get("match_date")
            )

            candidates = []

            for history_row in history_rows:
                item = dict(history_row)

                history_home = normalize_team(
                    item.get("home_team")
                )

                history_away = normalize_team(
                    item.get("away_team")
                )

                if (
                    history_home != target_home
                    or history_away != target_away
                ):
                    continue

                score = parse_score(
                    item.get("home_score"),
                    item.get("away_score"),
                    (
                        item.get("final_score")
                        or item.get("score")
                    )
                )

                if not score:
                    continue

                history_date = date_part(
                    item.get("match_date")
                )

                # Если даты известны, не привязываем прогноз
                # к другой встрече этих же команд.
                if (
                    target_date
                    and history_date
                    and target_date != history_date
                ):
                    continue

                candidates.append((item, score))

            if not candidates:
                continue

            # Если есть несколько записей, берём последнюю.
            candidates.sort(
                key=lambda x: (
                    str(x[0].get("match_date") or ""),
                    int(x[0].get("id") or 0)
                ),
                reverse=True
            )

            history_item, score = candidates[0]

            home_goals, away_goals = score
            total_goals = home_goals + away_goals

            outcome = (
                "WIN" if total_goals >= 3 else "LOSE"
            )

            final_score = f"{home_goals}:{away_goals}"

            profit = calculate_profit(
                outcome,
                prediction.get("odds")
            )

            result_ts = now_ts()

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
                result_ts,
                prediction["id"],
            ))

            prediction["outcome"] = outcome
            prediction["final_score"] = final_score
            prediction["profit"] = profit

            updated.append(prediction)

        conn.commit()

    except Exception as e:
        print(
            f"❌ Ошибка синхронизации результатов: {e}"
        )
        return 0

    finally:
        conn.close()

    # Обновляем сообщения Telegram.
    if updated:
        try:
            from telegram_bot import (
                edit_telegram,
                format_with_result
            )

            for prediction in updated:
                message_id = prediction.get(
                    "telegram_message_id"
                )

                base_text = prediction.get(
                    "telegram_text"
                )

                if not message_id or not base_text:
                    continue

                result_line = (
                    f"\n\n"
                    f"{'✅ WIN' if prediction['outcome'] == 'WIN' else '❌ LOSE'}"
                    f" | Счёт: {prediction['final_score']}"
                )

                new_text = format_with_result(
                    base_text,
                    result_line
                )

                edit_telegram(
                    message_id,
                    new_text
                )

        except Exception as e:
            print(
                "⚠️ Ошибка обновления Telegram результатов: "
                f"{e}"
            )

    if updated:
        print(
            "📊 MODEL STATS: обновлено результатов: "
            f"{len(updated)}"
        )

    return len(updated)


# ============================================================
# СТАТИСТИКА ОДНОЙ МОДЕЛИ
# ============================================================

def get_model_stats(model_name):
    conn = get_connection()

    try:
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE WHEN outcome = 'WIN'
                    THEN 1 ELSE 0 END
                ) AS wins,
                SUM(
                    CASE WHEN outcome = 'LOSE'
                    THEN 1 ELSE 0 END
                ) AS losses,
                SUM(
                    CASE WHEN outcome = 'PENDING'
                    THEN 1 ELSE 0 END
                ) AS pending,
                COALESCE(SUM(profit), 0) AS profit
            FROM model_predictions
            WHERE model_name = ?
        """, (model_name,)).fetchone()

        total = row["total"] or 0
        wins = row["wins"] or 0
        losses = row["losses"] or 0
        pending = row["pending"] or 0
        profit = float(row["profit"] or 0)

        settled = wins + losses

        accuracy = (
            wins / settled * 100
            if settled else 0
        )

        roi = (
            profit / settled * 100
            if settled else 0
        )

        return {
            "model_name": model_name,
            "total": total,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "settled": settled,
            "accuracy": round(accuracy, 2),
            "profit": round(profit, 2),
            "roi": round(roi, 2),
        }

    finally:
        conn.close()


# ============================================================
# СТАТИСТИКА ВСЕХ МОДЕЛЕЙ
# ============================================================

def get_all_model_stats():
    return {
        name: get_model_stats(name)
        for name in MODELS
    }


def get_all_stats():
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT
                model_name,
                COUNT(*) AS total,
                SUM(
                    CASE WHEN outcome = 'WIN'
                    THEN 1 ELSE 0 END
                ) AS wins,
                SUM(
                    CASE WHEN outcome = 'LOSE'
                    THEN 1 ELSE 0 END
                ) AS losses,
                SUM(
                    CASE WHEN outcome = 'PENDING'
                    THEN 1 ELSE 0 END
                ) AS pending,
                COALESCE(SUM(profit), 0) AS profit
            FROM model_predictions
            GROUP BY model_name
        """).fetchall()

        result = {}

        for row in rows:
            total = row["total"] or 0
            wins = row["wins"] or 0
            losses = row["losses"] or 0
            pending = row["pending"] or 0
            profit = float(row["profit"] or 0)

            settled = wins + losses

            result[row["model_name"]] = {
                "total": total,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "settled": settled,
                "accuracy": round(
                    wins / settled * 100, 2
                ) if settled else 0,
                "profit": round(profit, 2),
                "roi": round(
                    profit / settled * 100, 2
                ) if settled else 0,
            }

        return result

    finally:
        conn.close()


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

            item["created_at"] = (
                datetime.fromtimestamp(
                    item["created_ts"],
                    MOSCOW_TZ
                ).strftime("%d.%m.%Y %H:%M")
                if item.get("created_ts") else ""
            )

            item["team1"] = item.get("home_team")
            item["team2"] = item.get("away_team")
            item["odds_over"] = item.get("odds")

            item["prediction"] = json_load(
                item.get("prediction_json")
            )

            item["match_data"] = json_load(
                item.get("match_data_json")
            )

            result.append(item)

        return result

    finally:
        conn.close()


# ============================================================
# СТАРТ
# ============================================================

if __name__ == "__main__":
    init_db()
    print("✅ MODEL STATS: модуль готов")
