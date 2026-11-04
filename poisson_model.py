import math

def poisson_prob(k, lam):
    """Вероятность ровно k событий при среднем lam."""
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def prob_over(total, lam):
    """
    Вероятность, что сумма голов > total.
    lam — ожидаемое количество голов (сумма двух команд).
    """
    p_under = 0
    for k in range(int(total) + 1):  # 0..total
        p_under += poisson_prob(k, lam)
    return 1 - p_under

def estimate_total_goals(liga_name):
    """
    Заглушка: средний тотал по лиге (обе команды вместе).
    Потом заменим на данные из БД (форма команд).
    """
    league_avg = {
        "Лига Чемпионов УЕФА": 2.8,
        "Чемпионат Англии. Чемпионшип": 2.5,
        "Чемпионат Бразилии. Серия A": 2.4,
        "Кубок России": 2.2,
        "Молодежная лига УЕФА": 3.2,
    }
    return league_avg.get(liga_name, 2.5)
