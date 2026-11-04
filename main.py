import time
import threading
import traceback
from datetime import datetime
import requests
import web
import database as db
from config import *
from telegram_bot import send_telegram

# ==== API линии 1xBet ====
LINE_URL = f"{BASE_URL}/service-api/main-line-feed/v3/games1x2"

def get_prematch_games():
    params = {
        "cfView": 3,
        "count": 40,
        "fcountry": 1,
        "gr": 2336,
        "grMode": 4,
        "lng": "ru",
        "ref": 1
    }
    try:
        r = requests.get(LINE_URL, headers=HEADERS, params=params, timeout=15)
        print(f"🔎 LINE HTTP: {r.status_code}", flush=True)
        if r.status_code != 200:
            print(f"❌ Ошибка: {r.text[:300]}", flush=True)
            return []
        data = r.json()
        if isinstance(data, list):
            print(f"📊 Получено матчей: {len(data)}", flush=True)
            return [g for g in data if isinstance(g, dict)]
        return []
    except Exception as e:
        print(f"❌ Исключение: {e}", flush=True)
        return []

def parse_prematch_game(game):
    try:
        team1 = game["opponent1"]["fullName"]
        team2 = game["opponent2"]["fullName"]
        start_ts = game["startTs"]
        game_id = game["id"]
        liga = game.get("liga", {}).get("name", "Неизвестная лига")
        sport = game.get("sport", {}).get("name", "Футбол")

        odds = {
            "1": None, "X": None, "2": None,
            "TB": {},
            "OZ_Yes": None, "OZ_No": None,
        }

        for group in game.get("eventGroups", []):
            for event_list in group.get("events", []):
                for ev in event_list:
                    ev_type = ev.get("type")
                    cf = ev.get("cf")
                    if ev_type == 1: odds["1"] = cf
                    elif ev_type == 2: odds["X"] = cf
                    elif ev_type == 3: odds["2"] = cf
                    elif ev_type == 180: odds["OZ_Yes"] = cf
                    elif ev_type == 181: odds["OZ_No"] = cf

        for group in game.get("centralBlockEventGroups", []):
            if group.get("groupId") != 17:
                continue
            for event_list in group.get("events", []):
                for ev in event_list:
                    ev_type = ev.get("type")
                    cf = ev.get("cf")
                    param = ev.get("parameter")
                    if param is None: continue
                    if ev_type == 9: odds["TB"].setdefault(param, {})["over"] = cf
                    elif ev_type == 10: odds["TB"].setdefault(param, {})["under"] = cf

        return {
            "game_id": game_id,
            "team1": team1,
            "team2": team2,
            "liga": liga,
            "sport": sport,
            "start_time": datetime.fromtimestamp(start_ts),
            "start_ts": start_ts,
            "odds": odds,
            "raw": game,
        }
    except Exception as e:
        print(f"⚠️ Ошибка парсинга: {e}", flush=True)
        return None

def run_web():
    try:
        web.app.run(host="0.0.0.0", port=3000, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"❌ Ошибка запуска сайта: {e}", flush=True)

def bot_loop():
    print("🚀 БОТ ЗАПУЩЕН (Value Betting на кэфах 1xBet)", flush=True)
    while True:
        try:
            now = datetime.now(MOSCOW_TZ)
            print(f"\n🔄 [{now:%H:%M:%S}] Загрузка линии...", flush=True)

            games = get_prematch_games()
            count_ok = 0
            count_value = 0

            for game in games:
                parsed = parse_prematch_game(game)
                if not parsed:
                    continue

                t1 = parsed["team1"].lower()
                t2 = parsed["team2"].lower()
                if ("специальное" in t1 or "специальное" in t2
                        or t1 in ("хозяева", "гости") or t2 in ("хозяева", "гости")):
                    continue

                tb_25 = parsed["odds"]["TB"].get(2.5)
                if not tb_25 or not tb_25.get("over"):
                    continue

                count_ok += 1
                coef_over = tb_25["over"]
                p_book = 1 / coef_over

                if coef_over < 1.50:
                    p_model = p_book + 0.03
                elif coef_over > 2.50:
                    p_model = p_book - 0.03
                else:
                    p_model = p_book + 0.01

                edge = p_model - p_book

                print(
                    f"\n⚽ {parsed['team1']} — {parsed['team2']}"
                    f"\n   Лига: {parsed['liga']}"
                    f"\n   Начало: {parsed['start_time']:%d.%m %H:%M}"
                    f"\n   Кэф ТБ 2.5: {coef_over}"
                    f"\n   Модель: {p_model:.1%} | Букмекер: {p_book:.1%} | Edge: {edge:+.1%}",
                    flush=True
                )

                if edge > 0.05:
                    count_value += 1
                    print(f"   🔥 ВАЛУЙ", flush=True)

                    msg = (
                        f"🔥 <b>ВАЛУЙ: ТБ 2.5</b>\n\n"
                        f"⚽ <b>{parsed['team1']} — {parsed['team2']}</b>\n"
                        f"🏆 {parsed['liga']}\n"
                        f"🕒 {parsed['start_time']:%d.%m %H:%M}\n\n"
                        f"💰 Кэф: <b>{coef_over}</b>\n"
                        f"📊 Модель: {p_model:.1%} | Букмекер: {p_book:.1%}\n"
                        f"✅ Edge: +{edge:.1%}\n"
                    )
                    send_telegram(msg)

            print(f"\n✅ Матчей с ТБ 2.5: {count_ok} | валуев: {count_value}", flush=True)
            print("💤 Спим 5 минут...", flush=True)
            time.sleep(300)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Ошибка цикла: {e}", flush=True)
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot_loop()
