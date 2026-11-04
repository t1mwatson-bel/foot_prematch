import time
import threading
import traceback
from datetime import datetime
import requests
import web
import database as db
from config import *
from stats_parser import parse_prematch_game
from poisson_model import prob_over
from parse_nb_bet_html import parse_nb_bet_html

# Тестовый эндпоинт линии (тот, что ты скинул)
LINE_URL = f"{BASE_URL}/service-api/main-line-feed/v3/games1x2"

def get_prematch_games():
    """Тянет линию с 1xBet по рабочему эндпоинту."""
    url = f"{BASE_URL}/service-api/main-line-feed/v3/games1x2"
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
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"🔎 LINE HTTP: {r.status_code}", flush=True)
        if r.status_code != 200:
            print(f"❌ Ошибка: {r.text[:300]}", flush=True)
            return []
        data = r.json()
        if isinstance(data, list):
            print(f"📊 Получено матчей: {len(data)}", flush=True)
            return [g for g in data if isinstance(g, dict)]
        print(f"❌ Неожиданный тип ответа: {type(data)}", flush=True)
        return []
    except Exception as e:
        print(f"❌ Исключение при запросе: {e}", flush=True)
        return []
def run_web():
    try:
        web.app.run(host="0.0.0.0", port=3000, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"❌ Ошибка запуска сайта: {e}", flush=True)

def bot_loop():
    print("🚀 PREMATCH-БОТ ЗАПУЩЕН (тест линии)", flush=True)
    while True:
        try:
            now = datetime.now(MOSCOW_TZ)
            print(f"\n🔄 [{now:%H:%M:%S}] Загрузка линии...", flush=True)

            games = get_prematch_games()
            for game in games[:10]:  # пока первые 10 для теста
                parsed = parse_prematch_game(game)
                if not parsed:
                    continue
                print(
                    f"\n⚽ {parsed['sport']}: {parsed['team1']} — {parsed['team2']}"
                    f"\n   Лига: {parsed['liga']}"
                    f"\n   Начало: {parsed['start_time']:%d.%m %H:%M}"
                    f"\n   1X2: {parsed['odds']['1']} / {parsed['odds']['X']} / {parsed['odds']['2']}"
                    f"\n   ОЗ: да {parsed['odds']['OZ_Yes']} / нет {parsed['odds']['OZ_No']}"
                )
                # первые 3 тотала
                for i, (param, vals) in enumerate(parsed["odds"]["TB"].items()):
                    if i >= 3: break
                    print(f"   ТБ {param}: {vals.get('over')} / ТМ {param}: {vals.get('under')}")

            print("💤 Спим 5 минут...", flush=True)
            time.sleep(300)

        except KeyboardInterrupt:
            print("⏹️ Остановка", flush=True)
            break
        except Exception as e:
            print(f"❌ Ошибка цикла: {e}", flush=True)
            traceback.print_exc()
            time.sleep(60)

def bot_loop():
    print("🚀 PREMATCH-БОТ ЗАПУЩЕН (тест линии + модель)", flush=True)
    while True:
        try:
            now = datetime.now(MOSCOW_TZ)
            print(f"\n🔄 [{now:%H:%M:%S}] Загрузка линии...", flush=True)

            games = get_prematch_games()
            count_ok = 0
            count_skipped = 0
            count_value = 0

            for game in games:
                parsed = parse_prematch_game(game)
                if not parsed:
                    continue

                t1 = parsed["team1"].lower().strip()
                t2 = parsed["team2"].lower().strip()

                # ФИЛЬТР 1: специальные/сборные ставки
                skip_words = ("специальное", "специальные", "хозяева", "гости", "home", "away")
                if any(w in t1 or w in t2 for w in skip_words):
                    count_skipped += 1
                    continue

                # ФИЛЬТР 2: нужен тотал ровно 2.5
                tb_25 = parsed["odds"]["TB"].get(2.5)
                if not tb_25 or not tb_25.get("over") or not tb_25.get("under"):
                    count_skipped += 1
                    continue

                count_ok += 1
                coef_over = tb_25["over"]

                # --- Poisson-модель ---
                lam = estimate_total_goals(parsed["liga"])
                p_model = prob_over(2.5, lam)   # вероятность ТБ 2.5 по модели
                p_book = 1 / coef_over          # вероятность по кэфу букмекера
                edge = p_model - p_book

                base_info = (
                    f"\n⚽ {parsed['team1']} — {parsed['team2']}"
                    f"\n   Лига: {parsed['liga']}"
                    f"\n   Начало: {parsed['start_time']:%d.%m %H:%M}"
                    f"\n   Кэф ТБ 2.5: {coef_over}"
                    f"\n   Модель: {p_model:.1%} | Букмекер: {p_book:.1%} | Edge: {edge:+.1%}"
                )

                if edge > 0.05:
                    count_value += 1
                    print(f"\n🔥 ВАЛУЙ{base_info}", flush=True)
                    # Сюда позже добавим send_to_telegram(...)
                else:
                    print(f"   ℹ️ {base_info}", flush=True)

            print(
                f"\n✅ Матчей с ТБ 2.5: {count_ok} | "
                f"отсеяно: {count_skipped} | "
                f"валуев: {count_value}",
                flush=True,
            )
            print("💤 Спим 5 минут...", flush=True)
            time.sleep(300)

        except KeyboardInterrupt:
            print("⏹️ Остановка", flush=True)
            break
        except Exception as e:
            print(f"❌ Ошибка цикла: {e}", flush=True)
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot_loop()
