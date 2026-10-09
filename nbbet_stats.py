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

API_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "ru",
    "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJndWVzdElkIjoiMEFBMDk0QjAtQkY4OC00RjdCLUFFRkYtRTlGNTRBMEYxNkU4IiwiaWF0IjoxNzkxNTY1NDI0LCJleHAiOjE4MjMxMjMwMjR9.ou2tQNRKLwVEt6ij3l-946rzCctoGHsD3lqEQDRXrmg",
    "origin": "https://nb-bet.com",
    "referer": "https://nb-bet.com/",
    "user-agent": NB_HEADERS["user-agent"],
}

_BUILD_ID = None

# Транслитерация рус → лат (для поиска в nb-bet)
_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    ' ': ' ', '-': '-',
}


def translit(text):
    """Рус → лат. 'Ланс' → 'lans'."""
    result = []
    for ch in text.lower():
        result.append(_TRANSLIT.get(ch, ch))
    return ''.join(result)


def get_build_id():
    global _BUILD_ID
    if _BUILD_ID:
        return _BUILD_ID
    r = requests.get(f"{NB_BASE}/ru/", headers=NB_HEADERS, timeout=15)
    match = re.search(r'"buildId":"([^"]+)"', r.text)
    if match:
        _BUILD_ID = match.group(1)
    return _BUILD_ID


# =====================================================================
# ПОИСК МАТЧА
# =====================================================================
def find_match_slug(team1, team2):
    """
    Ищет slug матча в nb-bet по названиям команд.
    team1, team2 — на русском ('Ланс', 'Лион')
    Возвращает slug или None.
    """
    # Транслитерируем первую команду для поиска
    query = translit(team1.split()[0])  # 'Ланс' → 'lans'
    
    url = f"{NB_API}/v1/soccer/search/"
    params = {"query": query}
    
    try:
        r = requests.get(url, headers=API_HEADERS, params=params, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ Поиск {query}: HTTP {r.status_code}", flush=True)
            return None
        data = r.json()
    except Exception as e:
        print(f"❌ Поиск {query}: {e}", flush=True)
        return None
    
    results = data.get("data", [])
    if not results:
        return None
    
    # Ищем матч, где обе команды совпадают
    t1 = translit(team1.split()[0]).lower()
    t2 = translit(team2.split()[0]).lower()
    
    for item in results:
        title = item.get("title", [])
        if len(title) < 2:
            continue
        n1 = title[0].lower()
        n2 = title[1].lower()
        
        # Проверяем совпадение (начало строки или вхождение)
        if (n1.startswith(t1[:4]) or t1.startswith(n1[:4])) and \
           (n2.startswith(t2[:4]) or t2.startswith(n2[:4])):
            return item.get("link")
    
    # Если точного совпадения нет — берём первый результат
    # (можно убрать, если нужна точность)
    return results[0].get("link")


# =====================================================================
# ПОЛУЧЕНИЕ ДАННЫХ
# =====================================================================
def fetch_match_base(match_slug):
    """Базовые данные (кэфы, мотивация, травмы, H2H)."""
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
        print(f"❌ Base {match_slug}: {e}", flush=True)
        return None


def fetch_match_summary(match_slug):
    """Расширенная статистика (xG, xGOT, xA)."""
    url = (
        f"{NB_API}/v1/soccer/events/summary/{match_slug}/"
        f"50/12/true/false/true/false/true"
    )
    try:
        r = requests.get(url, headers=API_HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        print(f"❌ Summary {match_slug}: {e}", flush=True)
        return None


# =====================================================================
# ПАРСИНГ
# =====================================================================
def parse_summary(summary_data):
    """Парсит xG, xGOT, xA из API."""
    data = summary_data.get("data", [])
    if not data or len(data) < 1:
        return None
    
    all_matches = data[0]
    if len(all_matches) < 2:
        return None
    
    home = all_matches[0]
    away = all_matches[1]
    
    def team_dict(t):
        matches = t.get("1") or 1
        return {
            "matches": t.get("1"),
            "wins": t.get("2"),
            "draws": t.get("3"),
            "losses": t.get("4"),
            "goals_scored": t.get("5"),
            "goals_conceded": t.get("6"),
            "avg_total": t.get("7"),
            "avg_scored": t.get("8"),
            "avg_conceded": t.get("9"),
            # xG (ключи 74-76)
            "avg_xg": t.get("75"),              # ← xG команды
            "avg_xga": t.get("76"),             # ← xG соперников
            "xg_total": t.get("74"),
            # xGOT (82-83)
            "avg_xgot": t.get("82"),
            "avg_xgot_against": t.get("83"),
            # xA (86-87)
            "avg_xa": t.get("86"),
            "avg_xa_against": t.get("87"),
            # Голевые моменты (80)
            "goal_opportunities": t.get("80"),
            # Углы (90-92)
            "corners": t.get("91"),
            "corners_against": t.get("92"),
            "corners_total": t.get("90"),
            # Карточки (94-96)
            "yellow_cards": t.get("95"),
            "yellow_against": t.get("96"),
            # Владение (71)
            "possession": t.get("71"),
            # Удары в створ (27-29)
            "shots_on_target": t.get("28"),
            "shots_on_target_against": t.get("29"),
            # Атаки (98-100)
            "attacks": t.get("99"),
            # Опасные атаки (102-104)
            "dangerous_attacks": t.get("103"),
        }
    
    return {
        "home": team_dict(home),
        "away": team_dict(away),
    }


def parse_base_for_checklist(base_data, summary_data):
    """
    Объединяет базовые данные и summary в формат для checklist.
    Возвращает home_stats / away_stats.
    """
    if not summary_data:
        return None
    
    parsed = parse_summary(summary_data)
    if not parsed:
        return None
    
    h = parsed["home"]
    a = parsed["away"]
    
    # over_pct — грубая оценка: если avg_total > 2.5, то 0.7, иначе 0.4
    # (нет точного % верховых в API)
    def calc_over_pct(avg_total):
        if not avg_total:
            return 0.5
        if avg_total >= 3.5:
            return 0.8
        if avg_total >= 2.5:
            return 0.65
        if avg_total >= 2.0:
            return 0.5
        return 0.35
    
    # btts_pct — тоже оценка
    def calc_btts_pct(avg_scored, avg_conceded):
        if not avg_scored or not avg_conceded:
            return 0.5
        # Если обе > 1.0 — вероятно BTTS часто
        if avg_scored > 1.5 and avg_conceded > 1.0:
            return 0.7
        if avg_scored > 1.0 and avg_conceded > 0.8:
            return 0.55
        return 0.4
    
    home_stats = {
        "over_pct": calc_over_pct(h.get("avg_total")),
        "avg_total": h.get("avg_total") or 0,
        "avg_xg": h.get("avg_xg") or 0,
        "avg_scored_home": h.get("avg_scored") or 0,
        "avg_missed_home": h.get("avg_conceded") or 0,
        "btts_pct": calc_btts_pct(h.get("avg_scored"), h.get("avg_conceded")),
        # Доп. поля для сигнала
        "avg_xgot": h.get("avg_xgot"),
        "corners": h.get("corners"),
        "yellow_cards": h.get("yellow_cards"),
        "possession": h.get("possession"),
    }
    
    away_stats = {
        "over_pct": calc_over_pct(a.get("avg_total")),
        "avg_total": a.get("avg_total") or 0,
        "avg_xg": a.get("avg_xg") or 0,
        "avg_scored_away": a.get("avg_scored") or 0,
        "avg_missed_away": a.get("avg_conceded") or 0,
        "btts_pct": calc_btts_pct(a.get("avg_scored"), a.get("avg_conceded")),
        "avg_xgot": a.get("avg_xgot"),
        "corners": a.get("corners"),
        "yellow_cards": a.get("yellow_cards"),
        "possession": a.get("possession"),
    }
    
    return {
        "home_stats": home_stats,
        "away_stats": away_stats,
        "raw": parsed,
    }


# =====================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =====================================================================
def get_match_data(team1=None, team2=None, match_slug=None):
    """
    Главная функция.
    Можно вызывать двумя способами:
      get_match_data(team1="Ланс", team2="Лион")
      get_match_data(match_slug="1601494-lans-lion-prognoz-na-match")
    """
    if not match_slug:
        if not team1 or not team2:
            return None
        match_slug = find_match_slug(team1, team2)
        if not match_slug:
            print(f"❌ Не найден slug для {team1} — {team2}", flush=True)
            return None
    
    # Базовые данные
    base = fetch_match_base(match_slug)
    
    # Summary (xG)
    summary = fetch_match_summary(match_slug)
    
    if not summary:
        return None
    
    result = parse_base_for_checklist(base, summary)
    if result:
        result["match_slug"] = match_slug
        if base:
            match = base.get("props", {}).get("initialState", {}).get("pageSoccerEvent", {}).get("match", {})
            block27 = match.get("27", {})
            block18 = match.get("18", {})
            
            result["motivation_home"] = block27.get("4", [{}])[0].get("motivation_value") if block27.get("4") else None
            result["motivation_away"] = block27.get("4", [{}, {}])[1].get("motivation_value") if len(block27.get("4", [])) > 1 else None
            result["injuries_text"] = block27.get("5")
            result["referee"] = block18.get("1", {}).get("8")
            result["stadium"] = block18.get("2")
            result["weather"] = f"{block18.get('4')}, {block18.get('3')}"
    
    return result


if __name__ == "__main__":
    # Тест
    data = get_match_data(team1="Ланс", team2="Лион")
    if data:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("❌ Не удалось получить данные")
