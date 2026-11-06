
import math
import logging


logger = logging.getLogger(__name__)

MODEL_NAME = "OLD GOALS MODEL"

# Минимум данных для расчёта
MIN_REQUIRED_FIELDS = 4

# Максимальное количество голов для суммирования распределения
MAX_GOALS = 12


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def to_float(value):
    try:
        if value is None or value == "":
            return None

        result = float(value)

        if not math.isfinite(result):
            return None

        return result

    except (TypeError, ValueError):
        return None


def get_stat(stats, *names):
    if not isinstance(stats, dict):
        return None

    for name in names:
        value = to_float(stats.get(name))

        if value is not None and value >= 0:
            return value

    return None


def poisson_probability(goals, expected_goals):
    """Вероятность конкретного количества голов по Пуассону."""

    if expected_goals < 0:
        return 0.0

    try:
        return (
            math.exp(-expected_goals)
            * expected_goals ** goals
            / math.factorial(goals)
        )
    except (OverflowError, ValueError):
        return 0.0


# ============================================================
# ОЖИДАЕМЫЕ ГОЛЫ КОМАНД
# ============================================================

def calculate_expected_goals(home, away):
    """
    Оцениваем ожидаемые голы отдельно для каждой команды.

    Используем:
    - xG;
    - среднюю результативность;
    - среднюю пропускаемость соперника.

    Приоритет xG выше, если он доступен у обеих команд.
    """

    home_xg = get_stat(home, "avg_xg")
    away_xg = get_stat(away, "avg_xg")

    home_scored = get_stat(
        home,
        "avg_scored_home",
        "avg_scored"
    )

    away_scored = get_stat(
        away,
        "avg_scored_away",
        "avg_scored"
    )

    home_conceded = get_stat(
        home,
        "avg_missed_home",
        "avg_conceded_home",
        "avg_missed"
    )

    away_conceded = get_stat(
        away,
        "avg_missed_away",
        "avg_conceded_away",
        "avg_missed"
    )

    # --------------------------------------------------------
    # Домашняя команда
    # --------------------------------------------------------

    home_values = []

    if home_xg is not None:
        home_values.append(home_xg)

    if home_scored is not None:
        home_values.append(home_scored)

    if away_conceded is not None:
        home_values.append(away_conceded)

    # --------------------------------------------------------
    # Гостевая команда
    # --------------------------------------------------------

    away_values = []

    if away_xg is not None:
        away_values.append(away_xg)

    if away_scored is not None:
        away_values.append(away_scored)

    if home_conceded is not None:
        away_values.append(home_conceded)

    # Требуем минимум два независимых показателя
    if len(home_values) < 2 or len(away_values) < 2:
        return None

    expected_home = sum(home_values) / len(home_values)
    expected_away = sum(away_values) / len(away_values)

    # Защита от некорректных экстремальных значений
    expected_home = min(max(expected_home, 0.05), 5.0)
    expected_away = min(max(expected_away, 0.05), 5.0)

    return {
        "home": expected_home,
        "away": expected_away,
        "total": expected_home + expected_away,
        "home_sources": len(home_values),
        "away_sources": len(away_values)
    }


# ============================================================
# ВЕРОЯТНОСТЬ ТБ 2.5
# ============================================================

def calculate_over_2_5(expected_home, expected_away):
    """
    Рассчитывает вероятность того, что суммарно будет
    забито минимум 3 гола.
    """

    probability_under_or_equal_2 = 0.0

    for home_goals in range(3):
        for away_goals in range(3 - home_goals):
            p_home = poisson_probability(
                home_goals,
                expected_home
            )

            p_away = poisson_probability(
                away_goals,
                expected_away
            )

            probability_under_or_equal_2 += p_home * p_away

    probability_over = 1.0 - probability_under_or_equal_2

    return min(max(probability_over, 0.0), 1.0)


# ============================================================
# РАСЧЁТ VALUE
# ============================================================

def calculate_value(probability, odds):
    """
    Value = P * коэффициент - 1.

    Например:
    вероятность 0.60, коэффициент 1.90:
    Value = 0.60 * 1.90 - 1 = 0.14 (14%).
    """

    odds = to_float(odds)

    if odds is None or odds <= 1.0:
        return None

    return probability * odds - 1.0


# ============================================================
# ОСНОВНАЯ МОДЕЛЬ
# ============================================================

def evaluate(match_data):
    if not isinstance(match_data, dict):
        return {
            "model": MODEL_NAME,
            "ready": False,
            "candidate": False,
            "reason": "Некорректные входные данные"
        }

    home = match_data.get("home_stats") or {}
    away = match_data.get("away_stats") or {}

    expected = calculate_expected_goals(home, away)

    if expected is None:
        return {
            "model": MODEL_NAME,
            "market": "OVER_2_5",
            "ready": False,
            "candidate": False,
            "probability_over_2_5": None,
            "expected_home_goals": None,
            "expected_away_goals": None,
            "expected_total_goals": None,
            "value": None,
            "reason": "Недостаточно статистических данных"
        }

    probability = calculate_over_2_5(
        expected["home"],
        expected["away"]
    )

    odds_data = match_data.get("odds") or {}

    odds = to_float(odds_data.get("over_2_5"))

    value = calculate_value(probability, odds)

    # Кандидат определяется по Value.
    # Вероятность не корректируется коэффициентом.
    candidate = (
        value is not None
        and value >= 0.05
    )

    return {
        "model": MODEL_NAME,
        "market": "OVER_2_5",
        "ready": True,
        "candidate": candidate,

        "expected_home_goals": round(
            expected["home"], 4
        ),

        "expected_away_goals": round(
            expected["away"], 4
        ),

        "expected_total_goals": round(
            expected["total"], 4
        ),

        "probability_over_2_5": round(
            probability, 6
        ),

        "probability_over_2_5_percent": round(
            probability * 100, 2
        ),

        "fair_odds": round(
            1.0 / probability, 3
        ) if probability > 0 else None,

        "bookmaker_odds": odds,

        "value": round(value, 6) if value is not None else None,

        "value_percent": round(
            value * 100, 2
        ) if value is not None else None,

        "sources": {
            "home": expected["home_sources"],
            "away": expected["away_sources"]
        },

        "reason": (
            "Положительное Value"
            if candidate
            else "Value ниже установленного порога "
            "или коэффициент отсутствует"
        )
    }


# ============================================================
# ТЕСТ
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_data = {
        "home_stats": {
            "avg_xg": 1.7,
            "avg_scored_home": 1.8,
            "avg_missed_home": 1.1
        },

        "away_stats": {
            "avg_xg": 1.3,
            "avg_scored_away": 1.2,
            "avg_missed_away": 1.4
        },

        "odds": {
            "over_2_5": 1.95
        }
    }

    result = evaluate(test_data)

    import json

    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2
    ))
