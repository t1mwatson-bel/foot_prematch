
import logging


logger = logging.getLogger(__name__)

MODEL_NAME = "OLD CHECKLIST 10"

# Минимальное количество подтверждённых критериев
MIN_AVAILABLE = 5

# Минимальная оценка для отметки сильного кандидата
MIN_SCORE = 7


def to_float(value):
    try:
        if value is None or value == "":
            return None

        result = float(value)

        if result != result:
            return None

        return result
    except (TypeError, ValueError):
        return None


def get_stat(stats, *names):
    if not isinstance(stats, dict):
        return None

    for name in names:
        value = to_float(stats.get(name))

        if value is not None:
            return value

    return None


def add_criterion(items, name, value, condition, explanation):
    """
    Критерий получает балл только при наличии данных
    и выполнении условия.
    """

    if value is None:
        items.append({
            "name": name,
            "passed": None,
            "value": None,
            "explanation": "Нет достаточных данных"
        })
        return

    passed = bool(condition(value))

    items.append({
        "name": name,
        "passed": passed,
        "value": round(value, 3),
        "explanation": explanation if passed else "Критерий не выполнен"
    })


def evaluate(match_data):
    """
    OLD CHECKLIST 10.

    Основной рынок: ТБ 2.5.

    Возвращает:
    - score: выполненные критерии;
    - available: количество проверяемых критериев;
    - criteria: подробности;
    - ready: достаточно ли данных;
    - candidate: достигнут ли минимальный балл.

    Это экспертный чек-лист, а не математическая вероятность.
    """

    if not isinstance(match_data, dict):
        return {
            "model": MODEL_NAME,
            "ready": False,
            "candidate": False,
            "score": 0,
            "available": 0,
            "total": 10,
            "criteria": [],
            "reason": "Некорректные входные данные"
        }

    home = match_data.get("home_stats") or {}
    away = match_data.get("away_stats") or {}

    history = match_data.get("history") or {}
    home_history = history.get("home") or []
    away_history = history.get("away") or []

    criteria = []

    # --------------------------------------------------------
    # 1. Средний тотал голов хозяев дома
    # --------------------------------------------------------

    home_total = get_stat(
        home,
        "avg_total",
        "average_total"
    )

    add_criterion(
        criteria,
        "Средний тотал хозяев",
        home_total,
        lambda x: x >= 2.5,
        "Средний тотал хозяев не ниже 2.5"
    )

    # --------------------------------------------------------
    # 2. Средний тотал гостей в гостях
    # --------------------------------------------------------

    away_total = get_stat(
        away,
        "avg_total",
        "average_total"
    )

    add_criterion(
        criteria,
        "Средний тотал гостей",
        away_total,
        lambda x: x >= 2.5,
        "Средний тотал гостей не ниже 2.5"
    )

    # --------------------------------------------------------
    # 3. Совокупный xG
    # --------------------------------------------------------

    home_xg = get_stat(home, "avg_xg")
    away_xg = get_stat(away, "avg_xg")

    combined_xg = (
        home_xg + away_xg
        if home_xg is not None and away_xg is not None
        else None
    )

    add_criterion(
        criteria,
        "Совокупный xG",
        combined_xg,
        lambda x: x >= 2.7,
        "Совокупный xG не ниже 2.7"
    )

    # --------------------------------------------------------
    # 4. Средняя результативность хозяев
    # --------------------------------------------------------

    home_scored = get_stat(
        home,
        "avg_scored_home",
        "avg_scored"
    )

    add_criterion(
        criteria,
        "Атака хозяев",
        home_scored,
        lambda x: x >= 1.5,
        "Хозяева забивают в среднем не менее 1.5"
    )

    # --------------------------------------------------------
    # 5. Средняя результативность гостей
    # --------------------------------------------------------

    away_scored = get_stat(
        away,
        "avg_scored_away",
        "avg_scored"
    )

    add_criterion(
        criteria,
        "Атака гостей",
        away_scored,
        lambda x: x >= 1.2,
        "Гости забивают в среднем не менее 1.2"
    )

    # --------------------------------------------------------
    # 6. Пропускаемость хозяев
    # --------------------------------------------------------

    home_conceded = get_stat(
        home,
        "avg_missed_home",
        "avg_conceded_home",
        "avg_missed"
    )

    add_criterion(
        criteria,
        "Пропускаемость хозяев",
        home_conceded,
        lambda x: x >= 1.0,
        "Хозяева пропускают в среднем не менее 1 гола"
    )

    # --------------------------------------------------------
    # 7. Пропускаемость гостей
    # --------------------------------------------------------

    away_conceded = get_stat(
        away,
        "avg_missed_away",
        "avg_conceded_away",
        "avg_missed"
    )

    add_criterion(
        criteria,
        "Пропускаемость гостей",
        away_conceded,
        lambda x: x >= 1.0,
        "Гости пропускают в среднем не менее 1 гола"
    )

    # --------------------------------------------------------
    # 8. История голов хозяев дома
    # --------------------------------------------------------

    home_history_totals = []

    for game in home_history:
        if not isinstance(game, dict):
            continue

        if game.get("is_home") is not True:
            continue

        total = to_float(game.get("total"))

        if total is not None:
            home_history_totals.append(total)

    home_history_rate = (
        sum(1 for x in home_history_totals if x >= 3)
        / len(home_history_totals)
        if len(home_history_totals) >= 3
        else None
    )

    add_criterion(
        criteria,
        "ТБ 2.5 в домашних матчах хозяев",
        home_history_rate,
        lambda x: x >= 0.60,
        "Не менее 60% домашних матчей завершились с 3+ голами"
    )

    # --------------------------------------------------------
    # 9. История голов гостей на выезде
    # --------------------------------------------------------

    away_history_totals = []

    for game in away_history:
        if not isinstance(game, dict):
            continue

        if game.get("is_home") is not False:
            continue

        total = to_float(game.get("total"))

        if total is not None:
            away_history_totals.append(total)

    away_history_rate = (
        sum(1 for x in away_history_totals if x >= 3)
        / len(away_history_totals)
        if len(away_history_totals) >= 3
        else None
    )

    add_criterion(
        criteria,
        "ТБ 2.5 в выездных матчах гостей",
        away_history_rate,
        lambda x: x >= 0.60,
        "Не менее 60% выездных матчей завершились с 3+ голами"
    )

    # --------------------------------------------------------
    # 10. Совокупная результативность по истории
    # --------------------------------------------------------

    history_totals = (
        home_history_totals + away_history_totals
    )

    history_average = (
        sum(history_totals) / len(history_totals)
        if len(history_totals) >= 6
        else None
    )

    add_criterion(
        criteria,
        "Средний тотал по истории",
        history_average,
        lambda x: x >= 2.8,
        "Средний тотал последних домашних и выездных матчей не ниже 2.8"
    )

    # --------------------------------------------------------
    # РЕЗУЛЬТАТ
    # --------------------------------------------------------

    passed = sum(
        1 for item in criteria
        if item["passed"] is True
    )

    available = sum(
        1 for item in criteria
        if item["passed"] is not None
    )

    missing = sum(
        1 for item in criteria
        if item["passed"] is None
    )

    ready = available >= MIN_AVAILABLE

    candidate = (
        ready
        and passed >= MIN_SCORE
    )

    return {
        "model": MODEL_NAME,
        "market": "OVER_2_5",
        "ready": ready,
        "candidate": candidate,
        "score": passed,
        "available": available,
        "missing": missing,
        "total": 10,
        "criteria": criteria,
        "reason": (
            "Достаточно данных"
            if ready
            else "Недостаточно данных для оценки"
        )
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_data = {
        "home_stats": {
            "avg_total": 2.8,
            "avg_xg": 1.7,
            "avg_scored_home": 1.8,
            "avg_missed_home": 1.1
        },
        "away_stats": {
            "avg_total": 2.9,
            "avg_xg": 1.4,
            "avg_scored_away": 1.3,
            "avg_missed_away": 1.2
        },
        "history": {
            "home": [],
            "away": []
        }
    }

    result = evaluate(test_data)

    print(result)
