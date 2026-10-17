# nbbet_stats.py
import requests
import re
import json
import time

NB_BASE = "https://nb-bet.com"
NB_API = "https://app.nb-bet.com"

NB_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
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

TEAM_ALIASES = {
    "боруссия": "borussia", "боруссия дортмунд": "borussia-dortmund", "боруссия м": "borussia-monchengladbach",
    "бавария": "bayern", "байер": "bayer", "байер леверкузен": "bayer-leverkusen", "вердер": "werder",
    "вольфсбург": "wolfsburg", "гамбург": "hamburg", "хоффенхайм": "hoffenheim", "штутгарт": "stuttgart",
    "фрайбург": "freiburg", "унион берлин": "union-berlin", "унион": "union", "майнц": "mainz", "майнц 05": "mainz",
    "аугсбург": "augsburg", "падерборн": "paderborn", "эльверсберг": "elversberg", "айнтрахт": "eintracht",
    "айнтрахт франкфурт": "eintracht-frankfurt", "рб лейпциг": "rb-leipzig", "лейпциг": "leipzig",
    "хольштайн": "holstein", "кайзерслаутерн": "kaiserslautern", "хайденхайм": "heidenheim", "шальке 04": "schalke",
    "манчестер юнайтед": "manchester-united", "манчестер сити": "manchester-city", "ливерпуль": "liverpool",
    "арсенал": "arsenal", "челси": "chelsea", "тоттенхэм": "tottenham", "ньюкасл": "newcastle", "вестам": "west-ham",
    "вестам юнайтед": "west-ham", "эвертон": "everton", "астон вилла": "aston-villa", "брайтон": "brighton",
    "кристал пэлас": "crystal-palace", "фулхэм": "fulham", "волверхэмптон": "wolves", "лестер": "leicester",
    "саутгемптон": "southampton", "ипсвич": "ipswich", "ипсвич таун": "ipswich", "ноттингем форест": "nottingham-forest",
    "борнмут": "bournemouth", "брентфорд": "brentford", "реал мадрид": "real-madrid", "барселона": "barcelona",
    "атлетико": "atletico", "атлетико мадрид": "atletico-madrid", "севилья": "sevilla", "бетис": "betis",
    "реал бетис": "real-betis", "вильярреал": "villarreal", "реал сосьедад": "real-sociedad", "атлетик": "athletic",
    "атлетик бильбао": "athletic-bilbao", "валенсия": "valencia", "жирона": "girona", "сельта": "celta",
    "райо": "rayo", "райо вальекано": "rayo-vallecano", "осасуна": "osasuna", "мальорка": "mallorca",
    "лас пальмас": "las-palmas", "алавес": "alaves", "эспаньол": "espanol", "малага": "malaga", "леганес": "leganes",
    "реал вальядолид": "real-valladolid", "эльче": "elche", "ювентус": "juventus", "интер": "inter", "милан": "milan",
    "наполи": "napoli", "рома": "roma", "лацио": "lazio", "аталанта": "atalanta", "фиорентина": "fiorentina",
    "болонья": "bologna", "торино": "torino", "дженоа": "genoa", "кальяри": "cagliari", "удина": "udinese",
    "удинезе": "udinese", "верона": "verona", "эмполи": "empoli", "лечче": "lecce", "парма": "parma",
    "комо": "como", "венеция": "venezia", "монца": "monza", "псж": "psg", "пари сен-жермен": "psg",
    "марсель": "marseille", "лион": "lyon", "ланс": "lens", "лилль": "lille", "монако": "monaco", "ренн": "rennes",
    "николь": "nice", "ник": "nice", "страсбур": "strasbourg", "нант": "nantes", "тулуза": "toulouse", "рейн": "reims",
    "г авр": "le-havre", "гавр": "le-havre", "сен-этьен": "saint-etienne", "анже": "angers", "оксер": "auxerre",
    "брест": "brest", "стад брестуа 29": "brest", "монпелье": "montpellier", "труа": "troyes", "зенит": "zenit",
    "спартак": "spartak", "цска": "cska", "динамо": "dinamo", "локомотив": "lokomotiv", "краснодар": "krasnodar",
    "ростов": "rostov", "рубин": "rubin", "крылья советов": "krylya-sovetov", "ахмат": "akhmat", "пари нн": "paris-nn",
    "факел": "fakel", "балтика": "baltika", "акрон": "akron", "оренбург": "orenburg", "дим": "dynamo-makhachkala",
    "динамо махачкала": "dynamo-makhachkala", "химки": "khimki",
}

_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    ' ': '-', '-': '-',
}


def translit(text):
    result = []
    for ch in text.lower():
        result.append(_TRANSLIT.get(ch, ch))
    return ''.join(result).strip('-')


def clean_team_name(name):
    if not name:
        return ""
    name = re.sub(r'\s*\(.*?\)\s*', '', name)
    name = re.sub(r'\s+\d+$', '', name)
    return name.strip()


def is_placeholder(name):
    if not name:
        return True
    n = name.lower()
    return "хозяева" in n or "гости" in n or n.strip() in ["", "?", "tbd"]


def get_team_query(name):
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
    except Exception:
        pass
    return _BUILD_ID


# =====================================================================
# ПОИСК МАТЧА (через HTML, чтобы обойти блокировку API)
# =====================================================================
def find_match_slug(team1, team2):
    if is_placeholder(team1) or is_placeholder(team2):
        return None

    query1 = get_team_query(team1)
    query2 = get_team_query(team2)

    slug = _search_html(query1, query2)
    if slug:
        return slug

    return _search_html(query2, query1)

def _search_html(query, other_query):
    """Ищет через HTML страницу поиска (обходит блокировку API)."""
    url = f"{NB_BASE}/Search/Matches"
    params = {"query": query}
    try:
        r = requests.get(url, headers=NB_HEADERS, params=params, timeout=15)
        if r.status_code != 200:
            return None
        
        # Ищем ссылки на матчи в HTML
        # Формат ссылки: /Events/123456-team1-team2-prognoz-na-match
        links = re.findall(r'/Events/([a-zA-Z0-9\-]+prognoz-na-match)', r.text)
        
        q2 = other_query.lower()
        for link in links:
            link_lower = link.lower()
            # Проверяем, что в ссылке есть вторая команда
            if q2[:3] in link_lower:
                return link
                
        # Если не нашли точную пару, но есть результаты, берем первый (рискованно, но лучше чем ничего)
        if links:
            return links[0]
            
    except Exception as e:
        print(f"⚠️ HTML Search {query}: {e}", flush=True)
    return None


# =====================================================================
# ПОЛУЧЕНИЕ ДАННЫХ (через HTML __NEXT_DATA__)
# =====================================================================
def fetch_match_data_html(match_slug):
    """Скачивает страницу матча и вытаскивает __NEXT_DATA__."""
    url = f"{NB_BASE}/Events/{match_slug}"
    try:
        r = requests.get(url, headers=NB_HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        
        # Ищем JSON внутри <script id="__NEXT_DATA__">
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.DOTALL)
        if not match:
            return None
            
        data = json.loads(match.group(1))
        return data
    except Exception as e:
        print(f"❌ HTML Data {match_slug}: {e}", flush=True)
        return None


# =====================================================================
# ПАРСИНГ ДАННЫХ ИЗ __NEXT_DATA__
# =====================================================================
def parse_html_data(data):
    """Вытаскивает статистику (включая xG) из __NEXT_DATA__."""
    try:
        initial = data.get("props", {}).get("initialState", {})
        
        # В HTML-версии блок summary лежит в soccerEventsSummary
        summary_block = initial.get("soccerEventsSummary", {}).get("summary", [])
        
        if not summary_block or len(summary_block) < 3:
            return None
            
        # summary_block[0] — все матчи (Ланс, Лион и т.д.)
        all_matches = summary_block[0]
        if len(all_matches) < 2:
            return None
            
        home = all_matches[0]
        away = all_matches[1]

        def team_dict(t):
            if not t: return {}
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
                "avg_xg": t.get("75"),      # xG
                "avg_xga": t.get("76"),     # xGA
                "xg_total": t.get("74"),
                "avg_xgot": t.get("82"),
                "corners": t.get("91"),
                "yellow_cards": t.get("95"),
                "possession": t.get("71"),
            }

        return {
            "home": team_dict(home),
            "away": team_dict(away),
            "base_data": initial # Сохраняем весь блок для травм и мотивации
        }
    except Exception as e:
        print(f"⚠️ Parse Error: {e}", flush=True)
        return None


def calc_over_pct(avg_total):
    if not avg_total: return 0.5
    if avg_total >= 3.5: return 0.8
    if avg_total >= 2.5: return 0.65
    if avg_total >= 2.0: return 0.5
    return 0.35

def calc_btts_pct(avg_scored, avg_conceded):
    if not avg_scored or not avg_conceded: return 0.5
    if avg_scored > 1.5 and avg_conceded > 1.0: return 0.7
    if avg_scored > 1.0 and avg_conceded > 0.8: return 0.55
    return 0.4


# =====================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =====================================================================
def get_match_data(team1=None, team2=None, match_slug=None):
    if not match_slug:
        if not team1 or not team2: return None
        match_slug = find_match_slug(team1, team2)
        if not match_slug:
            return None

    # Скачиваем HTML
    html_data = fetch_match_data_html(match_slug)
    if not html_data:
        return None

    parsed = parse_html_data(html_data)
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

    # Проверка: если xG = 0 для обеих команд — не отправляем
    if home_stats["avg_xg"] == 0 and away_stats["avg_xg"] == 0:
        print(f"      ⏭ xG = 0, пропуск {match_slug}", flush=True)
        return None

    result = {
        "match_slug": match_slug,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "raw": parsed
    }

    # Вытаскиваем мотивацию и травмы из __NEXT_DATA__
    initial = parsed.get("base_data", {})
    match_info = initial.get("pageSoccerEvent", {}).get("match", {})
    if match_info:
        block27 = match_info.get("27", {})
        block18 = match_info.get("18", {})
        
        result["motivation_home"] = block27.get("4", [{}])[0].get("motivation_value") if block27.get("4") else None
        result["motivation_away"] = block27.get("4", [{}, {}])[1].get("motivation_value") if len(block27.get("4", [])) > 1 else None
        result["injuries_text"] = block27.get("5")
        result["referee"] = block18.get("1", {}).get("8")

    return result