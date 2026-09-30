# =====================================================================
# 1XLITE PREMATCH FEED
# =====================================================================
import requests
from config import BASE_URL, HEADERS, LEAGUES


def get_prematch_games():
    url = f"{BASE_URL}/service-api/main-line-feed/v3/games1x2"
    params = {
        "cfView": 3,
        "count": 40,           # ← как в твоём URL
        "fcountry": 1,
        "gr": 2336,
        "grMode": 4,
        "lng": "ru",
        "ref": 1,
        "selectedMs": "1.1,2.1,10.1",  # ← добавили
    }
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        if r.status_code != 200:
            print(f"❌ 1xlite: HTTP {r.status_code}", flush=True)
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        return [g for g in data if isinstance(g, dict)]
    except Exception as e:
        print(f"❌ 1xlite: {e}", flush=True)
        return []


def parse_prematch_game(game):
    """Парсит матч из прематч-линии."""
    if not isinstance(game, dict):
        return None

    # Только футбол
    if (game.get("sport") or {}).get("id") != 1:
        return None

    # Только наши лиги
    liga_id = (game.get("liga") or {}).get("id")
    league_name = None
    for name, info in LEAGUES.items():
        if info["1xlite_id"] == liga_id:
            league_name = name
            break
    if not league_name:
        return None

    # Команды
    team1 = (game.get("opponent1") or {}).get("fullName", "?")
    team2 = (game.get("opponent2") or {}).get("fullName", "?")

    # Время старта
    start_ts = game.get("startTs", 0)

    # Кэф ТБ 2.5
    odd_tb25 = get_odd_tb25(game)

    return {
        "game_id": str(game.get("id")),
        "liga_id": liga_id,
        "league": league_name,
        "team1": team1,
        "team2": team2,
        "match": f"{team1} — {team2}",
        "start_ts": start_ts,
        "odd_tb25": odd_tb25,
    }


def get_odd_tb25(game):
    """Вытаскивает кэф на ТБ 2.5."""
    for grp in (game.get("centralBlockEventGroups") or []):
        if grp.get("groupId") != 17:
            continue
        events = grp.get("events") or []
        if len(events) < 1:
            continue
        tb_list = events[0] if isinstance(events[0], list) else []
        for item in tb_list:
            if (isinstance(item, dict)
                    and item.get("parameter") == 2.5
                    and item.get("type") == 9):
                return item.get("cf")
    return None