# nbbet_stats.py
import requests
import re
import json
import time

NB_BASE = "https://nb-bet.com"
NB_API = "https://app.nb-bet.com"

NB_HEADERS = {
    "accept": "*/*",
    "accept-language": "ru,en;q=0.9",
    "referer": "https://nb-bet.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 YaBrowser/26.8.0.0 Safari/537.36",
}

_BUILD_ID = None
_GUEST_TOKEN = None


def get_build_id():
    """Получает buildId со страницы nb-bet.com."""
    global _BUILD_ID
    if _BUILD_ID:
        return _BUILD_ID
    r = requests.get(f"{NB_BASE}/ru/", headers=NB_HEADERS, timeout=15)
    match = re.search(r'"buildId":"([^"]+)"', r.text)
    if match:
        _BUILD_ID = match.group(1)
    return _BUILD_ID


def get_guest_token():
    """
    Получает гостевой токен.
    Если у тебя есть свой токен из cookies — вставь его сюда.
    """
    global _GUEST_TOKEN
    if _GUEST_TOKEN:
        return _GUEST_TOKEN
    # Токен из твоего запроса (гостевой)
    _GUEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJndWVzdElkIjoiMEFBMDk0QjAtQkY4OC00RjdCLUFFRkYtRTlGNTRBMEYxNkU4IiwiaWF0IjoxNzkxNTY1NDI0LCJleHAiOjE4MjMxMjMwMjR9.ou2tQNRKLwVEt6ij3l-946rzCctoGHsD3lqEQDRXrmg"
    return _GUEST_TOKEN


def fetch_match_base(match_slug):
    """Базовые данные матча (кэфы, мотивация, травмы, H2H)."""
    build_id = get_build_id()
    if not build_id:
        return None
    url = f"{NB_BASE}/_next/data/{build_id}/ru/Events/{match_slug}.json"
    params = {"matchUrl": match_slug}
    try:
        r = requests.get(url, headers=NB_HEADERS, params=params, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        print(f"❌ NB-Bet base {match_slug}: {e}", flush=True)
        return None


def fetch_match_summary(match_slug, count_matches=50, count_months=12):
    """Расширенная статистика (xG, xGOT, xA, голевые моменты)."""
    token = get_guest_token()
    url = (
        f"{NB_API}/v1/soccer/events/summary/{match_slug}/"
        f"{count_matches}/{count_months}/true/false/true/false/true"
    )
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ru",
        "authorization": token,
        "origin": "https://nb-bet.com",
        "referer": "https://nb-bet.com/",
        "user-agent": NB_HEADERS["user-agent"],
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            print(f"⚠️ Summary status {r.status_code} для {match_slug}", flush=True)
            return None
        return r.json()
    except Exception as e:
        print(f"❌ NB-Bet summary {match_slug}: {e}", flush=True)
        return None


def parse_match_base(data):
    """Парсит базовые данные из _next/data JSON."""
    match = data.get("props", {}).get("initialState", {}).get("pageSoccerEvent", {}).get("match", {})
    if not match:
        return None

    block27 = match.get("27", {})
    block18 = match.get("18", {})
    odds_start = match.get("5", {})
    odds_current = match.get("6", {})

    summary = block27.get("8", [{}, {}])
    home_stats = summary[0] if len(summary) > 0 else {}
    away_stats = summary[1] if len(summary) > 1 else {}

    motivation = block27.get("4", [{}, {}])
    mot_home = motivation[0].get("motivation_value") if len(motivation) > 0 else None
    mot_away = motivation[1].get("motivation_value") if len(motivation) > 1 else None

    return {
        "home_team": match.get("7", {}).get("1"),
        "away_team": match.get("8", {}).get("1"),
        "tournament": match.get("10", {}).get("1"),
        "date": match.get("4"),

        "odds_start_home": odds_start.get("1"),
        "odds_start_draw": odds_start.get("3"),
        "odds_start_away": odds_start.get("2"),

        "odds_current_home": odds_current.get("1"),
        "odds_current_draw": odds_current.get("3"),
        "odds_current_away": odds_current.get("2"),

        "motivation_home": mot_home,
        "motivation_away": mot_away,

        "injuries_text": block27.get("5"),

        "referee": block18.get("1", {}).get("8"),
        "referee_link": block18.get("1", {}).get("9"),
        "referee_yellow_avg": block18.get("1", {}).get("2"),
        "referee_red_avg": block18.get("1", {}).get("5"),

        "stadium": block18.get("2"),
        "weather_temp": block18.get("3"),
        "weather_desc": block18.get("4"),

        "home_matches": home_stats.get("1"),
        "home_wins": home_stats.get("2"),
        "home_draws": home_stats.get("3"),
        "home_losses": home_stats.get("4"),
        "home_goals_scored": home_stats.get("5"),
        "home_goals_conceded": home_stats.get("6"),
        "home_avg_total": home_stats.get("7"),

        "away_matches": away_stats.get("1"),
        "away_wins": away_stats.get("2"),
        "away_draws": away_stats.get("3"),
        "away_losses": away_stats.get("4"),
        "away_goals_scored": away_stats.get("5"),
        "away_goals_conceded": away_stats.get("6"),
        "away_avg_total": away_stats.get("7"),

        "h2h_matches": block27.get("7", []),
        "facts": block27.get("3", []),
    }


def parse_summary(summary_data):
    """
    Парсит xG, xGOT, xA, голевые моменты из API summary.
    data[0] — все матчи
    data[1] — дома/гости
    data[2] — H2H
    """
    data = summary_data.get("data", [])
    if not data or len(data) < 1:
        return None

    all_matches = data[0]
    if len(all_matches) < 2:
        return None

    home = all_matches[0]
    away = all_matches[1]

    return {
        "home_team": {
            "matches": home.get("1"),
            "wins": home.get("2"),
            "draws": home.get("3"),
            "losses": home.get("4"),
            "goals_scored": home.get("5"),
            "goals_conceded": home.get("6"),
            "avg_total": home.get("7"),
            "avg_scored": home.get("8"),
            "avg_conceded": home.get("9"),
            # xG блок
            "xg": home.get("75"),              # 2.3 ✅
            "xga": home.get("76"),             # 1.9 ✅
            "xg_total": home.get("74"),        # 4.2
            "xgot": home.get("82"),            # 3.6
            "xgot_against": home.get("83"),    # 1.8
            "xa": home.get("86"),              # 2.6
            "xa_against": home.get("87"),      # 1.4
            "goal_opportunities": home.get("80"),  # 3.2
            # Углы
            "corners": home.get("91"),         # 10.8
            "corners_against": home.get("92"), # 7.8
            "corners_total": home.get("90"),   # 18.6
            # Карточки
            "yellow_cards": home.get("95"),    # 4
            "yellow_against": home.get("96"),  # 3.2
            "yellow_total": home.get("94"),    # 7.2
            # Владение
            "possession": home.get("71"),      # 51
        },
        "away_team": {
            "matches": away.get("1"),
            "wins": away.get("2"),
            "draws": away.get("3"),
            "losses": away.get("4"),
            "goals_scored": away.get("5"),
            "goals_conceded": away.get("6"),
            "avg_total": away.get("7"),
            "avg_scored": away.get("8"),
            "avg_conceded": away.get("9"),
            "xg": away.get("75"),              # 1.8 ✅
            "xga": away.get("76"),             # 1.2 ✅ (на скриншоте было 1.2!)
            "xg_total": away.get("74"),        # 3
            "xgot": away.get("82"),            # 2.4
            "xgot_against": away.get("83"),    # 1.6
            "xa": away.get("86"),              # 1.9
            "xa_against": away.get("87"),      # 1.3
            "goal_opportunities": away.get("80"),  # 2.4
            "corners": away.get("91"),         # 9.2
            "corners_against": away.get("92"), # 7.2
            "corners_total": away.get("90"),   # 16.4
            "yellow_cards": away.get("95"),    # 4.2
            "yellow_against": away.get("96"),  # 4
            "yellow_total": away.get("94"),    # 8.2
            "possession": away.get("71"),      # 52
        },
    }


def get_match_data(match_slug):
    """
    Главная функция: возвращает ВСЁ для чек-листа.
    """
    base = fetch_match_base(match_slug)
    if not base:
        return None

    summary = fetch_match_summary(match_slug)

    result = parse_match_base(base)
    if not result:
        return None

    if summary:
        xg_data = parse_summary(summary)
        if xg_data:
            result["home_team_stats"] = xg_data["home_team"]
            result["away_team_stats"] = xg_data["away_team"]

    # Считаем критерии чек-листа
    if "home_team_stats" in result and "away_team_stats" in result:
        h = result["home_team_stats"]
        a = result["away_team_stats"]

        # Критерий 2: средний тотал пары
        if h.get("avg_total") and a.get("avg_total"):
            result["avg_total_pair"] = (h["avg_total"] + a["avg_total"]) / 2

        # Критерий 3: xG пары
        if h.get("xg") and a.get("xg"):
            result["xg_pair_total"] = h["xg"] + a["xg"]
            result["xg_pair_avg"] = (h["xg"] + a["xg"]) / 2

        # Критерий 4: атака хозяев
        result["home_attack"] = h.get("avg_scored")

        # Критерий 5: атака гостей
        result["away_attack"] = a.get("avg_scored")

        # Критерий 6: оборона
        result["home_defense"] = h.get("avg_conceded")
        result["away_defense"] = a.get("avg_conceded")

    return result


if __name__ == "__main__":
    slug = "1601494-lans-lion-prognoz-na-match"
    data = get_match_data(slug)
    if data:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("❌ Не удалось получить данные")
