
# -*- coding: utf-8 -*-

import time
import threading
import traceback
import html

from datetime import datetime, timedelta
from math import exp, factorial

import requests
import web
import database as db

from config import *
from nbbet_stats import get_match_data
from telegram_bot import send_telegram
from ruscore import fetch_ruscore_events
# --- ВЫЗОВ ОЧИСТКИ ---
# Проверяем, есть ли файл-флаг. Если нет — чистим базу.
if not os.path.exists(".db_cleaned"):
    import clean_db
    clean_db.run_cleanup()
# --------------------


# ============================================================
# НЕЗАВИСИМЫЕ МОДЕЛИ OLD
# ============================================================

try:
    import checklist_model
    CHECKLIST_AVAILABLE = True
except Exception as e:
    checklist_model = None
    CHECKLIST_AVAILABLE = False
    print(f"⚠️ OLD CHECKLIST 10 недоступен: {e}", flush=True)

try:
    import goals_model
    GOALS_MODEL_AVAILABLE = True
except Exception as e:
    goals_model = None
    GOALS_MODEL_AVAILABLE = False
    print(f"⚠️ OLD GOALS MODEL недоступна: {e}", flush=True)

try:
    import model_stats
    MODEL_STATS_AVAILABLE = True
except Exception as e:
    model_stats = None
    MODEL_STATS_AVAILABLE = False
    print(f"⚠️ Статистика моделей недоступна: {e}", flush=True)


# ============================================================
# НАСТРОЙКИ
# ============================================================

LINE_URL = f"{BASE_URL}/service-api/main-line-feed/v3/games1x2"

SCAN_INTERVAL = 300
PREMATCH_COUNT = 40

# Сохраняем все прогнозы моделей на сайте.
# В Telegram отправляем только прошедшие фильтры.
SHADOW_MODE = True

CHECKLIST_MIN_SCORE = 8
GOALS_MIN_PROBABILITY = 0.65


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        result = float(value)

        if result != result:
            return None

        return result

    except (TypeError, ValueError):
        return None


def format_percent(value):
    number = safe_float(value)

    if number is None:
        return "нет данных"

    if number <= 1:
        number *= 100

    return f"{number:.1f}%"


def send_model_prediction(
    prediction_id,
    model_name,
    match_data,
    prediction,
    message
):
    """
    Отправляет прогноз модели в Telegram.
    Повторно уже опубликованные прогнозы не отправляет.
    """

    if not prediction_id:
        print(
            f"⚠️ {model_name}: отсутствует ID прогноза",
            flush=True
        )
        return False

    try:
        existing = model_stats.get_prediction(prediction_id)

        if not existing:
            print(
                f"⚠️ {model_name}: прогноз {prediction_id} "
                f"не найден в базе",
                flush=True
            )
            return False

        if existing.get("telegram_sent"):
            return False

        message_id = send_telegram(message)

        if not message_id:
            print(
                f"❌ {model_name}: Telegram не подтвердил отправку",
                flush=True
            )
            return False

        saved = model_stats.set_telegram_message(
            prediction_id,
            message_id,
            message
        )

        if not saved:
            print(
                f"⚠️ {model_name}: сообщение отправлено, "
                f"но message_id не удалось сохранить. "
                f"ID сообщения: {message_id}",
                flush=True
            )
            return False

        print(
            f"📨 {model_name}: прогноз отправлен в Telegram "
            f"(ID {prediction_id}, сообщение {message_id})",
            flush=True
        )

        return True

    except Exception as e:
        print(
            f"❌ Ошибка отправки {model_name}: {e}",
            flush=True
        )
        traceback.print_exc()
        return False


def make_checklist_message(match_data, prediction):
    home = html.escape(str(match_data["team1"]))
    away = html.escape(str(match_data["team2"]))
    league = html.escape(str(match_data.get("league") or "Неизвестная лига"))

    start_time = match_data.get("start_time", "")

    try:
        start_time = datetime.fromisoformat(
            str(start_time)
        ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        start_time = str(start_time)

    score = safe_float(prediction.get("score"))

    score_text = (
        f"{score:g}/10"
        if score is not None
        else "нет данных"
    )

    return (
        f"🧾 <b>OLD CHECKLIST 10</b>\n\n"
        f"⚽ <b>{home} — {away}</b>\n"
        f"🏆 {league}\n"
        f"🕒 {start_time}\n\n"
        f"🎯 Чек-лист: <b>{score_text}</b>\n"
        f"📊 Рынок: <b>ТБ 2.5</b>\n\n"
        f"✅ Прогноз прошёл фильтр качества"
    )


def make_goals_message(
    match_data,
    probability,
    odds,
    value
):
    home = html.escape(str(match_data["team1"]))
    away = html.escape(str(match_data["team2"]))
    league = html.escape(str(match_data.get("league") or "Неизвестная лига"))

    start_time = match_data.get("start_time", "")

    try:
        start_time = datetime.fromisoformat(
            str(start_time)
        ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        start_time = str(start_time)

    return (
        f"🧠 <b>OLD GOALS MODEL</b>\n\n"
        f"⚽ <b>{home} — {away}</b>\n"
        f"🏆 {league}\n"
        f"🕒 {start_time}\n\n"
        f"🎯 Прогноз: <b>ТБ 2.5</b>\n"
        f"📊 Вероятность: <b>{probability * 100:.1f}%</b>\n"
        f"💰 Коэффициент: <b>{odds:.2f}</b>\n"
        f"📈 Value: <b>+{value * 100:.1f}%</b>\n\n"
        f"✅ Прогноз прошёл фильтр качества"
    )


# ============================================================
# ПРЕМАТЧ-ЛИНИЯ
# ============================================================

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
        response = requests.get(
            LINE_URL,
            headers=HEADERS,
            params=params,
            timeout=15
        )

        if response.status_code != 200:
            print(
                f"❌ Ошибка линии: HTTP {response.status_code}",
                flush=True
            )
            return []

        data = response.json()

        if isinstance(data, list):
            return [
                game for game in data
                if isinstance(game, dict)
            ]

        return []

    except Exception as e:
        print(f"❌ Ошибка загрузки линии: {e}", flush=True)
        return []


# ============================================================
# ПАРСИНГ МАТЧА
# ============================================================

def parse_prematch_game(game):
    try:
        team1 = game["opponent1"]["fullName"]
        team2 = game["opponent2"]["fullName"]

        start_ts = int(game["startTs"])

        liga = game.get("liga", {}).get(
            "name",
            "Неизвестная лига"
        )

        event_id = (
            game.get("id")
            or game.get("I")
            or game.get("ID")
            or game.get("eventId")
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

                    try:
                        param = float(param)
                    except (TypeError, ValueError):
                        continue

                    if ev_type == 9:
                        odds["TB"].setdefault(
                            param, {}
                        )["over"] = cf

                    elif ev_type == 10:
                        odds["TB"].setdefault(
                            param, {}
                        )["under"] = cf

        return {
            "event_id": str(event_id) if event_id else None,
            "team1": team1,
            "team2": team2,
            "liga": liga,
            "start_time": datetime.fromtimestamp(
                start_ts,
                MOSCOW_TZ
            ),
            "start_ts": start_ts,
            "odds": odds
        }

    except Exception as e:
        print(f"⚠️ Ошибка разбора матча: {e}", flush=True)
        return None


# ============================================================
# ИСТОРИЯ КОМАНД
# ============================================================

def get_team_history(team_name, limit=10):
    result = []

    try:
        conn = db.get_connection()

        try:
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

        finally:
            conn.close()

        for row in rows:
            is_home = (
                str(row["home_team"]).lower()
                == str(team_name).lower()
            )

            try:
                if is_home:
                    scored = int(row["home_score"])
                    conceded = int(row["away_score"])
                else:
                    scored = int(row["away_score"])
                    conceded = int(row["home_score"])
            except (TypeError, ValueError):
                continue

            result.append({
                "opponent": (
                    row["away_team"]
                    if is_home
                    else row["home_team"]
                ),
                "is_home": is_home,
                "scored": scored,
                "conceded": conceded,
                "total": scored + conceded,
                "date": row["match_date"]
            })

    except Exception as e:
        print(
            f"⚠️ Ошибка истории {team_name}: {e}",
            flush=True
        )

    return result


# ============================================================
# ОБЩИЕ ДАННЫЕ ДЛЯ МОДЕЛЕЙ
# ============================================================

def build_model_input(parsed, nb_data):
    team1 = parsed["team1"]
    team2 = parsed["team2"]

    home_stats = {}
    away_stats = {}

    if isinstance(nb_data, dict):
        home_stats = nb_data.get("home_stats") or {}
        away_stats = nb_data.get("away_stats") or {}

    tb25 = parsed["odds"]["TB"].get(2.5) or {}

    try:
        odds_over = float(tb25.get("over"))
    except (TypeError, ValueError):
        odds_over = None

    try:
        odds_under = float(tb25.get("under"))
    except (TypeError, ValueError):
        odds_under = None

    home_history = get_team_history(team1, 10)
    away_history = get_team_history(team2, 10)

    return {
        "event_id": parsed.get("event_id"),

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
            "home": home_history,
            "away": away_history
        },

        "data_sources": {
            "nb_bet": bool(nb_data),
            "match_history": bool(
                home_history or away_history
            )
        }
    }


# ============================================================
# ЗАПУСК ДВУХ МОДЕЛЕЙ И ФИЛЬТРЫ TELEGRAM
# ============================================================

def run_shadow_models(match_data):
    if not MODEL_STATS_AVAILABLE:
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

            if (
                isinstance(prediction, dict)
                and prediction.get("ready")
                and prediction.get("candidate")
            ):
                prediction_id = model_stats.save_prediction(
                    model_name="OLD CHECKLIST 10",
                    match_data=match_data,
                    prediction=prediction
                )

                if prediction_id:
                    score = safe_float(
                        prediction.get("score")
                    )

                    print(
                        f"🧾 OLD CHECKLIST 10 | {match_name} "
                        f"| {score if score is not None else 'нет данных'}/10 "
                        f"| сохранён",
                        flush=True
                    )

                    # Публикуем только при результате 8/10 или выше.
                    if (
                        score is not None
                        and score >= CHECKLIST_MIN_SCORE
                    ):
                        message = make_checklist_message(
                            match_data,
                            prediction
                        )

                        send_model_prediction(
                            prediction_id,
                            "OLD CHECKLIST 10",
                            match_data,
                            prediction,
                            message
                        )

                    else:
                        print(
                            f"⏭ CHECKLIST: {match_name} "
                            f"| ниже порога {CHECKLIST_MIN_SCORE}/10 "
                            f"| оставлен на сайте",
                            flush=True
                        )

        except Exception as e:
            print(
                f"❌ CHECKLIST: {match_name}: {e}",
                flush=True
            )
            traceback.print_exc()

    # --------------------------------------------------------
    # OLD GOALS MODEL
    # --------------------------------------------------------

    if GOALS_MODEL_AVAILABLE:
        try:
            prediction = goals_model.evaluate(match_data)

            if (
                isinstance(prediction, dict)
                and prediction.get("ready")
                and prediction.get("candidate")
            ):
                prediction_id = model_stats.save_prediction(
                    model_name="OLD GOALS MODEL",
                    match_data=match_data,
                    prediction=prediction
                )

                if prediction_id:
                    probability = safe_float(
                        prediction.get(
                            "probability_over_2_5"
                        )
                    )

                    if probability is not None and probability > 1:
                        probability /= 100

                    odds = safe_float(
                        match_data.get("odds", {}).get(
                            "over_2_5"
                        )
                    )

                    value = None

                    if (
                        probability is not None
                        and odds is not None
                        and odds > 1
                    ):
                        value = probability * odds - 1

                    probability_text = (
                        f"{probability * 100:.1f}%"
                        if probability is not None
                        else "нет данных"
                    )

                    value_text = (
                        f"{value * 100:+.1f}%"
                        if value is not None
                        else "нет данных"
                    )

                    print(
                        f"🧠 OLD GOALS MODEL | {match_name} "
                        f"| вероятность {probability_text} "
                        f"| Value {value_text} "
                        f"| сохранён",
                        flush=True
                    )

                    # Два обязательных условия:
                    # вероятность не ниже 65%;
                    # Value строго положительный.
                    if (
                        probability is not None
                        and probability >= GOALS_MIN_PROBABILITY
                        and odds is not None
                        and odds > 1
                        and value is not None
                        and value > 0
                    ):
                        message = make_goals_message(
                            match_data,
                            probability,
                            odds,
                            value
                        )

                        send_model_prediction(
                            prediction_id,
                            "OLD GOALS MODEL",
                            match_data,
                            prediction,
                            message
                        )

                    else:
                        print(
                            f"⏭ GOALS MODEL: {match_name} "
                            f"| не прошёл фильтр "
                            f"(вероятность от 65% + положительный Value) "
                            f"| оставлен на сайте",
                            flush=True
                        )

        except Exception as e:
            print(
                f"❌ GOALS MODEL: {match_name}: {e}",
                flush=True
            )
            traceback.print_exc()


# ============================================================
# СТАРАЯ МАТЕМАТИКА ПРЕМАТЧ-СКАНЕРА
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
# СОХРАНЕНИЕ РЕЗУЛЬТАТОВ RUSCORE
# ============================================================

def save_ruscore_results():
    print("📥 Накопление истории Ruscore...", flush=True)

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

            for item in score:
                if item.get("type") == "overall":
                    h_score = item.get("home")
                    a_score = item.get("away")
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
            f"✅ Сохранено результатов Ruscore: {count}",
            flush=True
        )

    except Exception as e:
        print(f"⚠️ Ошибка Ruscore: {e}", flush=True)
        traceback.print_exc()


# ============================================================
# СВЕРКА РЕЗУЛЬТАТОВ НОВЫХ МОДЕЛЕЙ
# ============================================================

def sync_model_results():
    if not MODEL_STATS_AVAILABLE:
        return

    try:
        updated = model_stats.sync_results_from_history()

        if updated:
            print(
                f"🏁 Обновлены результаты новых моделей: {updated}",
                flush=True
            )

    except Exception as e:
        print(
            f"⚠️ Ошибка синхронизации моделей: {e}",
            flush=True
        )
        traceback.print_exc()


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
    print("🚀 OLD FOOTBALL PREMATCH ЗАПУЩЕН", flush=True)

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
        f"📊 MODEL STATS: "
        f"{'ON' if MODEL_STATS_AVAILABLE else 'OFF'}",
        flush=True
    )

    print(
        f"🧪 SHADOW MODE: {SHADOW_MODE}",
        flush=True
    )

    print(
        f"📨 TELEGRAM FILTERS: "
        f"CHECKLIST >= {CHECKLIST_MIN_SCORE}/10 | "
        f"GOALS >= {GOALS_MIN_PROBABILITY * 100:.0f}% + positive Value",
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

            # Ежедневное сохранение истории.
            if (
                now.hour == 3
                and last_save_date != now.date()
            ):
                save_ruscore_results()
                last_save_date = now.date()

            # Сверяем результаты на каждом цикле.
            sync_model_results()

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

                # Получение NB-Bet.
                try:
                    nb_data = get_match_data(
                        parsed["team1"],
                        parsed["team2"]
                    )

                except Exception as e:
                    print(
                        f"⚠️ NB-Bet: {parsed['team1']} — "
                        f"{parsed['team2']}: {e}",
                        flush=True
                    )
                    nb_data = None

                match_data = build_model_input(
                    parsed,
                    nb_data
                )

                # Новые независимые модели.
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
                    try:
                        h_xg = float(
                            nb_data["home_stats"].get("avg_xg") or 0
                        )

                        a_xg = float(
                            nb_data["away_stats"].get("avg_xg") or 0
                        )
                    except (TypeError, ValueError):
                        h_xg = 0
                        a_xg = 0

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

            # Повторная сверка после обработки линии.
            sync_model_results()

            print(
                f"\n✅ Матчей обработано: {count_ok}\n"
                f"🔥 Старых валуев: {count_value}\n"
                f"🧪 Матчей передано новым моделям: {count_shadow}\n"
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
            traceback.print_exc()

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    bot_loop()
