
# -*- coding: utf-8 -*-

"""
OLD GOALS MODEL
Прематч-модель вероятности Over 2.5.

Расчёт:
1. Оцениваем ожидаемые голы домашней команды.
2. Оцениваем ожидаемые голы гостевой команды.
3. Рассчитываем вероятность тотала больше 2.5
   через распределение Пуассона.

Telegram-фильтр находится в main.py.
"""

import math


MODEL_NAME = "OLD GOALS MODEL"

MIN_PROBABILITY = 0.65

MIN_HISTORY = 3

MAX_LAMBDA = 4.5
MIN_LAMBDA = 0.15


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

        if not math.isfinite(result):
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


def average(values):
    values = [
        value for value in values
        if value is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


# ============================================================
# ИСТОРИЯ КОМАНД
# ============================================================

def parse_history(history):
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


def history_stats(history):
    games = parse_history(history)

    if not games:
        return {
            "count": 0,
            "scored": None,
            "conceded": None,
            "total": None,
            "over25": None,
        }

    totals = [
        game["total"]
        for game in games
        if game["total"] is not None
    ]

    return {
        "count": len(games),
        "scored": average([
            game["scored"] for game in games
        ]),
        "conceded": average([
            game["conceded"] for game in games
        ]),
        "total": average(totals),
        "over25": (
            sum(value >= 3 for value in totals) / len(totals)
            if totals else None
        ),
    }


# ============================================================
# РАСПРЕДЕЛЕНИЕ ПУАССОНА
# ============================================================

def poisson_probability(lam, goals):
    if lam < 0:
        return 0.0

    try:
        return (
            math.exp(-lam)
            * (lam ** goals)
            / math.factorial(goals)
        )
    except (OverflowError, ValueError):
        return 0.0


def probability_over_25(home_lambda, away_lambda):
    """
    Вероятность того, что суммарно будет 3 или более голов.
    """

    total_lambda = home_lambda + away_lambda

    probability_under_25 = (
        math.exp(-total_lambda)
        * (
            1
            + total_lambda
            + total_lambda ** 2 / 2
        )
    )

    probability = 1.0 - probability_under_25

    return clamp(probability, 0.0, 1.0)


# ============================================================
# ОЖИДАЕМЫЕ ГОЛЫ КОМАНД
# ============================================================

def estimate_team_lambda(
    scored,
    opponent_conceded,
    xg,
    history_scored,
    history_opponent_conceded,
):
    """
    Смешиваем:
    - результативность команды;
    - пропускаемость соперника;
    - xG;
    - историю команды.
    """

    estimates = []

    if scored is not None:
        estimates.append((scored, 0.30))

    if opponent_conceded is not None:
        estimates.append((opponent_conceded, 0.25))

    if xg is not None:
        estimates.append((xg, 0.30))

    if history_scored is not None:
        estimates.append((history_scored, 0.10))

    if history_opponent_conceded is not None:
        estimates.append((history_opponent_conceded, 0.05))

    if not estimates:
        return None

    total_weight = sum(weight for _, weight in estimates)

    value = sum(
        number * weight
        for number, weight in estimates
    ) / total_weight

    return clamp(value, MIN_LAMBDA, MAX_LAMBDA)


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

    home_history = history_stats(
        history.get("home", [])
    )

    away_history = history_stats(
        history.get("away", [])
    )

    # --------------------------------------------------------
    # ПОКАЗАТЕЛИ ДОМАШНЕЙ КОМАНДЫ
    # --------------------------------------------------------

    home_scored = get_number(home_stats, [
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

    home_xg = get_number(home_stats, [
        "xg",
        "avg_xg",
        "expected_goals",
        "goals_xg",
    ])

    # --------------------------------------------------------
    # ПОКАЗАТЕЛИ ГОСТЕВОЙ КОМАНДЫ
    # --------------------------------------------------------

    away_scored = get_number(away_stats, [
        "avg_scored",
        "avg_goals_scored",
        "goals_scored_avg",
        "scored_avg",
        "goals_for",
    ])

    away_conceded = get_number(away_stats, [
        "avg_conceded",
        "avg_goals_conceded",
        "goals_conceded_avg",
        "conceded_avg",
        "goals_against",
    ])

    away_xg = get_number(away_stats, [
        "xg",
        "avg_xg",
        "expected_goals",
        "goals_xg",
    ])

    # --------------------------------------------------------
    # ИСТОРИЧЕСКИЕ ПОКАЗАТЕЛИ
    # --------------------------------------------------------

    home_history_scored = home_history["scored"]
    home_history_conceded = home_history["conceded"]

    away_history_scored = away_history["scored"]
    away_history_conceded = away_history["conceded"]

    # --------------------------------------------------------
    # РАСЧЁТ ОЖИДАЕМЫХ ГОЛОВ
    # --------------------------------------------------------

    home_lambda = estimate_team_lambda(
        scored=home_scored,
        opponent_conceded=away_conceded,
        xg=home_xg,
        history_scored=home_history_scored,
        history_opponent_conceded=away_history_conceded,
    )

    away_lambda = estimate_team_lambda(
        scored=away_scored,
        opponent_conceded=home_conceded,
        xg=away_xg,
        history_scored=away_history_scored,
        history_opponent_conceded=home_history_conceded,
    )

    # Если данных недостаточно, модель не выдаёт прогноз.
    if home_lambda is None or away_lambda is None:
        return {
            "model": MODEL_NAME,
            "ready": False,
            "candidate": False,
            "reason": "Недостаточно данных для расчёта ожидаемых голов",
            "probability_over_2_5": 0,
            "home_lambda": home_lambda,
            "away_lambda": away_lambda,
        }

    # --------------------------------------------------------
    # ВЕРОЯТНОСТЬ OVER 2.5
    # --------------------------------------------------------

    probability = probability_over_25(
        home_lambda,
        away_lambda,
    )

    probability_percent = round(probability * 100, 2)

    # --------------------------------------------------------
    # КОЭФФИЦИЕНТ И VALUE
    # --------------------------------------------------------

    odds_data = match_data.get("odds") or {}

    odds = get_number(odds_data, [
        "over_2_5",
        "over25",
        "total_over_2_5",
    ])

    if odds is None:
        odds = get_number(match_data, [
            "odds_over_2_5",
        ])

    if odds is not None and odds > 1:
        value = probability * odds - 1
        value_percent = round(value * 100, 2)
    else:
        value = None
        value_percent = None

    # --------------------------------------------------------
    # ГОТОВНОСТЬ МОДЕЛИ
    # --------------------------------------------------------

    history_available = (
        home_history["count"] >= MIN_HISTORY
        and away_history["count"] >= MIN_HISTORY
    )

    # Не выдаём высокий уровень уверенности,
    # если нет истории и ключевых показателей.
    data_available = sum([
        home_scored is not None,
        home_conceded is not None,
        home_xg is not None,
        away_scored is not None,
        away_conceded is not None,
        away_xg is not None,
    ])

    ready = data_available >= 2

    candidate = (
        ready
        and probability >= MIN_PROBABILITY
        and value is not None
        and value > 0
    )

    if not ready:
        reason = "Недостаточно исходных показателей"
    elif probability < MIN_PROBABILITY:
        reason = "Вероятность ниже установленного порога 65%"
    elif value is None:
        reason = "Нет коэффициента Over 2.5 для расчёта Value"
    elif value <= 0:
        reason = "Отрицательный или нулевой Value"
    else:
        reason = "Прогноз прошёл фильтр вероятности и Value"

    return {
        "model": MODEL_NAME,
        "market": "Over 2.5",
        "ready": ready,
        "candidate": candidate,
        "probability_over_2_5": probability,
        "probability_percent": probability_percent,
        "home_lambda": round(home_lambda, 3),
        "away_lambda": round(away_lambda, 3),
        "expected_total_goals": round(
            home_lambda + away_lambda,
            3
        ),
        "odds_over_2_5": odds,
        "value": value,
        "value_percent": value_percent,
        "history_available": history_available,
        "home_history_games": home_history["count"],
        "away_history_games": away_history["count"],
        "reason": reason,
        "home_team": home,
        "away_team": away,
        "prediction": "Over 2.5",
    }
