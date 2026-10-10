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

# =====================================================================
# МАППИНГ РУССКИХ НАЗВАНИЙ → ЛАТИНСКИХ (как в nb-bet)
# =====================================================================
TEAM_ALIASES = {
    # Германия
    "боруссия": "borussia",
    "боруссия дортмунд": "borussia-dortmund",
    "боруссия м": "borussia-monchengladbach",
    "бавария": "bayern",
    "байер": "bayer",
    "байер леверкузен": "bayer-leverkusen",
    "вердер": "werder",
    "вольфсбург": "wolfsburg",
    "гамбург": "hamburg",
    "хоффенхайм": "hoffenheim",
    "штутгарт": "stuttgart",
    "фрайбург": "freiburg",
    "унион берлин": "union-berlin",
    "унион": "union",
    "майнц": "mainz",
    "майнц 05": "mainz",
    "аугсбург": "augsburg",
    "падерборн": "paderborn",
    "эльверсберг": "elversberg",
    "айнтрахт": "eintracht",
    "айнтрахт франкфурт": "eintracht-frankfurt",
    "рб лейпциг": "rb-leipzig",
    "лейпциг": "leipzig",
    "хольштайн": "holstein",
    "кайзерслаутерн": "kaiserslautern",
    "хайденхайм": "heidenheim",

    # Англия
    "манчестер юнайтед": "manchester-united",
    "манчестер сити": "manchester-city",
    "ливерпуль": "liverpool",
    "арсенал": "arsenal",
    "челси": "chelsea",
    "тоттенхэм": "tottenham",
    "ньюкасл": "newcastle",
    "вестам": "west-ham",
    "вестам юнайтед": "west-ham",
    "эвертон": "everton",
    "астон вилла": "aston-villa",
    "брайтон": "brighton",
    "кристал пэлас": "crystal-palace",
    "фулхэм": "fulham",
    "волверхэмптон": "wolves",
    "лестер": "leicester",
    "саутгемптон": "southampton",
    "ипсвич": "ipswich",
    "ипсвич таун": "ipswich",
    "ноттингем форест": "nottingham-forest",
    "борнмут": "bournemouth",
    "брентфорд": "brentford",

    # Испания
    "реал мадрид": "real-madrid",
    "барселона": "barcelona",
    "атлетико": "atletico",
    "атлетико мадрид": "atletico-madrid",
    "севилья": "sevilla",
    "бетис": "betis",
    "вильярреал": "villarreal",
    "реал сосьедад": "real-sociedad",
    "атлетик": "athletic",
    "атлетик бильбао": "athletic-bilbao",
    "валенсия": "valencia",
    "жирона": "girona",
    "сельта": "celta",
    "райо": "rayo",
    "райо вальекано": "rayo-vallecano",
    "осасуна": "osasuna",
    "мальорка": "mallorca",
    "лас пальмас": "las-palmas",
    "алавес": "alaves",
    "эспаньол": "espanol",
    "малага": "malaga",
    "леганес": "leganes",
    "реал вальядолид": "real-valladolid",

    # Италия
    "ювентус": "juventus",
    "интер": "inter",
    "милан": "milan",
    "наполи": "napoli",
    "рома": "roma",
    "лацио": "lazio",
    "аталанта": "atalanta",
    "фиорентина": "fiorentina",
    "болонья": "bologna",
    "торино": "torino",
    "дженоа": "genoa",
    "кальяри": "cagliari",
    "удина": "udinese",
    "верона": "verona",
    "эмполи": "empoli",
    "лечче": "lecce",
    "парма": "parma",
    "комо": "como",
    "венеция": "venezia",
    "монца": "monza",

    # Франция
    "псж": "psg",
    "пари сен-жермен": "psg",
    "марсель": "marseille",
    "лион": "lyon",
    "ланс": "lens",
    "лилль": "lille",
    "монако": "monaco",
    "ренн": "rennes",
    "николь": "nice",
    "ник": "nice",
    "страсбур": "strasbourg",
    "нант": "nantes",
    "тулуза": "toulouse",
    "рейн": "reims",
    "г авр": "le-havre",
    "гавр": "le-havre",
    "сен-этьен": "saint-etienne",
    "анже": "angers",
    "оксер": "auxerre",
    "брест": "brest",
    "монпелье": "montpellier",

    # Россия
    "зенит": "zenit",
    "спартак": "spartak",
    "цска": "cska",
    "динамо": "dinamo",
    "локомотив": "lokomotiv",
    "краснодар": "krasnodar",
    "ростов": "rostov",
    "рубин": "rubin",
    "крылья советов": "krylya-sovetov",
    "ахмат": "akhmat",
    "пари нн": "paris-nn",
    "факел": "fakel",
    "балтика": "baltika",
    "акрон": "akron",
    "оренбург": "orenburg",
    "дим": "dynamo-makhachkala",
    "динамо махачкала": "dynamo-makhachkala",
    "химки": "khimki",
}


# =====================================================================
# ВСПОМОГАТЕЛЬНЫЕ
# =====================================================================
_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    ' ': '-', '-': '-',
}


def translit(text):
    """Рус → лат. 'Ланс' → 'lans'."""
    result = []
    for ch in text.lower():
        result.append(_TRANSLIT.get(ch, ch))
    return ''.join(result).strip('-')


def clean_team_name(name):
    """Убирает лишнее из названия команды."""
    if not name:
        return ""
    name = re.sub(r'\s*\(.*?\)\s*', '', name)
    name = re.sub(r'\s+\d+$', '', name)
    return name.strip()


def is_placeholder(name):
    """Проверяет, является ли название плейсхолдером."""
    if not name:
        return True
    n = name.lower()
    return "хозяева" in n or "гости" in n or n.strip() in ["", "?", "tbd"]


def get_team_query(name):
    """Возвращает поисковый запрос для команды."""
    name_clean = clean_team_name(name)
    name_lower = name_clean.lower()

    if name_lower in TEAM_ALIASES:
        return TEAM_ALIASES[name_lower]

    first_word = name_lower.split()[0] if name_lower.split() else name_lower
    if first_word in TEAM_ALIASES:
        return TEAM_ALIASES[first_word]

    return translit(first_word)


def get_build_id():
    global _BUILD_ID
    if _BUILD_ID:
        return _BUILD_ID
    try:
        r = requests.get(f"{NB_BASE}/ru/", headers=NB_HEADERS, timeout=15)
        match = re.search(r'"buildId":"([^"]+)"', r.text)
        if match:
            _BUILD_ID = match.group(1)
    except Exception as e:
        print(f"⚠️ get_build_id: {e}", flush=True)
    return _BUILD_ID


# =====================================================================
# ПОИСК МАТЧА (СТРОГИЙ)
# =====================================================================
def find_match_slug(team1, team2):
    """
    Ищет slug матча в nb-bet по названиям команд.
    Строгий поиск: обе команды должны совпасть.
    Возвращает slug или None.
    """
    if is_placeholder(team1) or is_placeholder(team2):
        return None

    query1 = get_team_query(team1)
    query2 = get_team_query(team2)

    # Ищем по первой команде
    slug = _search_by_query(query1, query2)
    if slug:
        return slug

    # Fallback: ищем по второй команде
    slug = _search_by_query(query2, query1)
    if slug:
        return slug

    return None


def _search_by_query(query, other_query):
    """Ищет по query, проверяя other_query в результатах."""
    url = f"{NB_API}/v1/soccer/search/"
    params = {"query": query}

    try:
        r = requests.get(url, headers=API_HEADERS, params=params, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception as e:
        print(f"⚠️ Search {query}: {e}", flush=True)
        return None

    results = data.get("data", [])
    if not results:
        return None

    q1 = query.lower()
    q2 = other_query.lower()

    # 🔥 СТРОГИЙ ПОИСК: обе команды должны совпасть
    for item in results:
        # type: 6 = матч, 5 = команда (пропускаем)
        if item.get("type") != 6:
            continue

        title = item.get("title", [])
        if len(title) < 2:
            continue

        n1 = title[0].lower()
        n2 = title[1].lower()

        # Проверяем совпадение по первым 3 символам
        match1 = q1[:3] in n1 or n1[:3] in q1
        match2 = q2[:3] in n2 or n2[:3] in q2

        if match1 and match2:
            return item.get("link")

    # Не нашли пару — возвращаем None
    return None


# =====================================================================
# ПОЛУЧЕНИЕ ДАННЫХ
# =====================================================================
def fetch_match_base(match_slug):
    """Базовые данные (кэфы, мотивация, травмы, H2H). Не критично."""
    build_id = get_build_id()
    if not build_id:
        return None
    url = f"{NB_BASE}/_next/data/{build_id}/ru/Events/{match_slug}.json"
    params = {"matchUrl": match_slug}
    try:
        r = requests.get(url, headers=NB_HEADERS, params=params, timeout=20)
        if r.status_code != 200:
            return None
        ct = r.headers.get("content-type", "")
        if "json" not in ct.lower() and not r.text.strip().startswith("{"):
            return None
        return r.json()
    except Exception:
        return None


def fetch_match_summary(match_slug, retries=3):
    """Расширенная статистика (xG, xGOT, xA). Критично."""
    url = (
        f"{NB_API}/v1/soccer/events/summary/{match_slug}/"
        f"50/12/true/false/true/false/true"
    )
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=API_HEADERS, timeout=20)
            if r.status_code != 200:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return None
            ct = r.headers.get("content-type", "")
            if "json" not in ct.lower() and not r.text.strip().startswith("{"):
                return None
            return r.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            print(f"❌ Summary {match_slug}: {e}", flush=True)
            return None
    return None


def fetch_match_result(match_slug):
    """
    Получает результат завершённого матча.
    Возвращает dict {home, away, total, status} или None.
    """
    url = f"{NB_API}/v1/soccer/events/{match_slug}"
    try:
        r = requests.get(url, headers=API_HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()

        # Структура ответа может отличаться — ищем счёт в разных местах
        # Вариант 1: data.match.score
        match = data.get("match") or data.get("data", {})

        # Пробуем разные ключи
        home_score = (
            match.get("score_home")
            or match.get("home_score")
            or match.get("scoreHome")
            or (match.get("score") or {}).get("home")
        )
        away_score = (
            match.get("score_away")
            or match.get("away_score")
            or match.get("scoreAway")
            or (match.get("score") or {}).get("away")
        )
        status = match.get("status") or match.get("matchStatus") or ""

        if home_score is None or away_score is None:
            return None

        return {
            "home": int(home_score),
            "away": int(away_score),
            "total": int(home_score) + int(away_score),
            "status": status,
        }
    except Exception as e:
        print(f"⚠️ Result {match_slug}: {e}", flush=True)
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
        if not t:
            return {}
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
            "avg_xg": t.get("75"),
            "avg_xga": t.get("76"),
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


def calc_over_pct(avg_total):
    """Грубая оценка % верховых на основе среднего тотала."""
    if not avg_total:
        return 0.5
    if avg_total >= 3.5:
        return 0.8
    if avg_total >= 2.5:
        return 0.65
    if avg_total >= 2.0:
        return 0.5
    return 0.35


def calc_btts_pct(avg_scored, avg_conceded):
    """Грубая оценка % BTTS."""
    if not avg_scored or not avg_conceded:
        return 0.5
    if avg_scored > 1.5 and avg_conceded > 1.0:
        return 0.7
    if avg_scored > 1.0 and avg_conceded > 0.8:
        return 0.55
    return 0.4


def parse_base_for_checklist(base_data, summary_data):
    """Объединяет базовые данные и summary в формат для checklist."""
    if not summary_data:
        return None

    parsed = parse_summary(summary_data)
    if not parsed:
        return None

    h = parsed["home"]
    a = parsed["away"]

    home_stats = {
        "over_pct": calc_over_pct(h.get("avg_total")),
        "avg_total": h.get("avg_total") or 0,
        "avg_xg": h.get("avg_xg") or 0,
        "avg_scored_home": h.get("avg_scored") or 0,
        "avg_missed_home": h.get("avg_conceded") or 0,
        "btts_pct": calc_btts_pct(h.get("avg_scored"), h.get("avg_conceded")),
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
      get_match_data(team1="Ланс", team2="Лион")
      get_match_data(match_slug="1601494-lans-lion-prognoz-na-match")

    Возвращает None, если xG = 0 (нет данных) — чтобы не отправлять сигнал.
    """
    if not match_slug:
        if not team1 or not team2:
            return None
        match_slug = find_match_slug(team1, team2)
        if not match_slug:
            return None

    # Базовые данные (не критично)
    base = fetch_match_base(match_slug)

    # Summary (критично)
    summary = fetch_match_summary(match_slug)

    if not summary:
        return None

    result = parse_base_for_checklist(base, summary)
    if not result:
        return None

    result["match_slug"] = match_slug

    # 🔥 Проверка: если xG = 0 для обеих команд — не отправляем
    home_xg = result["home_stats"].get("avg_xg") or 0
    away_xg = result["away_stats"].get("avg_xg") or 0
    if home_xg == 0 and away_xg == 0:
        print(f"      ⏭ xG = 0, пропуск {match_slug}", flush=True)
        return None

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
    print("=== Тест: Ипсвич — Фулхэм ===")
    data = get_match_data(team1="Ипсвич Таун", team2="Фулхэм")
    if data:
        print(json.dumps(data["home_stats"], ensure_ascii=False, indent=2))
        print(json.dumps(data["away_stats"], ensure_ascii=False, indent=2))
    else:
        print("❌ Не удалось получить данные")