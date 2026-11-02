import time
import threading
import traceback
from datetime import datetime
import requests
import web
import database as db
import match_momentum
import goal_model as ml
from config import *
from stats_parser import (parse_game, update_match_history, common_ok,
    strategy_individual_total, strategy_xg, strategy_shots, strategy_corners,
    strategy_attacks, strategy_combo)
from live_logic import (check_pending_results, try_send_signal,
    restore_pending_checks, retry_pending_telegram_updates)
from ruscore import get_today_schedule, get_windows

p_game_cache = {}
sent_signals = {}
pending_checks = {}
last_scores = {}
recent_snapshots = {}
schedule_windows = []
schedule_updated_at = None

def get_live_games():
    try:
        url = f"{BASE_URL}/service-api/main-live-feed/v3/games1x2"
        params = {"cfView":3,"count":40,"fcountry":1,"gr":2336,"grMode":4,"lng":"ru","ref":1}
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"🔎 1xlite HTTP: {response.status_code}", flush=True)
        if response.status_code != 200:
            print(f"❌ Ошибка 1xlite: {response.text[:200]}", flush=True); return []
        data = response.json()
        if not isinstance(data, list):
            print(f"❌ 1xlite вернул неожиданный тип: {type(data)}", flush=True); return []
        print(f"📊 Матчей в ответе API: {len(data)}", flush=True)
        return [g for g in data if isinstance(g, dict)]
    except Exception as e:
        print(f"❌ Ошибка получения матчей: {e}", flush=True); return []

def monitor():
    global p_game_cache, sent_signals, pending_checks, last_scores, recent_snapshots
    games = get_live_games()
    if not games: return
    now_ts = int(time.time())
    p_game_cache = {}
    for game in games:
        gid = game.get("id")
        if gid is not None: p_game_cache[gid] = game; p_game_cache[str(gid)] = game
    for game in games:
        try:
            parsed = parse_game(game)
            if not parsed: continue
            gid = parsed.get("game_id", game.get("id"))
            update_match_history(parsed, now_ts, recent_snapshots)
            match_momentum.update_momentum(parsed, now_ts)
            if not common_ok(parsed, gid, now_ts, last_scores): continue

            # Действующие прогнозы на следующий гол: логика стратегий не меняется.
            for fn in (strategy_xg, strategy_shots, strategy_corners, strategy_attacks, strategy_combo):
                strategy = fn(parsed)
                if not strategy: continue
                if try_send_signal(parsed, strategy, now_ts, p_game_cache, sent_signals, pending_checks):
                    break

            # ИТБ проверяется независимо от сигнала на следующий гол.
            individual_candidates = strategy_individual_total(parsed) or []
            for strategy in individual_candidates:
                try_send_signal(parsed, strategy, now_ts, p_game_cache, sent_signals, pending_checks)
        except Exception as e:
            print(f"❌ Ошибка обработки матча {game.get('id')}: {e}", flush=True)
            traceback.print_exc()
    sent_signals = {k:v for k,v in sent_signals.items() if now_ts-v.get("ts",now_ts)<14400}

def refresh_schedule_if_needed():
    global schedule_windows, schedule_updated_at
    now=datetime.now(MOSCOW_TZ)
    if schedule_updated_at and (now-schedule_updated_at).total_seconds()<SCHEDULE_REFRESH_SEC: return
    try:
        schedule=get_today_schedule(); schedule_windows=get_windows(schedule); schedule_updated_at=now
        print(f"📅 Расписание обновлено. Окон: {len(schedule_windows)}", flush=True)
    except Exception as e: print(f"⚠️ Не удалось обновить расписание: {e}", flush=True)

def run_web():
    try: web.app.run(host="0.0.0.0",port=3000,use_reloader=False,threaded=True)
    except Exception as e: print(f"❌ Ошибка запуска сайта: {e}", flush=True)

def retry_telegram_results():
    try: retry_pending_telegram_updates()
    except Exception as e: print(f"❌ Ошибка повторного обновления Telegram: {e}", flush=True); traceback.print_exc()

def check_results_safely():
    try: check_pending_results(pending_checks)
    except Exception as e: print(f"❌ Ошибка проверки результатов: {e}", flush=True); traceback.print_exc()

def bot_loop():
    print("🚀 LIVE-БОТ OLD ЗАПУЩЕН", flush=True)
    try: ml.sync_confirmed_results()
    except Exception as e: print(f"⚠️ Ошибка при старте синхронизации OLD ML: {e}", flush=True)
    while True:
        try:
            now=datetime.now(MOSCOW_TZ)
            check_results_safely(); retry_telegram_results()
            if SLEEP_HOUR_START <= now.hour < SLEEP_HOUR_END:
                print(f"😴 Ночной режим ({now:%H:%M}); проверка результатов продолжается", flush=True)
                time.sleep(60); continue
            refresh_schedule_if_needed(); monitor()
            check_results_safely(); retry_telegram_results(); time.sleep(UPDATE_INTERVAL)
        except KeyboardInterrupt:
            print("⏹️ Остановка по команде", flush=True); break
        except Exception as e:
            print(f"❌ Ошибка основного цикла: {e}", flush=True); traceback.print_exc()
            check_results_safely(); retry_telegram_results(); time.sleep(30)

if __name__ == "__main__":
    db.init_db()
    pending_checks.update(restore_pending_checks())
    threading.Thread(target=run_web, daemon=True).start()
    bot_loop()
