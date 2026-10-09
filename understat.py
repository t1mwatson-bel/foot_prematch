# =====================================================================
# UNDERSTAT PARSER
# =====================================================================
import requests
import re
import json
import time
from datetime import datetime

UNDERSTAT_LEAGUES = {
    "АПЛ": "https://understat.com/league/EPL",
    "Бундеслига": "https://understat.com/league/Bundesliga",
    "Ла Лига": "https://understat.com/league/La_liga",
    "Серия А": "https://understat.com/league/Serie_A",
    "Лига 1": "https://understat.com/league/Ligue_1",
    "РПЛ": "https://understat.com/league/Russian_Premier_League",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

# Кэш: {league: {"data": {...}, "ts": timestamp}}
_CACHE = {}
CACHE_TTL = 3600  # 1 час


def fetch_understat(league_name):
    """Скачивает HTML Understat и парсит teamsData."""
    # Проверяем кэш
    if league_name in _CACHE:
        cached = _CACHE[league_name]
        if time.time() - cached["ts"] < CACHE_TTL:
            return cached["data"]

    url = UNDERSTAT_LEAGUES.get(league_name)
    if not url:
        print(f"❌ Understat '{league_name}': нет URL", flush=True)
        return None

    try:
        print(f"   🔎 Understat: GET {url}", flush=True)
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(f"   🔎 Understat {league_name}: HTTP {r.status_code} | len={len(r.text)}", flush=True)

        if r.status_code != 200:
            print(f"   ❌ Understat {league_name}: HTTP {r.status_code}", flush=True)
            return None

        html = r.text

        # Ищем все переменные с JSON.parse — узнаём новое имя
import re as _re
all_vars = _re.findall(r"var\s+(\w+)\s*=\s*JSON\.parse", html)
print(f"   🔎 Найдены переменные: {all_vars}", flush=True)

# Показываем, какие ключевые слова есть в HTML
for kw in ["teamsData", "teamsStats", "datesData", "playersData", "leagueData"]:
    if kw in html:
        print(f"   💡 Найдено: {kw}", flush=True)

return None  # пока не парсим

        # Ищем переменную teamsData
        match = re.search(r"var teamsData\s*=\s*JSON\.parse\('(.+?)'\)", html)
        if not match:
            print(f"   ❌ Understat {league_name}: regex не сработал (структура изменилась)", flush=True)
            return None

        # Раскодируем escape-последовательности (\x7B → {)
        data_str = match.group(1).encode().decode('unicode_escape')
        data = json.loads(data_str)

        # Сохраняем в кэш
        _CACHE[league_name] = {"data": data, "ts": time.time()}

        print(f"   ✅ Understat {league_name}: {len(data)} команд", flush=True)
        return data

    except Exception as e:
        print(f"   ❌ Understat {league_name}: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None


def get_team_stats(team_name, league_name, data=None):
    """
    Возвращает средние показатели команды за последние 10 матчей.
    team_name — название из 1xlite (русское)
    league_name — название лиги
    """
    if data is None:
        data = fetch_understat(league_name)
    if not data:
        return None

    # Ищем команду по названию (частичное совпадение)
    team = None
    team_lower = team_name.lower()
    for tid, t in data.items():
        title = t.get("title", "").lower()
        if team_lower in title or title in team_lower:
            team = t
            break

    if not team:
        return None

    history = team.get("history", [])
    if not history:
        return None

    # Последние 10 матчей
    last_10 = history[-10:]
    n = len(last_10)

    # Считаем средние
    avg_xg = sum(float(m.get("xG", 0)) for m in last_10) / n
    avg_xga = sum(float(m.get("xGA", 0)) for m in last_10) / n
    avg_scored = sum(float(m.get("scored", 0)) for m in last_10) / n
    avg_missed = sum(float(m.get("missed", 0)) for m in last_10) / n
    avg_total = avg_scored + avg_missed

    # BTTS (% матчей, где обе забили)
    btts_count = sum(1 for m in last_10
                     if float(m.get("scored", 0)) > 0 and float(m.get("missed", 0)) > 0)
    btts_pct = btts_count / n

    # Частота верховых (ТБ 2.5) — % матчей, где тотал > 2.5
    over_count = sum(1 for m in last_10
                     if (float(m.get("scored", 0)) + float(m.get("missed", 0))) > 2.5)
    over_pct = over_count / n

    # Раздельные показатели (дома/выезд)
    home_matches = [m for m in last_10 if m.get("h_a") == "h"]
    away_matches = [m for m in last_10 if m.get("h_a") == "a"]

    avg_scored_home = (sum(float(m.get("scored", 0)) for m in home_matches) / len(home_matches)
                       if home_matches else avg_scored)
    avg_scored_away = (sum(float(m.get("scored", 0)) for m in away_matches) / len(away_matches)
                       if away_matches else avg_scored)
    avg_missed_home = (sum(float(m.get("missed", 0)) for m in home_matches) / len(home_matches)
                       if home_matches else avg_missed)
    avg_missed_away = (sum(float(m.get("missed", 0)) for m in away_matches) / len(away_matches)
                       if away_matches else avg_missed)

    return {
        "team": team.get("title"),
        "matches": n,
        "avg_xg": round(avg_xg, 2),
        "avg_xga": round(avg_xga, 2),
        "avg_scored": round(avg_scored, 2),
        "avg_missed": round(avg_missed, 2),
        "avg_total": round(avg_total, 2),
        "btts_pct": round(btts_pct, 2),
        "over_pct": round(over_pct, 2),
        "avg_scored_home": round(avg_scored_home, 2),
        "avg_scored_away": round(avg_scored_away, 2),
        "avg_missed_home": round(avg_missed_home, 2),
        "avg_missed_away": round(avg_missed_away, 2),
    }