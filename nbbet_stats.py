# nbbet_stats.py
import requests
import json
import urllib.parse
import re

NB_API = "https://app.nb-bet.com"
SCRAPER_API_KEY = "9248e1ae2328ca97262e3b74ca049796"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "ru,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJndWVzdElkIjoiMEFBMDk0QjAtQkY4OC00RjdCLUFFRkYtRTlGNTRBMEYxNkU4IiwiaWF0IjoxNzkxNTY1NDI0LCJleHAiOjE4MjMxMjMwMjR9.ou2tQNRKLwVEt6ij3l-946rzCctoGHsD3lqEQDRXrmg",
    "origin": "https://nb-bet.com",
    "referer": "https://nb-bet.com/",
}

# Словарь для перевода русских названий в латиницу (для поиска)
TEAM_ALIASES = {
    "вердер": "werder", "падерборн": "paderborn", "гамбург": "hamburg", "штутгарт": "stuttgart",
    "унион берлин": "union", "боруссия": "borussia", "шальке 04": "schalke", "майнц 05": "mainz",
    "эльверсберг": "elversberg", "аугсбург": "augsburg", "бавария": "bayern", "рб лейпциг": "leipzig",
    "эспаньол": "espanol", "атлетико мадрид": "atletico", "вильярреал": "villarreal", "эльче": "elche",
    "реал бетис": "betis", "барселона": "barcelona", "валенсия": "valencia", "атлетик бильбао": "athletic",
    "венеция": "venezia", "наполи": "napoli", "болонья": "bologna", "интер": "inter", "рома": "roma",
    "дженоа": "genoa", "удинезе": "udinese", "лечче": "lecce", "страсбург": "strasbourg",
    "псж": "psg", "лилль": "lille", "стад брестуа 29": "brest", "труа": "troyes", "ланс": "lens",
    "манчестер юнайтед": "manchester-united", "манчестер сити": "manchester-city", "ливерпуль": "liverpool",
    "арсенал": "arsenal", "челси": "chelsea", "тоттенхэм": "tottenham", "ньюкасл": "newcastle",
    "вестам": "west-ham", "эвертон": "everton", "астон вилла": "aston-villa", "брайтон": "brighton",
    "кристал пэлас": "crystal-palace", "фулхэм": "fulham", "волверхэмптон": "wolves", "лестер": "leicester",
    "саутгемптон": "southampton", "ипсвич таун": "ipswich", "ноттингем форест": "nottingham-forest",
    "борнмут": "bournemouth", "брентфорд": "brentford", "реал мадрид": "real-madrid",
    "севилья": "sevilla", "реал сосьедад": "real-sociedad", "жирона": "girona", "сельта": "celta",
    "райо вальекано": "rayo", "осасуна": "osasuna", "мальорка": "mallorca", "лас пальмас": "las-palmas",
    "алавес": "alaves", "малага": "malaga", "леганес": "leganes", "ювентус": "juventus",
    "милан": "milan", "лацио": "lazio", "аталанта": "atalanta", "фиорентина": "fiorentina",
    "торино": "torino", "кальяри": "cagliari", "верона": "verona", "эмполи": "empoli",
    "парма": "parma", "комо": "como", "монца": "monza", "марсель": "marseille",
    "лион": "lyon", "монако": "monaco", "ренн": "rennes", "николь": "nice", "нант": "nantes",
    "тулуза": "toulouse", "рейн": "reims", "гавр": "le-havre", "сен-этьен": "saint-etienne",
    "анже": "angers", "оксер": "auxerre", "монпелье": "montpellier", "зенит": "zenit",
    "спартак": "spartak", "цска": "cska", "динамо": "dinamo", "локомотив": "lokomotiv",
    "краснодар": "krasnodar", "ростов": "rostov", "рубин": "rubin", "крылья советов": "krylya-sovetov",
    "ахмат": "akhmat", "пари нн": "paris-nn", "факел": "fakel", "балтика": "baltika",
    "акрон": "akron", "оренбург": "orenburg", "динамо махачкала": "dynamo-makhachkala", "химки": "khimki"
}

def get_team_query(name):
    if not name: return ""
    name_clean = name.strip().lower()
    
    # Если есть в словаре, берем оттуда
    if name_clean in TEAM_ALIASES:
        return TEAM_ALIASES[name_clean]
    
    # Иначе ищем по первому слову
    first_word = name_clean.split()[0]
    if first_word in TEAM_ALIASES:
        return TEAM_ALIASES[first_word]
        
    return first_word

def is_placeholder(name):
    if not name: return True
    n = name.lower()
    return "хозяева" in n or "гости" in n or n.strip() in ["", "?", "tbd"]

def fetch_via_proxy(url):
    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={urllib.parse.quote(url)}"
    try:
        r = requests.get(proxy_url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def find_match_slug(team1, team2):
    if is_placeholder(team1) or is_placeholder(team2): 
        return None
    
    q1 = get_team_query(team1)
    q2 = get_team_query(team2)

    # Отправляем запрос в поиск nb-bet через прокси
    url = f"{NB_API}/v1/soccer/search/?query={q1}"
    data = fetch_via_proxy(url)
    
    # --- ИСПРАВЛЕННЫЙ БЛОК ---
    if data:
        with open("nbbet_debug.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("NB-Bet: ответ сохранён в nbbet_debug.json", flush=True)
    # -------------------------

    if not data: 
        return None

    results = data.get("data", [])
    for item in results:
        title = item.get("title", [])
        if len(title) < 2: 
            continue
        
        n1, n2 = title[0].lower(), title[1].lower()
        
        # Мягкий поиск совпадений (первые 3-4 буквы)
        match1 = (q1[:4] in n1 or n1[:4] in q1)
        match2 = (q2[:4] in n2 or n2[:4] in q2)
        
        if match1 and match2:
            return item.get("link")
            
    return None

def get_match_data(team1=None, team2=None):
    slug = find_match_slug(team1, team2)
    if not slug: 
        return None

    # Получаем статистику через прокси
    url = f"{NB_API}/v1/soccer/events/summary/{slug}/50/12/true/false/true/false/true"
    data = fetch_via_proxy(url)
    
    if not data: 
        return None

    summary = data.get("data", [])
    if not summary or len(summary) < 1: 
        return None

    all_matches = summary[0]
    if len(all_matches) < 2: 
        return None

    home = all_matches[0]
    away = all_matches[1]

    h_xg = home.get("75", 0)
    a_xg = away.get("75", 0)
    
    # Если нет xG, не отправляем
    if h_xg == 0 and a_xg == 0: 
        return None

    home_stats = {
        "avg_xg": h_xg or 0,
        "avg_total": home.get("7", 0),
        "avg_scored_home": home.get("8", 0),
        "avg_missed_home": home.get("9", 0),
        "over_pct": 0.65 if home.get("7", 0) > 2.5 else 0.4,
        "btts_pct": 0.6 if (home.get("8", 0) > 1 and home.get("9", 0) > 1) else 0.4,
        "corners": home.get("91"),
        "yellow_cards": home.get("95"),
        "possession": home.get("71")
    }

    away_stats = {
        "avg_xg": a_xg or 0,
        "avg_total": away.get("7", 0),
        "avg_scored_away": away.get("8", 0),
        "avg_missed_away": away.get("9", 0),
        "over_pct": 0.65 if away.get("7", 0) > 2.5 else 0.4,
        "btts_pct": 0.6 if (away.get("8", 0) > 1 and away.get("9", 0) > 1) else 0.4,
        "corners": away.get("91"),
        "yellow_cards": away.get("95"),
        "possession": away.get("71")
    }

    return {
        "match_slug": slug,
        "home_stats": home_stats,
        "away_stats": away_stats
    }
