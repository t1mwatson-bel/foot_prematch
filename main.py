import time
import threading
import traceback
from datetime import datetime, timedelta
import requests
import web
import database as db
from config import *
from telegram_bot import send_telegram
from ruscore import fetch_ruscore_events # Импортируем Ruscore

# ==== API линии 1xBet ====
LINE_URL = f"{BASE_URL}/service-api/main-line-feed/v3/games1x2"

def get_prematch_games():
    params = {
        "cfView": 3, "count": 40, "fcountry": 1,
        "gr": 2336, "grMode": 4, "lng": "ru", "ref": 1
    }
    try:
        r = requests.get(LINE_URL, headers=HEADERS, params=params, timeout=15)
        if r.status_code != 200: return []
        data = r.json()
        return [g for g in data if isinstance(g, dict)] if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Ошибка линии: {e}", flush=True)
        return []

def parse_prematch_game(game):
    try:
        team1 = game["opponent1"]["fullName"]
        team2 = game["opponent2"]["fullName"]
        start_ts = game["startTs"]
        liga = game.get("liga", {}).get("name", "Неизвестная лига")
        
        odds = {"TB": {}}
        for group in game.get("eventGroups", []):
            for event_list in group.get("events", []):
                for ev in event_list:
                    ev_type, cf = ev.get("type"), ev.get("cf")
                    if ev_type == 1: odds["1"] = cf
                    elif ev_type == 2: odds["X"] = cf
                    elif ev_type == 3: odds["2"] = cf
                    
        for group in game.get("centralBlockEventGroups", []):
            if group.get("groupId") != 17: continue
            for event_list in group.get("events", []):
                for ev in event_list:
                    ev_type, cf, param = ev.get("type"), ev.get("cf"), ev.get("parameter")
                    if param is None: continue
                    if ev_type == 9: odds["TB"].setdefault(param, {})["over"] = cf
                    elif ev_type == 10: odds["TB"].setdefault(param, {})["under"] = cf

        return {
            "team1": team1, "team2": team2, "liga": liga,
            "start_time": datetime.fromtimestamp(start_ts),
            "odds": odds
        }
    except: return None

def save_ruscore_results():
    """Раз в день тянет вчерашние результаты из Ruscore и сохраняет в БД."""
    print("📥 Накопление истории (Ruscore)...", flush=True)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        events = fetch_ruscore_events(yesterday)
        count = 0
        for ev in events:
            home = ev.get("home", {}).get("name")
            away = ev.get("away", {}).get("name")
            score = ev.get("score", [])
            if not home or not away or not score: continue
            
            h_score, a_score = None, None
            for s in score:
                if s.get("type") == "overall":
                    h_score, a_score = s.get("home"), s.get("away")
                    break
            
            if h_score is not None and a_score is not None:
                db.save_match_result(home, away, int(h_score), int(a_score), yesterday)
                count += 1
        print(f"✅ Сохранено результатов: {count}", flush=True)
    except Exception as e:
        print(f"⚠️ Ошибка Ruscore: {e}", flush=True)

def run_web():
    try: web.app.run(host="0.0.0.0", port=3000, use_reloader=False, threaded=True)
    except Exception as e: print(f"❌ Ошибка сайта: {e}", flush=True)

def bot_loop():
    print("🚀 ГИБРИДНЫЙ БОТ ЗАПУЩЕН", flush=True)
    last_save_date = None
    
    while True:
        try:
            now = datetime.now(MOSCOW_TZ)
            print(f"\n🔄 [{now:%H:%M:%S}] Загрузка линии...", flush=True)

            # 1. Раз в день (например, в 03:00 ночи) сохраняем результаты
            if now.hour == 3 and last_save_date != now.date():
                save_ruscore_results()
                last_save_date = now.date()

            # 2. Value Betting на кэфах 1xBet
            games = get_prematch_games()
            count_value = 0

            for game in games:
                parsed = parse_prematch_game(game)
                if not parsed: continue

                t1, t2 = parsed["team1"].lower(), parsed["team2"].lower()
                if ("специальное" in t1 or "специальное" in t2
                        or t1 in ("хозяева", "гости") or t2 in ("хозяева", "гости")):
                    continue

                tb_25 = parsed["odds"]["TB"].get(2.5)
                if not tb_25 or not tb_25.get("over"): continue

                coef_over = tb_25["over"]
                p_book = 1 / coef_over

                # Простая коррекция
                if coef_over < 1.50: p_model = p_book + 0.03
                elif coef_over > 2.50: p_model = p_book - 0.03
                else: p_model = p_book + 0.01

                edge = p_model - p_book

                if edge > 0.05:
                    count_value += 1
                    msg = (
                        f"🔥 <b>ВАЛУЙ: ТБ 2.5</b>\n\n"
                        f"⚽ <b>{parsed['team1']} — {parsed['team2']}</b>\n"
                        f"🏆 {parsed['liga']}\n"
                        f"🕒 {parsed['start_time']:%d.%m %H:%M}\n"
                        f"💰 Кэф: {coef_over}\n"
                        f"📊 Edge: +{edge:.1%}"
                    )
                    send_telegram(msg)
                    print(f"🔥 ВАЛУЙ: {parsed['team1']} — {parsed['team2']}", flush=True)

            print(f"✅ Валуев найдено: {count_value}. Спим 5 минут...", flush=True)
            time.sleep(300)

        except KeyboardInterrupt: break
        except Exception as e:
            print(f"❌ Ошибка цикла: {e}", flush=True)
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    db.init_db()
    threading.Thread(target=run_web, daemon=True).start()
    bot_loop()
