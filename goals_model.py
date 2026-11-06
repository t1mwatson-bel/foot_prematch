
# -*- coding: utf-8 -*-

"""
OLD GOALS MODEL
Прематч-модель вероятности ТБ 2.5.

Источники:
1. NB-Bet: xG, средние голы, пропущенные голы.
2. История команд из match_history.
3. Коэффициент ТБ 2.5 из прематч-линии.

Результат:
- вероятность ТБ 2.5;
- ожидаемые голы команд;
- Value;
- причина отсутствия прогноза.
"""

from math import exp, factorial


MODEL_NAME = "OLD GOALS MODEL"
MIN_PROBABILITY = 0.65


def safe_float(value):
    try:
        if value is None:
            return None

        result = float(value)

        if result != result or result < 0:
            return None

        return result

    except (TypeError, ValueError):
        return None


def average(values):
    values = [
        value for value in values
        if value is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def history_average(history, field):
    if not isinstance(history, list):
        return None

    values = []

    for item in history:
        if not isinstance(item, dict):
            continue

        value = safe_float(item.get(field))

        if value is not None:
            values.append(value)

    return average(values)


def poisson_probability(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0

    return (lam ** k) * exp(-lam) / factorial(k)


def probability_over_2_5(total_lambda):
    if total_lambda <= 0:
        return 0.0

    under_probability = sum(
        poisson_probability(k, total_lambda)
        for k in range(3)
    )

    return max(
        0.0,
        min(1.0, 1.0 - under_probability)
    )


def calculate_lambda(primary_values, fallback_values=None):
    """
    Рассчитывает ожидаемые голы команды.
    Основные показатели имеют одинаковый вес.
    История используется как дополнительный источник.
    """

    primary = [
        value for value in primary_values
        if value is not None
    ]

    fallback = [
        value for value in (fallback_values or [])
        if value is not None
    ]

    if primary:
        base = average(primary)

        if fallback:
            historical = average(fallback)

            # Исторические данные имеют меньший вес.
            return base * 0.75 + historical * 0.25

        return base

    if fallback:
        return average(fallback)

    return None


def evaluate(match_data):
    if not isinstance(match_data, dict):
        return {
            "model": MODEL_NAME,
            "ready": False,
            "candidate": False,
            "reason": "Некорректные входные данные"
        }

    home_stats = match_data.get("home_stats") or {}
    away_stats = match_data.get("away_stats") or {}

    history = match_data.get("history") or {}

    home_history = history.get("home") or []
    away_history = history.get("away") or []

    if not isinstance(home_stats, dict):
        home_stats = {}

    if not isinstance(away_stats, dict):
        away_stats = {}

    if not isinstance(home_history, list):
        home_history = []

    if not isinstance(away_history, list):
        away_history = []

    # --------------------------------------------------------
    # ПОКАЗАТЕЛИ NB-BET
    # --------------------------------------------------------

    home_xg = safe_float(home_stats.get("avg_xg"))
    away_xg = safe_float(away_stats.get("avg_xg"))

    home_scored = safe_float(
        home_stats.get("avg_scored_home")
    )

    home_conceded = safe_float(
        home_stats.get("avg_missed_home")
    )

    away_scored = safe_float(
        away_stats.get("avg_scored_away")
    )

    away_conceded = safe_float(
        away_stats.get("avg_missed_away")
    )

    # --------------------------------------------------------
    # ИСТОРИЯ КОМАНД
    # --------------------------------------------------------

    home_history_scored = history_average(
        home_history,
        "scored"
    )

    home_history_conceded = history_average(
        home_history,
        "conceded"
    )

    away_history_scored = history_average(
        away_history,
        "scored"
    )

    away_history_conceded = history_average(
        away_history,
        "conceded"
    )

    # --------------------------------------------------------
    # ОЖИДАЕМЫЕ ГОЛЫ ХОЗЯЕВ
    # --------------------------------------------------------

    home_primary = [
        home_scored,
        away_conceded,
        home_xg
    ]

    home_fallback = [
        home_history_scored,
        away_history_conceded
    ]

    home_lambda = calculate_lambda(
        home_primary,
        home_fallback
    )

    # --------------------------------------------------------
    # ОЖИДАЕМЫЕ ГОЛЫ ГОСТЕЙ
    # --------------------------------------------------------

    away_primary = [
        away_scored,
        home_conceded,
        away_xg
    ]

    away_fallback = [
        away_history_scored,
        home_history_conceded
    ]

    away_lambda = calculate_lambda(
        away_primary,
        away_fallback
    )

    # --------------------------------------------------------
    # ПРОВЕРКА ДАННЫХ
    # --------------------------------------------------------

    available_home = sum(
        value is not None
        for value in home_primary + home_fallback
    )

    available_away = sum(
        value is not None
        for value in away_primary + away_fallback
    )

    if home_lambda is None or away_lambda is None:
        return {
            "model": MODEL_NAME,
            "ready": False,
            "candidate": False,
            "reason": "Недостаточно данных для расчёта голов",
            "home_lambda": home_lambda,
            "away_lambda": away_lambda,
            "available_home": available_home,
            "available_away": available_away
        }

    # Защита от некорректных значений.
    home_lambda = max(0.05, min(home_lambda, 4.5))
    away_lambda = max(0.05, min(away_lambda, 4.5))

    total_lambda = home_lambda + away_lambda

    # --------------------------------------------------------
    # ВЕРОЯТНОСТЬ ТБ 2.5
    # --------------------------------------------------------

    probability = probability_over_2_5(
        total_lambda
    )

    # --------------------------------------------------------
    # КОЭФФИЦИЕНТ И VALUE
    # --------------------------------------------------------

    odds = safe_float(
        (match_data.get("odds") or {}).get("over_2_5")
    )

    if odds is not None and odds <= 1:
        odds = None

    value = None

    if odds is not None:
        value = probability * odds - 1

    # --------------------------------------------------------
    # ФИЛЬТР ПРОГНОЗА
    # --------------------------------------------------------

    ready = True

    candidate = (
        probability >= MIN_PROBABILITY
        and odds is not None
        and value is not None
        and value > 0
    )

    reasons = []

    if probability < MIN_PROBABILITY:
        reasons.append("вероятность ниже 65%")

    if odds is None:
        reasons.append("нет коэффициента ТБ 2.5")

    if value is not None and value <= 0:
        reasons.append("отрицательный Value")

    if candidate:
        reason = "Прогноз прошёл фильтр"
    else:
        reason = "; ".join(reasons)

    # --------------------------------------------------------
    # РЕЗУЛЬТАТ
    # --------------------------------------------------------

    return {
        "model": MODEL_NAME,
        "market": "OVER 2.5",

        "ready": ready,
        "candidate": candidate,

        "probability_over_2_5": probability,
        "probability_percent": probability * 100,

        "home_lambda": home_lambda,
        "away_lambda": away_lambda,
        "expected_total_goals": total_lambda,

        "odds_over_2_5": odds,

        "value": value,
        "value_percent": (
            value * 100
            if value is not None
            else None
        ),

        "available_home": available_home,
        "available_away": available_away,

        "reason": reason,

        "home_team": match_data.get("team1"),
        "away_team": match_data.get("team2"),

        "prediction": "ТБ 2.5"
    }
