import time
import threading
import traceback
from datetime import datetime
import requests
import web
import database as db
import json
import gzip
from config import *
from stats_parser import parse_prematch_game
from poisson_model import prob_over
from telegram_bot import send_telegram

# ==== API линии 1xBet ====
LINE_URL = f"{BASE_URL}/service-api/main-line-feed/v3/games1x2"
NB_BET_TRENDS_URL = "https://nb-bet.com/_next/data/d2b78be8ab0400f112655049fdf444f79f406133/ru/value-trends.json"

# Заголовки, которые мы вытащили из твоего DevTools
NB_BET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 YaBrowser/26.10.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "ru,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://nb-bet.com/",
    "x-nextjs-data": "1",
    "x-middleware-prefetch": "1",
    "Cookie": ".nb-utz=Europe%2FMoscow; _ym_uid=1791564582977233122; _ym_d=1791564582; .nb-token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJndWVzdElkIjoiMEFBMDk0QjAtQkY4OC00RjdCLUFFRkYtRTlGNTRBMEYxNkU4IiwiaWF0IjoxNzkxNTY1NDI0LCJleHAiOjE4MjMxMjMwMjR9.ou2tQNRKLwVEt6ij3l-946rzCctoGHsD3lqEQDRXrmg; .nb-gid=0AA094B0-BF88-4F7B-AEFF-E9F54A0F16E8; .nb-locale=ru; _ym_isad=2; mdd=1; _ym_visorc_2384738=151255.875"
}

def get_prematch_games():
    params = {
        "cfView": 3, "count": 40, "fcountry": 1,
        "gr": 2336, "grMode": 4, "lng": "ru", "ref": 1
    }
    try:
        r = requests.get(LINE_URL, headers=HEADERS, params=params, timeout=15)
        if r.status_code != 200: return []
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Ошибка линии: {e}", flush=True)
        return []

def fetch_nb_bet_json(url):
    """Скачивает JSON с nb-bet, используя правильные заголовки"""
    try:
        r = requests.get(url, headers=NB_BET_HEADERS, timeout=15)
        print(f"🔎 NB-BET HTTP: {r.status_code}", flush=True)
        if r.status_code != 200:
            return None
        
        content = r.content
        # Пробуем распаковать gzip, если надо
        try:
            content = gzip.decompress(content)
        except Exception:
            pass
            
        return json.loads(content.decode("utf-8"))
    except Exception as e:
        print(f"⚠️ Ошибка скачивания JSON: {e}", flush=True)
        return None

def run_web():
    try:
        web.app.run(host="0.0.0.0", port=3000, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"❌ Ошибка запуска сайта: {e}", flush=True)

def bot_loop():
    print("🚀 БОТ ЗАПУЩЕН (JSON модель)", flush=True)
    while True:
        try:
            now = datetime.now(MOSCOW_TZ)
            print(f"\n🔄 [{now:%H:%M:%S}] Загрузка линии...", flush=True)

            # Скачиваем JSON с nb-bet
            print("📥 Скачиваем базу с nb-bet...", flush=True)
            nb_data = fetch_nb_bet_json(NB_BET_TRENDS_URL)
            if nb_data:
                print(f"✅ Данные с nb-bet получены! Размер: {len(str(nb_data))} символов", flush=True)
                # Для теста: выведем первые 1000 символов в консоль, чтобы понять структуру
                print(f"📄 Структура данных: {str(nb_data)[:1000]}", flush=True)
            else:
                print("❌ Не удалось получить JSON с nb-bet", flush=True)

            games = get_prematch_games()
            count_ok = 0
            count_value = 0

            for game in games:
                parsed = parse_prematch_game(game)
                if not parsed: continue

                t1 = parsed["team1"].lower()
                t2 = parsed["team2"].lower()
                if ("специальное" in t1 or "специальное" in t2
                        or t1 in ("хозяева", "гости") or t2 in ("хозяева", "гости")):
                    continue

                tb_25 = parsed["odds"]["TB"].get(2.5)
                if not tb_25 or not tb_25.get("over"): continue

                count_ok += 1
                # (Пока не знаем точную структуру JSON, чтобы искать матчи, 
                # просто пропускаем проверку на валуй. Сначала надо посмотреть, что пришло)

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
