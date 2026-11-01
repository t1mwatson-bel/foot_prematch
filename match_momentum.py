# -*- coding: utf-8 -*-
"""
OLD — Match Momentum.
Сохраняет снимки статистики матча в отдельную таблицу SQLite и рассчитывает
импульс хозяев/гостей, температуру матча и динамику за 5, 10 и 15 минут.
Модуль не отправляет сигналы и не меняет действующие стратегии.
"""
import os
import sqlite3
import time
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/app"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = os.getenv("FOOTBALL_BOT_DB", str(DATA_DIR / "bot_stats.db"))

SNAPSHOT_INTERVAL = 45
HISTORY_SECONDS = 3 * 60 * 60
WINDOWS = (5, 10, 15)


def _number(value, default=0.0):
    try:
        result = float(value)
        if result != result or result in (float("inf"), float("-inf")):
            return float(default)
        return result
    except (TypeError, ValueError, OverflowError):
        return float(default)


def _connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def init_momentum_db():
    """Создаёт отдельную таблицу, не изменяя старые таблицы OLD."""
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
                xg1 REAL DEFAULT 0, xg2 REAL DEFAULT 0,
                shots_on1 INTEGER DEFAULT 0, shots_on2 INTEGER DEFAULT 0,
                shots_all1 INTEGER DEFAULT 0, shots_all2 INTEGER DEFAULT 0,
                corners1 INTEGER DEFAULT 0, corners2 INTEGER DEFAULT 0,
                att1 INTEGER DEFAULT 0, att2 INTEGER DEFAULT 0,
                red1 INTEGER DEFAULT 0, red2 INTEGER DEFAULT 0
            )
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_momentum_game_ts
            ON match_momentum_snapshots(game_id, ts)
        """)
        con.commit()
        return True
    except Exception as exc:
        print(f"⚠️ OLD Momentum: ошибка инициализации БД: {exc}", flush=True)
        return False
    finally:
        if con:
            con.close()


def _snapshot(p, now_ts):
    return {
        "game_id": str(p.get("game_id")),
        "ts": int(now_ts),
        "minute": int(_number(p.get("minute"))),
        "score": str(p.get("score") or ""),
        "xg1": _number(p.get("xg1")), "xg2": _number(p.get("xg2")),
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


def _save_snapshot(con, snap):
    previous = con.execute("""
        SELECT ts FROM match_momentum_snapshots
        WHERE game_id = ? ORDER BY ts DESC LIMIT 1
    """, (snap["game_id"],)).fetchone()
    if previous and snap["ts"] - int(previous["ts"]) < SNAPSHOT_INTERVAL:
        return False

    con.execute("""
        INSERT INTO match_momentum_snapshots (
            game_id, ts, minute, score, xg1, xg2, shots_on1, shots_on2,
            shots_all1, shots_all2, corners1, corners2, att1, att2, red1, red2
        ) VALUES (
            :game_id, :ts, :minute, :score, :xg1, :xg2, :shots_on1, :shots_on2,
            :shots_all1, :shots_all2, :corners1, :corners2, :att1, :att2, :red1, :red2
        )
    """, snap)
    return True


def _get_reference(con, game_id, now_ts, minutes):
    target_ts = int(now_ts) - int(minutes * 60)
    tolerance = max(150, int(minutes * 60 * 0.35))
    return con.execute("""
        SELECT * FROM match_momentum_snapshots
        WHERE game_id = ? AND ts <= ? AND ts >= ?
        ORDER BY ts DESC LIMIT 1
    """, (str(game_id), target_ts, target_ts - tolerance)).fetchone()


def _delta(current, previous):
    # Накопительные счётчики при сбросе API не должны давать отрицательный импульс.
    return max(0.0, _number(current) - _number(previous))


def _team_impulse(current, previous, side):
    n = "1" if side == "home" else "2"
    xg = _delta(current[f"xg{n}"], previous[f"xg{n}"])
    sot = _delta(current[f"shots_on{n}"], previous[f"shots_on{n}"])
    shots = _delta(current[f"shots_all{n}"], previous[f"shots_all{n}"])
    corners = _delta(current[f"corners{n}"], previous[f"corners{n}"])
    attacks = _delta(current[f"att{n}"], previous[f"att{n}"])
    score = xg * 8.0 + sot * 2.5 + shots * 0.8 + corners * 1.2 + attacks * 0.08
    return {
        "score": round(score, 2),
        "xg_delta": round(xg, 3),
        "shots_on_delta": int(sot),
        "shots_delta": int(shots),
        "corners_delta": int(corners),
        "attacks_delta": int(attacks),
    }


def _window_result(con, snap, minutes):
    previous = _get_reference(con, snap["game_id"], snap["ts"], minutes)
    if not previous:
        return {
            "available": False, "minutes": minutes,
            "home": None, "away": None, "temperature": None,
        }
    home = _team_impulse(snap, previous, "home")
    away = _team_impulse(snap, previous, "away")
    return {
        "available": True,
        "minutes": minutes,
        "home": home,
        "away": away,
        "temperature": round(home["score"] + away["score"], 2),
        "reference_ts": int(previous["ts"]),
        "elapsed_seconds": int(snap["ts"] - int(previous["ts"])),
    }


def _classify_state(windows):
    w5, w10, w15 = windows.get("5", {}), windows.get("10", {}), windows.get("15", {})
    if not w5.get("available"):
        return "INSUFFICIENT", "Недостаточно истории"
    current = _number(w5.get("temperature"))
    baselines = []
    for item in (w10, w15):
        if item.get("available"):
            elapsed = max(1, _number(item.get("elapsed_seconds"), 1))
            baselines.append(_number(item.get("temperature")) * 300.0 / elapsed)
    if not baselines:
        return "INSUFFICIENT", "Недостаточно истории"
    baseline = sum(baselines) / len(baselines)
    if current >= max(3.0, baseline * 1.25):
        return "RISING", "Активность растёт"
    if current <= baseline * 0.70:
        return "FALLING", "Активность снижается"
    return "STABLE", "Активность стабильна"


def update_momentum(p, now_ts=None):
    """Сохраняет снимок и добавляет рассчитанный результат в p['momentum']."""
    if not isinstance(p, dict) or p.get("game_id") is None:
        return {"available": False, "state": "INSUFFICIENT"}
    now_ts = int(now_ts or time.time())
    snap = _snapshot(p, now_ts)
    con = None
    try:
        con = _connect()
        _save_snapshot(con, snap)
        con.execute(
            "DELETE FROM match_momentum_snapshots WHERE ts < ?",
            (now_ts - HISTORY_SECONDS,),
        )
        con.commit()

        windows = {
            str(m): _window_result(con, snap, m)
            for m in WINDOWS
        }
        state, state_label = _classify_state(windows)
        w5 = windows["5"]
        home_score = _number(w5["home"]["score"]) if w5.get("available") else 0.0
        away_score = _number(w5["away"]["score"]) if w5.get("available") else 0.0

        if not w5.get("available"):
            leader, leader_label = "unknown", "Пока нет данных"
        elif home_score > away_score * 1.15 and home_score - away_score >= 1.0:
            leader, leader_label = "home", p.get("team1") or "Хозяева"
        elif away_score > home_score * 1.15 and away_score - home_score >= 1.0:
            leader, leader_label = "away", p.get("team2") or "Гости"
        else:
            leader, leader_label = "balanced", "Равная активность"

        result = {
            "available": bool(w5.get("available")),
            "state": state,
            "state_label": state_label,
            "leader": leader,
            "leader_label": leader_label,
            "home": {
                "name": p.get("team1") or "Хозяева",
                "impulse": round(home_score, 2) if w5.get("available") else None,
            },
            "away": {
                "name": p.get("team2") or "Гости",
                "impulse": round(away_score, 2) if w5.get("available") else None,
            },
            "temperature": w5.get("temperature"),
            "windows": windows,
            "updated_ts": now_ts,
        }
        p["momentum"] = result
        return result
    except Exception as exc:
        print(f"⚠️ OLD Momentum: ошибка расчёта: {exc}", flush=True)
        result = {"available": False, "state": "INSUFFICIENT"}
        p["momentum"] = result
        return result
    finally:
        if con:
            con.close()


def get_momentum_history(game_id, limit=180):
    """Возвращает снимки матча по времени для графика на сайте."""
    con = None
    try:
        con = _connect()
        rows = con.execute("""
            SELECT * FROM match_momentum_snapshots
            WHERE game_id = ?
            ORDER BY ts DESC LIMIT ?
        """, (str(game_id), max(1, min(int(limit), 1000)))).fetchall()
        return [dict(row) for row in reversed(rows)]
    except Exception as exc:
        print(f"⚠️ OLD Momentum: ошибка чтения истории: {exc}", flush=True)
        return []
    finally:
        if con:
            con.close()


init_momentum_db()
