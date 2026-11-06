
# -*- coding: utf-8 -*-

"""
OLD CHECKLIST 10
Прематч-модель оценки вероятности результативного матча.

Telegram-фильтр находится в main.py:
отправка только при score >= 8.
"""

from statistics import mean


MODEL_NAME = "OLD CHECKLIST 10"
MARKET = "Over 2.5"

MIN_AVAILABLE = 5


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def to_float(value):
    if value is None:
        return None

    try:
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", ".").strip()

        result = float(value)

        if result != result:
            return None

        return result

    except (TypeError, ValueError):
        return None


def get_number(data, aliases):
    if not isinstance(data, dict):
        return None

    for key in aliases:
        value = to_float(data.get(key))

        if value is not None:
            return value

    return None


def normalize_rate(value):
    if value is None:
        return None

    if value > 1:
        return value / 100.0

    return value


def get_history(history):
    if not isinstance(history, list):
        return []

    result = []

    for item in history:
        if not isinstance(item, dict):
            continue

        scored = to_float(item.get("scored"))
        conceded = to_float(item.get("conceded"))
        total = to_float(item.get("total"))

        if total is None and scored is not None and conceded is not None:
            total = scored + conceded

        if scored is None or conceded is None:
            continue

        result.append({
            "scored": scored,
            "conceded": conceded,
            "total": total,
        })

    return result


def average(values):
    values = [
        value for value in values
        if value is not None
    ]

    return mean(values) if values else None


def history_metrics(history):
    games = get_history(history)

    if not games:
        return {
            "count": 0,
            "avg_scored": None,
            "avg_conceded": None,
            "avg_total": None,
            "over25_rate": None,
            "btts_rate": None,
        }

    totals = [
        game["total"]
        for game in games
        if game["total"] is not None
    ]

    over25 = [
        game for game in games
        if game["total"] is not None
    ]

    btts = [
        game for game in games
    ]

    return {
        "count": len(games),
        "avg_scored": average([
            game["scored"] for game in games
        ]),
        "avg_conceded": average([
            game["conceded"] for game in games
        ]),
        "avg_total": average(totals),
        "over25_rate": (
            sum(game["total"] >= 3 for game in over25) / len(over25)
            if over25 else None
        ),
        "btts_rate": (
            sum(
                game["scored"] >= 1 and game["conceded"] >= 1
                for game in btts
            ) / len(btts)
            if btts else None
        ),
    }


def choose_value(primary, fallback):
    return primary if primary is not None else fallback


# ============================================================
# ОСНОВНАЯ МОДЕЛЬ
# ============================================================

def evaluate(match_data):
    match_data = match_data or {}

    home = (
        match_data.get("team1")
        or match_data.get("home")
        or match_data.get("home_team")
        or "Домашняя команда"
    )

    away = (
        match_data.get("team2")
        or match_data.get("away")
        or match_data.get("away_team")
        or "Гостевая команда"
    )

    home_stats = match_data.get("home_stats") or {}
    away_stats = match_data.get("away_stats") or {}

    history = match_data.get("history") or {}

    home_history = history_metrics(
        history.get("home", [])
    )

    away_history = history_metrics(
        history.get("away", [])
    )

    # --------------------------------------------------------
    # СРЕДНИЕ ПОКАЗАТЕЛИ КОМАНД
    # --------------------------------------------------------

    home_avg_total = get_number(home_stats, [
        "avg_total_goals",
        "average_total_goals",
        "avg_goals_total",
        "goals_avg_total",
    ])

    away_avg_total = get_number(away_stats, [
        "avg_total_goals",
        "average_total_goals",
        "avg_goals_total",
        "goals_avg_total",
    ])

    home_xg = get_number(home_stats, [
        "xg",
        "avg_xg",
        "expected_goals",
        "goals_xg",
    ])

    away_xg = get_number(away_stats, [
        "xg",
        "avg_xg",
        "expected_goals",
        "goals_xg",
    ])

    home_scored = get_number(home_stats, [
        "avg_scored",
        "avg_goals_scored",
        "goals_scored_avg",
        "scored_avg",
        "goals_for",
    ])

    away_scored = get_number(away_stats, [
        "avg_scored",
        "avg_goals_scored",
        "goals_scored_avg",
        "scored_avg",
        "goals_for",
    ])

    home_conceded = get_number(home_stats, [
        "avg_conceded",
        "avg_goals_conceded",
        "goals_conceded_avg",
        "conceded_avg",
        "goals_against",
    ])

    away_conceded = get_number(away_stats, [
        "avg_conceded",
        "avg_goals_conceded",
        "goals_conceded_avg",
        "conceded_avg",
        "goals_against",
    ])

    # История используется как резервный источник,
    # если соответствующее среднее отсутствует.

    home_avg_total = choose_value(
        home_avg_total,
        home_history["avg_total"]
    )

    away_avg_total = choose_value(
        away_avg_total,
        away_history["avg_total"]
    )

    home_scored = choose_value(
        home_scored,
        home_history["avg_scored"]
    )

    away_scored = choose_value(
        away_scored,
        away_history["avg_scored"]
    )

    home_conceded = choose_value(
        home_conceded,
        home_history["avg_conceded"]
    )

    away_conceded = choose_value(
        away_conceded,
        away_history["avg_conceded"]
    )

    combined_xg = (
        home_xg + away_xg
        if home_xg is not None and away_xg is not None
        else None
    )

    combined_history = []

    if home_history["avg_total"] is not None:
        combined_history.append(home_history["avg_total"])

    if away_history["avg_total"] is not None:
        combined_history.append(away_history["avg_total"])

    combined_avg_total = average(combined_history)

    combined_btts = average([
        home_history["btts_rate"],
        away_history["btts_rate"],
    ])

    # --------------------------------------------------------
    # ДЕСЯТЬ КРИТЕРИЕВ
    # --------------------------------------------------------

    criteria = []

    def add_criterion(number, name, value, threshold, operator=">="):
        if value is None:
            passed = None
        elif operator == ">=":
            passed = value >= threshold
        else:
            passed = value <= threshold

        criteria.append({
            "number": number,
            "name": name,
            "value": round(value, 3) if value is not None else None,
            "threshold": threshold,
            "operator": operator,
            "passed": passed,
            "status": (
                "PASS" if passed is True
                else "FAIL" if passed is False
                else "NO_DATA"
            ),
        })

    # 1. Среднее количество голов в матчах домашней команды.
    add_criterion(
        1,
        "Средний тотал домашней команды",
        home_avg_total,
        2.5,
    )

    # 2. Среднее количество голов в матчах гостевой команды.
    add_criterion(
        2,
        "Средний тотал гостевой команды",
        away_avg_total,
        2.5,
    )

    # 3. Суммарный ожидаемый показатель голов.
    add_criterion(
        3,
        "Суммарный xG",
        combined_xg,
        2.7,
    )

    # 4. Результативность домашней команды.
    add_criterion(
        4,
        "Голы домашней команды за матч",
        home_scored,
        1.5,
    )

    # 5. Результативность гостевой команды.
    add_criterion(
        5,
        "Голы гостевой команды за матч",
        away_scored,
        1.2,
    )

    # 6. Пропускаемые голы домашней команды.
    add_criterion(
        6,
        "Пропускаемые голы дома",
        home_conceded,
        1.0,
    )

    # 7. Пропускаемые голы гостевой команды.
    add_criterion(
        7,
        "Пропускаемые голы гостей",
        away_conceded,
        1.0,
    )

    # 8. Доля матчей Over 2.5 в истории домашней команды.
    add_criterion(
        8,
        "История Over 2.5 домашней команды",
        home_history["over25_rate"],
        0.60,
    )

    # 9. Доля матчей Over 2.5 в истории гостевой команды.
    add_criterion(
        9,
        "История Over 2.5 гостевой команды",
        away_history["over25_rate"],
        0.60,
    )

    # 10. Доля матчей, в которых обе команды забивали.
    add_criterion(
        10,
        "История BTTS",
        combined_btts,
        0.60,
    )

    # --------------------------------------------------------
    # ИТОГОВАЯ ОЦЕНКА
    # --------------------------------------------------------

    score = sum(
        1 for item in criteria
        if item["passed"] is True
    )

    available = sum(
        1 for item in criteria
        if item["passed"] is not None
    )

    missing = [
        item["name"]
        for item in criteria
        if item["passed"] is None
    ]

    ready = available >= MIN_AVAILABLE

    candidate = True

    if not ready:
        reason = (
            f"Недостаточно данных: "
            f"{available} из 10 критериев доступны"
        )
    else:
        reason = (
            f"Набрано {score}/10; "
            f"доступно данных по {available}/10 критериям"
        )

    return {
        "model": MODEL_NAME,
        "market": MARKET,
        "ready": ready,
        "candidate": candidate,
        "score": score,
        "available": available,
        "total": 10,
        "missing": missing,
        "criteria": criteria,
        "reason": reason,
        "home_team": home,
        "away_team": away,
        "prediction": "Over 2.5",
    }
