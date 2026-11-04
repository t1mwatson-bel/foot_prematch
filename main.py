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
NB_BET_RESULTS_URL = "https://nb-bet.com/_next/data/d2b78be8ab0400f112655049fdf444f79f406133/ru/Results.json"

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
        if r.status_code != 200:
            return []
        data = r.json()
        if isinstance(data, list):
            return [g for g in data if isinstance(g, dict)]
        return []
    except Exception as e:
        print(f"❌ Ошибка линии: {e}", flush=True)
        return []

def fetch_nb_bet_json(url):
    """Скачивает JSON с nb-bet, распаковывая gzip если нужно"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://nb-bet.com/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        
        content = r.content
        try:
            content = gzip.decompress(content)
        except Exception:
            pass # Если не gzip, пробуем как есть
            
        return json.loads(content.decode("utf-8"))
    except Exception as e:
        print(f"⚠️ Ошибка скачивания JSON: {e}", flush=True)
        return None

def find_match_in_results(data, team1, team2):
    """Ищет матч в JSON рекурсивно по названиям команд"""
    def normalize(s):
        return str(s).lower().replace(" ", "").replace("-", "")
    
    n1 = normalize(team1)
    n2 = normalize(team2)
    
    def search(obj):
        if isinstance(obj, dict):
            t1 = normalize(obj.get("team1_name", ""))
            t2 = normalize(obj.get("team2_name", ""))
            # Совпадение по первым 5 буквам
            if t1 and t2 and ((n1[:5] in t1 and n2[:5] in t2) or (n1[:5] in t2 and n2[:5] in t1)):
                return obj
            for v in obj.values():
                result = search(v)
                if result: return result
        elif isinstance(obj, list):
            for item in obj:
                result = search(item)
                if result: return result
        return None
    
    return search(data)

def get_team_stats_from_nb(match_data):
    """Достает средние голы из JSON матча (если они там есть)"""
    # Пытаемся найти поля с голами (структура может отличаться, 
    # но мы ищем похожие ключи)
    try:
        # Заглушка, пока не знаем точную структуру JSON.
        # Если nb-bet отдает в JSON те же данные, что и в HTML - 
        # мы найдем их в поле "27" или похожем.
        preview = str(match_data)
        
        import re
        # Ищем паттерн "забивает X ... пропускает Y" прямо в тексте JSON
        matches = re.findall(r"забивает\s+([\d.]+).*?пропускает\s+([\d.]+)", preview)
        
        if len(matches) >= 2:
            home_goals = float(matches[0][0].rstrip(".,"))
            home_miss = float(matches[0][1].rstrip(".,"))
            away_goals = float(matches[1][0].rstrip(".,"))
            away_miss = float(matches[1][1].rstrip(".,"))
            return {
                "avg_scored_home": home_goals,
                "avg_conceded_home": home_miss,
                "avg_scored_away": away_goals,
                "avg_conceded_away": away_miss,
            }
    except Exception:
        pass
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

            # 1. Получаем все матчи с nb-bet (один раз за цикл)
            print("📥 Скачиваем базу матчей с nb-bet...", flush=True)
            all_nb_matches = fetch_nb_bet_json(NB_BET_RESULTS_URL)
            if not all_nb_matches:
                print("❌ Не удалось получить JSON с nb-bet", flush=True)

            games = get_prematch_games()
            count_ok = 0
            count_value = 0

            for game in games:
                parsed = parse_prematch_game(game)
                if not parsed:
                    continue

                # Фильтр: специальные/сборные
                t1 = parsed["team1"].lower()
                t2 = parsed["team2"].lower()
                if ("специальное" in t1 or "специальное" in t2
                        or t1 in ("хозяева", "гости") or t2 in ("хозяева", "гости")):
                    continue

                # Фильтр: тотал 2.5
                tb_25 = parsed["odds"]["TB"].get(2.5)
                if not tb_25 or not tb_25.get("over"):
                    continue

                count_ok += 1

                # Пытаемся найти этот матч в базе nb-bet
                nb_data = None
                if all_nb_matches:
                    nb_match = find_match_in_results(all_nb_matches, parsed["team1"], parsed["team2"])
                    if nb_match:
                        nb_data = get_team_stats_from_nb(nb_match)

                if nb_data and nb_data["avg_scored_home"] is not None:
                    lam_home = (nb_data["avg_scored_home"] + nb_data["avg_conceded_away"]) / 2
                    lam_away = (nb_data["avg_scored_away"] + nb_data["avg_conceded_home"]) / 2
                    lam_total = lam_home + lam_away

                    p_model = prob_over(2.5, lam_total)
                    coef_over = tb_25["over"]
                    p_book = 1 / coef_over
                    edge = p_model - p_book

                    print(
                        f"\n⚽ {parsed['team1']} — {parsed['team2']} (данные с nb-bet)"
                        f"\n   Лига: {parsed['liga']}"
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
                else:
                    # Если в JSON nb-bet не нашли данные, просто пропускаем
                    pass

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
