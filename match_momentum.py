
# -*- coding: utf-8 -*-
"""
OLD — Match Momentum.

Сбор истории статистики матчей и расчёт:
- импульса хозяев и гостей;
- температуры матча;
- динамики за 5, 10 и 15 минут;
- изменения инициативы.

Модуль не отправляет сигналы и не меняет стратегии OLD.
"""

import os
import sqlite3
import time
from pathlib import Path


# ============================================================
# НАСТРОЙКИ
# ============================================================

DATA_DIR = Path(os.getenv("DATA_DIR", "/app"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = os.getenv(
    "FOOTBALL_BOT_DB",
    str(DATA_DIR / "bot_stats.db")
)

SNAPSHOT_INTERVAL = 45
HISTORY_SECONDS = 3 * 60 * 60

WINDOWS = (5, 10, 15)


# ============================================================
# БАЗОВЫЕ ФУНКЦИИ
# ============================================================

def _number(value, default=0.0):
    try:
        result = float(value)

        if result != result:
            return float(default)

        if result in (float("inf"), float("-inf")):
            return float(default)

        return result

    except (TypeError, ValueError, OverflowError):
        return float(default)


def _connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 30000")
    return con


# ============================================================
# ИНИЦИАЛИЗАЦИЯ SQLITE И МИГРАЦИЯ
# ============================================================

def init_momentum_db():
    """
    Создаёт таблицу Momentum.

    Если таблица уже существует, аккуратно добавляет
    недостающие колонки названий команд.

    Старые снимки и таблицы OLD не удаляются.
    """

    con = None

    try:
        con = _connect()

        con.execute("""
            CREATE TABLE IF NOT EXISTS match_momentum_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                ts INTEGER NOT NULL,
                minute INTEGER NOT NULL DEFAULT 0,
                score TEXT DEFAULT '',

                team1 TEXT DEFAULT '',
                team2 TEXT DEFAULT '',

                xg1 REAL DEFAULT 0,
                xg2 REAL DEFAULT 0,

                shots_on1 INTEGER DEFAULT 0,
                shots_on2 INTEGER DEFAULT 0,

                shots_all1 INTEGER DEFAULT 0,
                shots_all2 INTEGER DEFAULT 0,

                corners1 INTEGER DEFAULT 0,
                corners2 INTEGER DEFAULT 0,

                att1 INTEGER DEFAULT 0,
                att2 INTEGER DEFAULT 0,

                red1 INTEGER DEFAULT 0,
                red2 INTEGER DEFAULT 0,

                UNIQUE(game_id, ts)
            )
        """)

        # Проверяем структуру существующей таблицы.
        columns = {
            row["name"]
            for row in con.execute(
                "PRAGMA table_info(match_momentum_snapshots)"
            ).fetchall()
        }

        # Добавляем названия команд без удаления истории.
        if "team1" not in columns:
            con.execute("""
                ALTER TABLE match_momentum_snapshots
                ADD COLUMN team1 TEXT DEFAULT ''
            """)

        if "team2" not in columns:
            con.execute("""
                ALTER TABLE match_momentum_snapshots
                ADD COLUMN team2 TEXT DEFAULT ''
            """)

        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_momentum_game_ts
            ON match_momentum_snapshots(game_id, ts)
        """)

        con.commit()

        print(
            "✅ OLD Momentum: база данных готова",
            flush=True
        )

        return True

    except Exception as exc:
        print(
            f"⚠️ OLD Momentum: ошибка инициализации БД: {exc}",
            flush=True
        )

        return False

    finally:
        if con:
            con.close()


# ============================================================
# СОЗДАНИЕ СНИМКА
# ============================================================

def _snapshot(p, now_ts):
    return {
        "game_id": str(p.get("game_id")),
        "ts": int(now_ts),

        "minute": int(_number(p.get("minute"))),
        "score": str(p.get("score") or ""),

        "team1": str(p.get("team1") or "Хозяева"),
        "team2": str(p.get("team2") or "Гости"),

        "xg1": _number(p.get("xg1")),
        "xg2": _number(p.get("xg2")),

        "shots_on1": int(_number(p.get("shots_on1"))),
        "shots_on2": int(_number(p.get("shots_on2"))),

        "shots_all1": int(_number(p.get("shots_all1"))),
        "shots_all2": int(_number(p.get("shots_all2"))),

        "corners1": int(_number(p.get("corners1"))),
        "corners2": int(_number(p.get("corners2"))),

        "att1": int(_number(p.get("att1"))),
        "att2": int(_number(p.get("att2"))),

        "red1": int(_number(p.get("red1"))),
        "red2": int(_number(p.get("red2"))),
    }


# ============================================================
# СОХРАНЕНИЕ СНИМКА
# ============================================================

def _save_snapshot(con, snap):
    previous = con.execute("""
        SELECT ts
        FROM match_momentum_snapshots
        WHERE game_id = ?
        ORDER BY ts DESC
        LIMIT 1
    """, (snap["game_id"],)).fetchone()

    if previous:
        elapsed = snap["ts"] - int(previous["ts"])

        if elapsed < SNAPSHOT_INTERVAL:
            return False

    cursor = con.execute("""
        INSERT OR IGNORE INTO match_momentum_snapshots (
            game_id,
            ts,
            minute,
            score,
            team1,
            team2,
            xg1,
            xg2,
            shots_on1,
            shots_on2,
            shots_all1,
            shots_all2,
            corners1,
            corners2,
            att1,
            att2,
            red1,
            red2
        )
        VALUES (
    :game_id,
    :ts,
    :minute,
    :score,
    :team1,
    :team2,
    :xg1,
    :xg2,
    :shots_on1,
    :shots_on2,
    :shots_all1,
    :shots_all2,
    :corners1,
    :corners2,
    :att1,
    :att2,
    :red1,
    :red2
)
    """, snap)

    return cursor.rowcount > 0


# ============================================================
# ПОИСК ИСТОРИЧЕСКОГО СНИМКА
# ============================================================

def _get_reference(con, game_id, now_ts, minutes):
    target_ts = int(now_ts) - int(minutes * 60)

    tolerance = max(
        150,
        int(minutes * 60 * 0.35)
    )

    return con.execute("""
        SELECT *
        FROM match_momentum_snapshots
        WHERE game_id = ?
          AND ts <= ?
          AND ts >= ?
        ORDER BY ts DESC
        LIMIT 1
    """, (
        str(game_id),
        target_ts,
        target_ts - tolerance
    )).fetchone()


# ============================================================
# РАСЧЁТ РАЗНИЦЫ
# ============================================================

def _delta(current, previous):
    current = _number(current)
    previous = _number(previous)

    difference = current - previous

    if difference < 0:
        return 0.0

    return difference


# ============================================================
# ИМПУЛЬС ОДНОЙ КОМАНДЫ
# ============================================================

def _team_impulse(current, previous, side):
    n = "1" if side == "home" else "2"

    xg = _delta(current[f"xg{n}"], previous[f"xg{n}"])
    sot = _delta(current[f"shots_on{n}"], previous[f"shots_on{n}"])
    shots = _delta(current[f"shots_all{n}"], previous[f"shots_all{n}"])
    corners = _delta(current[f"corners{n}"], previous[f"corners{n}"])
    attacks = _delta(current[f"att{n}"], previous[f"att{n}"])

    score = (
        xg * 8.0
        + sot * 2.5
        + shots * 0.8
        + corners * 1.2
        + attacks * 0.08
    )

    return {
        "score": round(score, 2),
        "xg_delta": round(xg, 3),
        "shots_on_delta": int(sot),
        "shots_delta": int(shots),
        "corners_delta": int(corners),
        "attacks_delta": int(attacks),
    }


# ============================================================
# РАСЧЁТ ОКНА
# ============================================================

def _window_result(con, snap, minutes):
    previous = _get_reference(
        con,
        snap["game_id"],
        snap["ts"],
        minutes
    )

    if not previous:
        return {
            "available": False,
            "minutes": minutes,
            "home": None,
            "away": None,
            "temperature": None,
            "normalized_temperature": None,
        }

    elapsed = max(
        1,
        int(snap["ts"]) - int(previous["ts"])
    )

    home = _team_impulse(snap, previous, "home")
    away = _team_impulse(snap, previous, "away")

    temperature = round(
        home["score"] + away["score"],
        2
    )

    normalized_temperature = round(
        temperature * 300.0 / elapsed,
        2
    )

    home_normalized = round(
        home["score"] * 300.0 / elapsed,
        2
    )

    away_normalized = round(
        away["score"] * 300.0 / elapsed,
        2
    )

    return {
        "available": True,
        "minutes": minutes,

        "home": home,
        "away": away,

        "temperature": temperature,
        "normalized_temperature": normalized_temperature,

        "home_normalized": home_normalized,
        "away_normalized": away_normalized,

        "reference_ts": int(previous["ts"]),
        "elapsed_seconds": elapsed,
    }


# ============================================================
# СОСТОЯНИЕ МАТЧА
# ============================================================

def _classify_state(windows):
    w5 = windows.get("5", {})
    w10 = windows.get("10", {})
    w15 = windows.get("15", {})

    if not w5.get("available"):
        return "INSUFFICIENT", "Недостаточно истории"

    current = _number(
        w5.get("normalized_temperature")
    )

    baselines = []

    for item in (w10, w15):
        if item.get("available"):
            baselines.append(
                _number(item.get("normalized_temperature"))
            )

    if not baselines:
        return "INSUFFICIENT", "Недостаточно истории"

    baseline = sum(baselines) / len(baselines)

    if current >= max(3.0, baseline * 1.25):
        return "RISING", "Активность растёт"

    if current <= baseline * 0.70:
        return "FALLING", "Активность снижается"

    return "STABLE", "Активность стабильна"


# ============================================================
# ОСНОВНОЙ РАСЧЁТ MOMENTUM
# ============================================================

def update_momentum(p, now_ts=None):
    if (
        not isinstance(p, dict)
        or p.get("game_id") is None
    ):
        return {
            "available": False,
            "state": "INSUFFICIENT"
        }

    now_ts = int(now_ts or time.time())
    snap = _snapshot(p, now_ts)

    con = None

    try:
        con = _connect()

        _save_snapshot(con, snap)

        con.execute("""
            DELETE FROM match_momentum_snapshots
            WHERE ts < ?
        """, (now_ts - HISTORY_SECONDS,))

        con.commit()

        windows = {
            str(minutes): _window_result(con, snap, minutes)
            for minutes in WINDOWS
        }

        state, state_label = _classify_state(windows)
        w5 = windows["5"]

        if w5.get("available"):
            home_score = _number(w5["home_normalized"])
            away_score = _number(w5["away_normalized"])
        else:
            home_score = 0.0
            away_score = 0.0

        if not w5.get("available"):
            leader = "unknown"
            leader_label = "Пока нет данных"

        elif (
            home_score > away_score * 1.15
            and home_score - away_score >= 1.0
        ):
            leader = "home"
            leader_label = p.get("team1") or "Хозяева"

        elif (
            away_score > home_score * 1.15
            and away_score - home_score >= 1.0
        ):
            leader = "away"
            leader_label = p.get("team2") or "Гости"

        else:
            leader = "balanced"
            leader_label = "Равная активность"

        result = {
            "available": bool(w5.get("available")),

            "state": state,
            "state_label": state_label,

            "leader": leader,
            "leader_label": leader_label,

            "home": {
                "name": p.get("team1") or "Хозяева",
                "impulse": (
                    round(home_score, 2)
                    if w5.get("available")
                    else None
                ),
            },

            "away": {
                "name": p.get("team2") or "Гости",
                "impulse": (
                    round(away_score, 2)
                    if w5.get("available")
                    else None
                ),
            },

            "temperature": w5.get("normalized_temperature"),
            "windows": windows,
            "updated_ts": now_ts,
        }

        p["momentum"] = result

        return result

    except Exception as exc:
        print(
            f"⚠️ OLD Momentum: ошибка расчёта: {exc}",
            flush=True
        )

        result = {
            "available": False,
            "state": "INSUFFICIENT"
        }

        p["momentum"] = result

        return result

    finally:
        if con:
            con.close()


# ============================================================
# СПИСОК ПОСЛЕДНИХ МАТЧЕЙ ДЛЯ САЙТА
# ============================================================

def get_recent_momentum_matches(limit=50):
    """
    Возвращает последние матчи, по которым
    собиралась история Momentum.

    Используется сайтом для выбора матча.
    """

    con = None

    try:
        con = _connect()

        limit = max(1, min(int(limit), 200))

        rows = con.execute("""
            SELECT
                m.game_id,
                m.ts,
                m.team1,
                m.team2,
                m.minute,
                m.score
            FROM match_momentum_snapshots AS m

            INNER JOIN (
                SELECT
                    game_id,
                    MAX(ts) AS last_ts
                FROM match_momentum_snapshots
                GROUP BY game_id
            ) AS latest
                ON latest.game_id = m.game_id
               AND latest.last_ts = m.ts

            ORDER BY m.ts DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [
            {
                "game_id": str(row["game_id"]),
                "ts": int(row["ts"]),
                "team1": row["team1"] or "Хозяева",
                "team2": row["team2"] or "Гости",
                "minute": int(row["minute"] or 0),
                "score": row["score"] or "",
            }
            for row in rows
        ]

    except Exception as exc:
        print(
            f"⚠️ OLD Momentum: ошибка списка матчей: {exc}",
            flush=True
        )

        return []

    finally:
        if con:
            con.close()


# ============================================================
# ИСТОРИЯ ДЛЯ ГРАФИКА САЙТА
# ============================================================

def get_momentum_history(game_id, limit=180):
    """
    Возвращает снимки матча по времени
    для построения графика на сайте.
    """

    con = None

    try:
        con = _connect()

        limit = max(1, min(int(limit), 1000))

        rows = con.execute("""
            SELECT *
            FROM match_momentum_snapshots
            WHERE game_id = ?
            ORDER BY ts DESC
            LIMIT ?
        """, (
            str(game_id),
            limit
        )).fetchall()

        return [
            dict(row)
            for row in reversed(rows)
        ]

    except Exception as exc:
        print(
            f"⚠️ OLD Momentum: ошибка чтения истории: {exc}",
            flush=True
        )

        return []

    finally:
        if con:
            con.close()


# ============================================================
# ЗАПУСК ИНИЦИАЛИЗАЦИИ
# ============================================================

init_momentum_db()
