
import time
import threading
import traceback
import sqlite3

from datetime import datetime, timedelta
from math import exp, factorial

import requests
import web
import database as db

from nbbet_stats import get_match_data
from config import *
from telegram_bot import send_telegram
from ruscore import fetch_ruscore_events


# ============================================================
# НОВЫЕ НЕЗАВИСИМЫЕ МОДЕЛИ
# ============================================================

try:
    import checklist_model
    CHECKLIST_AVAILABLE = True
except Exception as e:
    checklist_model = None
    CHECKLIST_AVAILABLE = False
    print(f"⚠️ OLD CHECKLIST 10 пока недоступен: {e}", flush=True)

try:
    import goals_model
    GOALS_MODEL_AVAILABLE = True
except Exception as e:
    goals_model = None
    GOALS_MODEL_AVAILABLE = False
    print(f"⚠️ OLD GOALS MODEL пока недоступна: {e}", flush=True)

try:
    import model_stats
    MODEL_STATS_AVAILABLE = True
except Exception as e:
    model_stats = None
    MODEL_STATS_AVAILABLE = False
    print(f"⚠️ Статистика новых моделей пока недоступна: {e}", flush=True)


# ============================================================
# API ЛИНИИ 1XBET
# ============================================================

LINE_URL = f"{BASE_URL}/service-api/main-line-feed/v3/games1x2"

# Период сканирования прематч-линии
SCAN_INTERVAL = 300

# Не более 40 матчей за один цикл
PREMATCH_COUNT = 40

# Тестовый режим новых моделей
SHADOW_MODE = True


def get_prematch_games():
    params = {
        "cfView": 3,
        "count": PREMATCH_COUNT,
        "fcountry": 1,
        "gr": 2336,
        "grMode": 4,
        "lng": "ru",
        "ref": 1
    }

    try:
        r = requests.get(
            LINE_URL,
            headers=HEADERS,
            params=params,
            timeout=15
        )

        if r.status_code != 200:
            print(f"❌ Ошибка линии: HTTP {r.status_code}", flush=True)
            return []

        data = r.json()

        if isinstance(data, list):
            return [g for g in data if isinstance(g, dict)]

        return []

    except Exception as e:
        print(f"❌ Ошибка загрузки прематч-линии: {e}", flush=True)
        return []


# ============================================================
# ПАРСИНГ ПРЕМАТЧА
# ============================================================

def parse_prematch_game(game):
    try:
        team1 = game["opponent1"]["fullName"]
        team2 = game["opponent2"]["fullName"]

        start_ts = game["startTs"]
        liga = game.get("liga", {}).get(
            "name",
            "Неизвестная лига"
        )

        odds = {"TB": {}}

        for group in game.get("eventGroups", []):
            for event_list in group.get("events", []):
                for ev in event_list:
                    ev_type = ev.get("type")
                    cf = ev.get("cf")

                    if ev_type == 1:
                        odds["1"] = cf
                    elif ev_type == 2:
                        odds["X"] = cf
                    elif ev_type == 3:
                        odds["2"] = cf

        for group in game.get("centralBlockEventGroups", []):
            if group.get("groupId") != 17:
                continue

            for event_list in group.get("events", []):
                for ev in event_list:
                    ev_type = ev.get("type")
                    cf = ev.get("cf")
                    param = ev.get("parameter")

                    if param is None:
                        continue

                    if ev_type == 9:
                        odds["TB"].setdefault(param, {})["over"] = cf

                    elif ev_type == 10:
                        odds["TB"].setdefault(param, {})["under"] = cf

        return {
            "team1": team1,
            "team2": team2,
            "liga": liga,
            "start_time": datetime.fromtimestamp(
                start_ts,
                MOSCOW_TZ
            ),
            "start_ts": int(start_ts),
            "odds": odds
        }

    except Exception as e:
        print(f"⚠️ Ошибка разбора матча: {e}", flush=True)
        return None


# ============================================================
# ИСТОРИЯ КОМАНД ИЗ SQLITE
# ============================================================

def get_team_history(team_name, limit=10):
    """
    Получает последние завершённые матчи команды
    из match_history.

    Ничего не генерирует и не подменяет:
    если истории нет, возвращает пустой список.
    """

    result = []

    try:
        with db.get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    match_date
                FROM match_history
                WHERE LOWER(home_team) = LOWER(?)
                   OR LOWER(away_team) = LOWER(?)
                ORDER BY match_date DESC, id DESC
                LIMIT ?
            """, (
                team_name,
                team_name,
                limit
            )).fetchall()

        for row in rows:
            is_home = (
                str(row["home_team"]).lower()
                == str(team_name).lower()
            )

            if is_home:
                scored = row["home_score"]
                conceded = row["away_score"]
            else:
                scored = row["away_score"]
                conceded = row["home_score"]

            result.append({
                "opponent": (
                    row["away_team"]
                    if is_home
                    else row["home_team"]
                ),
                "is_home": is_home,
                "scored": int(scored),
                "conceded": int(conceded),
                "total": int(scored) + int(conceded),
                "date": row["match_date"]
            })

    except Exception as e:
        print(
            f"⚠️ Ошибка истории команды {team_name}: {e}",
            flush=True
        )

    return result


# ============================================================
# ПОДГОТОВКА ОБЩИХ ДАННЫХ ДЛЯ МОДЕЛЕЙ
# ============================================================

def build_model_input(parsed, nb_data):
    """
    Формирует единый набор исходных данных.

    Обе модели получают одинаковые исходные сведения,
    но рассчитывают прогнозы независимо.
    """

    team1 = parsed["team1"]
    team2 = parsed["team2"]

    home_stats = {}
    away_stats = {}

    if nb_data:
        home_stats = nb_data.get("home_stats") or {}
        away_stats = nb_data.get("away_stats") or {}

    tb25 = parsed["odds"]["TB"].get(2.5) or {}
    odds_over = tb25.get("over")
    odds_under = tb25.get("under")

    try:
        odds_over = float(odds_over) if odds_over else None
    except (TypeError, ValueError):
        odds_over = None

    try:
        odds_under = float(odds_under) if odds_under else None
    except (TypeError, ValueError):
        odds_under = None

    return {
        "team1": team1,
        "team2": team2,
        "league": parsed["liga"],
        "start_time": parsed["start_time"].isoformat(),
        "start_ts": parsed["start_ts"],

        "odds": {
            "over_2_5": odds_over,
            "under_2_5": odds_under
        },

        "home_stats": home_stats,
        "away_stats": away_stats,

        "history": {
            "home": get_team_history(team1, 10),
            "away": get_team_history(team2, 10)
        },

        "data_sources": {
            "nb_bet": bool(nb_data),
            "match_history": True
        }
    }


# ============================================================
# ЗАПУСК OLD CHECKLIST 10 И OLD GOALS MODEL
# ============================================================

def run_shadow_models(match_data):
    """
    Запускает обе модели независимо.

    Новые модели не отправляют Telegram-сообщения.
    Их прогнозы сохраняются отдельно.
    """

    if not SHADOW_MODE:
        return

    if not MODEL_STATS_AVAILABLE:
        print(
            "⚠️ Статистика моделей не подключена. "
            "Тестовые прогнозы не сохраняются.",
            flush=True
        )
        return

    match_name = (
        f"{match_data['team1']} — {match_data['team2']}"
    )

    # --------------------------------------------------------
    # OLD CHECKLIST 10
    # --------------------------------------------------------

    if CHECKLIST_AVAILABLE:
        try:
            prediction = checklist_model.evaluate(match_data)

            if prediction:
                saved = model_stats.save_prediction(
                    model_name="OLD CHECKLIST 10",
                    match_data=match_data,
                    prediction=prediction
                )

                if saved:
                    score = prediction.get("score", "—")
                    print(
                        f"🧾 OLD CHECKLIST 10 | {match_name} "
                        f"| оценка {score}/10 | сохранён",
                        flush=True
                    )

        except Exception as e:
            print(
                f"❌ OLD CHECKLIST 10: ошибка для "
                f"{match_name}: {e}",
                flush=True
            )
            traceback.print_exc()

    # --------------------------------------------------------
    # OLD GOALS MODEL
    # --------------------------------------------------------

    if GOALS_MODEL_AVAILABLE:
        try:
            prediction = goals_model.evaluate(match_data)

            if prediction:
                saved = model_stats.save_prediction(
                    model_name="OLD GOALS MODEL",
                    match_data=match_data,
                    prediction=prediction
                )

                if saved:
                    probability = prediction.get(
                        "probability_over_2_5"
                    )

                    if probability is not None:
                        probability_text = (
                            f"{float(probability) * 100:.1f}%"
                        )
                    else:
                        probability_text = "недостаточно данных"

                    print(
                        f"🧠 OLD GOALS MODEL | {match_name} "
                        f"| вероятность ТБ 2.5: "
                        f"{probability_text} | сохранён",
                        flush=True
                    )

        except Exception as e:
            print(
                f"❌ OLD GOALS MODEL: ошибка для "
                f"{match_name}: {e}",
                flush=True
            )
            traceback.print_exc()


# ============================================================
# СТАРАЯ МАТЕМАТИКА ПРЕЖНЕГО ПРЕМАТЧ-СКАНЕРА
# ============================================================

def poisson_prob(k, lam):
    return (lam ** k) * exp(-lam) / factorial(k)


def prob_over(total, lam):
    p_under = sum(
        poisson_prob(k, lam)
        for k in range(int(total) + 1)
    )
    return 1 - p_under


# ============================================================
# НАКОПЛЕНИЕ РЕЗУЛЬТАТОВ RUSCORE
# ============================================================

def save_ruscore_results():
    print("📥 Накопление истории (Ruscore)...", flush=True)

    yesterday = (
        datetime.now(MOSCOW_TZ) - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    try:
        events = fetch_ruscore_events(yesterday)
        count = 0

        for ev in events:
            home = ev.get("home", {}).get("name")
            away = ev.get("away", {}).get("name")
            score = ev.get("score", [])

            if not home or not away or not score:
                continue

            h_score = None
            a_score = None

            for s in score:
                if s.get("type") == "overall":
                    h_score = s.get("home")
                    a_score = s.get("away")
                    break

            if h_score is None or a_score is None:
                continue

            db.save_match_result(
                home,
                away,
                int(h_score),
                int(a_score),
                yesterday
            )

            count += 1

        print(
            f"✅ Сохранено результатов: {count}",
            flush=True
        )

    except Exception as e:
        print(f"⚠️ Ошибка Ruscore: {e}", flush=True)


# ============================================================
# ВЕБ-СЕРВЕР
# ============================================================

def run_web():
    try:
        web.app.run(
            host="0.0.0.0",
            port=3000,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        print(f"❌ Ошибка сайта: {e}", flush=True)


# ============================================================
# ОСНОВНОЙ ЦИКЛ
# ============================================================

def bot_loop():
    print(
        "🚀 OLD FOOTBALL PREMATCH ЗАПУЩЕН",
        flush=True
    )

    print(
        f"🧾 OLD CHECKLIST 10: "
        f"{'ON' if CHECKLIST_AVAILABLE else 'OFF'}",
        flush=True
    )

    print(
        f"🧠 OLD GOALS MODEL: "
        f"{'ON' if GOALS_MODEL_AVAILABLE else 'OFF'}",
        flush=True
    )

    print(
        f"🧪 SHADOW MODE: {SHADOW_MODE}",
        flush=True
    )

    last_save_date = None

    while True:
        try:
            now = datetime.now(MOSCOW_TZ)

            print(
                f"\n🔄 [{now:%d.%m.%Y %H:%M:%S}] "
                f"Загрузка прематч-линии...",
                flush=True
            )

            # Ежедневное накопление истории
            if (
                now.hour == 3
                and last_save_date != now.date()
            ):
                save_ruscore_results()
                last_save_date = now.date()

            games = get_prematch_games()

            count_ok = 0
            count_value = 0
            count_shadow = 0

            for game in games:
                parsed = parse_prematch_game(game)

                if not parsed:
                    continue

                team1 = parsed["team1"].lower()
                team2 = parsed["team2"].lower()

                if (
                    "специальное" in team1
                    or "специальное" in team2
                    or team1 in ("хозяева", "гости")
                    or team2 in ("хозяева", "гости")
                ):
                    continue

                count_ok += 1

                # Получение статистики NB-Bet
                try:
                    nb_data = get_match_data(
                        parsed["team1"],
                        parsed["team2"]
                    )
                except Exception as e:
                    print(
                        f"⚠️ NB-Bet: ошибка "
                        f"{parsed['team1']} — {parsed['team2']}: {e}",
                        flush=True
                    )
                    nb_data = None

                # Общий пакет данных для независимых моделей
                match_data = build_model_input(
                    parsed,
                    nb_data
                )

                # Запуск двух новых моделей
                if CHECKLIST_AVAILABLE or GOALS_MODEL_AVAILABLE:
                    run_shadow_models(match_data)
                    count_shadow += 1

                # ------------------------------------------------
                # СТАРЫЙ ПРЕМАТЧ-АЛГОРИТМ
                # ------------------------------------------------

                tb25 = parsed["odds"]["TB"].get(2.5)

                if not tb25 or not tb25.get("over"):
                    continue

                try:
                    coef_over = float(tb25["over"])
                except (TypeError, ValueError):
                    continue

                p_book = 1 / coef_over

                if nb_data:
                    h_xg = float(
                        nb_data["home_stats"].get("avg_xg") or 0
                    )

                    a_xg = float(
                        nb_data["away_stats"].get("avg_xg") or 0
                    )

                    lam_total = h_xg + a_xg

                    if lam_total > 0:
                        p_model = prob_over(
                            2.5,
                            lam_total
                        )

                        print(
                            f"📈 Старый сканер xG: "
                            f"{h_xg:.2f} + {a_xg:.2f} "
                            f"= {lam_total:.2f} "
                            f"| Модель: {p_model:.1%}",
                            flush=True
                        )

                    else:
                        if coef_over < 1.50:
                            p_model = p_book + 0.03
                        elif coef_over > 2.50:
                            p_model = p_book - 0.03
                        else:
                            p_model = p_book + 0.01

                else:
                    if coef_over < 1.50:
                        p_model = p_book + 0.03
                    elif coef_over > 2.50:
                        p_model = p_book - 0.03
                    else:
                        p_model = p_book + 0.01

                edge = p_model - p_book

                if edge > 0.05:
                    count_value += 1

                    msg = (
                        f"🔥 <b>ВАЛУЙ: ТБ 2.5</b>\n\n"
                        f"⚽ <b>{parsed['team1']} — "
                        f"{parsed['team2']}</b>\n"
                        f"🏆 {parsed['liga']}\n"
                        f"🕒 {parsed['start_time']:%d.%m %H:%M}\n"
                        f"💰 Кэф: {coef_over}\n"
                        f"📊 Edge: +{edge:.1%}"
                    )

                    send_telegram(msg)

                    print(
                        f"🔥 ВАЛУЙ: {parsed['team1']} — "
                        f"{parsed['team2']}",
                        flush=True
                    )

            print(
                f"\n✅ Матчей обработано: {count_ok}\n"
                f"🔥 Старых валуев: {count_value}\n"
                f"🧪 Матчей передано новым моделям: "
                f"{count_shadow}\n"
                f"⏳ Следующее сканирование через "
                f"{SCAN_INTERVAL // 60} минут.",
                flush=True
            )

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("🛑 Остановка OLD FOOTBALL", flush=True)
            break

        except Exception as e:
            print(
                f"❌ Ошибка основного цикла: {e}",
                flush=True
            )
            traceback.print_exc()
            time.sleep(60)


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    db.init_db()

    if MODEL_STATS_AVAILABLE:
        try:
            model_stats.init_db()
        except Exception as e:
            print(
                f"⚠️ Ошибка инициализации статистики моделей: {e}",
                flush=True
            )

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    bot_loop()
