import time
import json
import re
import requests
Вот у меня был Live logic import time
import json
import re
import requests
from datetime import datetime, timedelta

from config import *
from telegram_bot import send_telegram, edit_telegram, format_with_result
from stats_parser import *
from ruscore import fetch_ruscore_events, find_match, parse_score_for_match
import database as db
import goal_model as ml


# ============================================================
# ЖУРНАЛ РЕЗУЛЬТАТОВ
# ============================================================

def log_result_record(record):
    try:
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        print(f"⚠️ Не удалось записать {RESULTS_FILE}: {e}", flush=True)


# ============================================================
# ПОЛУЧЕНИЕ РЕЗУЛЬТАТОВ ИЗ 1XLITE
# ============================================================

def fetch_1xlite_live_games():
    """Получает текущую live-ленту для проверки сигналов."""
    url = f"{BASE_URL}/service-api/main-live-feed/v3/games1x2"

    params = {
        "cfView": 3,
        "count": 40,
        "fcountry": 1,
        "gr": 2336,
        "grMode": 4,
        "lng": "ru",
        "ref": 1,
    }

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            print(
                f"⚠️ 1xLite live: HTTP {response.status_code}",
                flush=True,
            )
            return None

        data = response.json()

        if isinstance(data, list):
            return [g for g in data if isinstance(g, dict)]

        if isinstance(data, dict):
            for field in (
                "Value", "value", "games", "Games", "events", "Events"
            ):
                value = data.get(field)
                if isinstance(value, list):
                    return [g for g in value if isinstance(g, dict)]

        print("⚠️ 1xLite live: неизвестный формат ответа", flush=True)
        return None

    except Exception as e:
        print(f"⚠️ Ошибка запроса live-ленты 1xLite: {e}", flush=True)
        return None


def fetch_1xlite_game_by_id(game_id):
    """Запрашивает конкретный матч по ID."""
    url = f"{BASE_URL}/service-api/LiveFeed/GetGameZip"

    params = {
        "id": str(game_id),
        "lng": "ru",
        "cfview": 0,
        "isSubGames": "true",
        "GroupEvents": "true",
        "allEventsGroupSubGames": "true",
        "countevents": 250,
        "partner": 36,
    }

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=12,
        )

        if response.status_code != 200:
            print(
                f"⚠️ GetGameZip: HTTP {response.status_code}, ID={game_id}",
                flush=True,
            )
            return None

        data = response.json()

        if not isinstance(data, dict):
            print(
                f"⚠️ GetGameZip: ответ не является объектом, ID={game_id}",
                flush=True,
            )
            return None

        game = data.get("Value")

        if isinstance(game, dict):
            game["_requested_id"] = str(game_id)
            return game

        if any(k in data for k in ("SC", "scores", "id", "ID")):
            data["_requested_id"] = str(game_id)
            return data

        print(
            f"⚠️ GetGameZip не вернул данные матча, ID={game_id}",
            flush=True,
        )
        return None

    except Exception as e:
        print(f"⚠️ Ошибка GetGameZip для ID={game_id}: {e}", flush=True)
        return None

# ============================================================
# ПОЛУЧЕНИЕ КОЭФФИЦИЕНТА НА ИНДИВИДУАЛЬНЫЙ ТОТАЛ
# ============================================================

def get_odd_individual_total(game, side="home", target=0.5):
    """
    Ищет коэффициент на Индивидуальный Тотал команды.

    side="home" — ИТ Хозяев.
    side="away" — ИТ Гостей.

    target — линия тотала (0.5, 1.5, 2.5 и т.д.).

    Поля 1xLite (GetGameZip):
        T / type      — тип события (9=общий тотал, 10=ИТ1, 11=ИТ2)
        P / parameter — линия
        C / cf        — коэффициент
    """

    if not isinstance(game, dict):
        return None

    try:
        target = float(target)
    except (TypeError, ValueError):
        target = 0.5

    if side not in ("home", "away"):
        return None

    # ИТ в 1xLite обычно находятся в группе 17 ("Тоталы").
    # На всякий случай проверяем все группы.
    groups = game.get("centralBlockEventGroups") or []

    if not isinstance(groups, list):
        return None

    for grp in groups:
        if not isinstance(grp, dict):
            continue

        event_lists = grp.get("events") or []

        if not isinstance(event_lists, list):
            continue

        for event_list in event_lists:
            if not isinstance(event_list, list):
                continue

            for item in event_list:
                if not isinstance(item, dict):
                    continue

                item_type = item.get("T", item.get("type"))
                parameter = item.get("P", item.get("parameter"))
                odd = item.get("C", item.get("cf"))

                try:
                    item_type = (
                        int(item_type)
                        if item_type is not None
                        else 0
                    )
                    parameter = float(parameter)
                    odd = float(odd)
                except (TypeError, ValueError):
                    continue

                # Проверяем нужную линию.
                if abs(parameter - target) > 0.001:
                    continue

                # Отбрасываем некорректные коэффициенты.
                if odd <= 1.0:
                    continue

                # ИТ хозяев.
                if side == "home" and item_type == 10:
                    return odd

                # ИТ гостей.
                if side == "away" and item_type == 11:
                    return odd

    return None 


def find_1xlite_game(games, game_id):
    """Ищет матч по точному ID."""
    if not games:
        return None

    target = str(game_id)

    for game in games:
        if not isinstance(game, dict):
            continue

        candidates = (
            game.get("id"),
            game.get("ID"),
            game.get("I"),
            game.get("_requested_id"),
        )

        if any(
            value is not None and str(value) == target
            for value in candidates
        ):
            return game

    return None


def _parse_score_value(value):
    """Разбирает счёт из строки или словаря."""
    if isinstance(value, str):
        match = re.search(
            r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$",
            value,
        )
        if match:
            return int(match.group(1)), int(match.group(2))

    if isinstance(value, dict):
        home = value.get("home", value.get("s1", value.get("S1")))
        away = value.get("away", value.get("s2", value.get("S2")))

        try:
            if home is not None and away is not None:
                return int(home), int(away)
        except (TypeError, ValueError):
            pass

    return None, None


def parse_1xlite_score(game):
    """Разбирает счёт из известных вариантов ответа 1xLite."""
    if not isinstance(game, dict):
        return None, None

    scores = game.get("scores") or {}

    if isinstance(scores, dict):
        for key in ("fullScore", "score", "currentScore", "result"):
            s1, s2 = _parse_score_value(scores.get(key))
            if s1 is not None and s2 is not None:
                return s1, s2

        s1, s2 = _parse_score_value(scores)
        if s1 is not None and s2 is not None:
            return s1, s2

    sc = game.get("SC") or {}

    if isinstance(sc, dict):
        fs = sc.get("FS") or {}

        if isinstance(fs, dict):
            try:
                s1 = fs.get("S1")
                s2 = fs.get("S2")

                if s1 is not None and s2 is not None:
                    return int(s1), int(s2)
            except (TypeError, ValueError):
                pass

        for key in ("FS", "S", "score", "Score"):
            s1, s2 = _parse_score_value(sc.get(key))
            if s1 is not None and s2 is not None:
                return s1, s2

    for key in ("fullScore", "score", "Score", "result"):
        s1, s2 = _parse_score_value(game.get(key))
        if s1 is not None and s2 is not None:
            return s1, s2

    return None, None


# ============================================================
# ПРОВЕРКА ЗАВЕРШЕНИЯ МАТЧА
# ============================================================

def _collect_status_text(value):
    """Собирает текстовые статусы из вложенных объектов."""
    parts = []

    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in {
                "fs", "score", "scores", "s1", "s2", "value"
            }:
                if str(key).lower() in {"s1", "s2"}:
                    continue

            if isinstance(nested, (dict, list)):
                parts.extend(_collect_status_text(nested))
            elif nested is not None and isinstance(nested, str):
                parts.append(nested)

    elif isinstance(value, list):
        for nested in value:
            parts.extend(_collect_status_text(nested))

    return parts


def is_finished_status(status):
    """Распознаёт явные текстовые признаки завершения матча."""
    if isinstance(status, dict):
        text = " ".join(_collect_status_text(status))
    else:
        text = str(status or "")

    text = text.lower().replace("ё", "е")
    text = " ".join(
        text.replace("_", " ").replace("-", " ").split()
    )

    finished_values = {
        "finished", "ended", "ft", "final", "complete", "completed",
        "full time", "match finished", "match ended",
        "завершен", "завершена", "матч завершен",
        "окончен", "окончена", "закончен", "закончена",
        "матч окончен", "матч закончен", "игра завершена",
        "завершение матча",
    }

    if text in finished_values:
        return True

    prefixes = (
        "finished ", "ended ", "completed ", "full time ",
        "match finished ", "match ended ", "завершен ",
        "завершена ", "матч завершен ", "окончен ",
        "окончена ", "закончен ", "закончена ",
    )

    return text.startswith(prefixes)


def is_1xlite_finished(game):
    """Проверяет завершение по текстовым статусам и явным флагам."""
    if not isinstance(game, dict):
        return False

    scores = game.get("scores") or {}
    sc = game.get("SC") or {}

    status_values = [
        game.get("status"),
        game.get("statusName"),
        game.get("statusText"),
        game.get("statusLine"),
        game.get("statusLineStr"),
        game.get("periodName"),
        game.get("currentPeriodName"),
    ]

    if isinstance(scores, dict):
        status_values.extend([
            scores.get("status"),
            scores.get("statusName"),
            scores.get("statusText"),
            scores.get("statusLine"),
            scores.get("statusLineStr"),
            scores.get("currentPeriodName"),
        ])

    if isinstance(sc, dict):
        status_values.extend([
            sc.get("status"),
            sc.get("statusName"),
            sc.get("statusText"),
            sc.get("periodName"),
            sc.get("currentPeriodName"),
        ])

    for value in status_values:
        if value is not None and is_finished_status(value):
            return True

    for container in (game, scores, sc):
        if not isinstance(container, dict):
            continue

        for field in ("isFinished", "finished", "isEnded", "ended"):
            value = container.get(field)

            if value is True or value == 1:
                return True

            if isinstance(value, str):
                if value.strip().lower() in (
                    "true", "yes", "finished", "ended"
                ):
                    return True

    return False


def get_ruscore_status(event):
    """Извлекает статус Ruscore из разных вариантов структуры."""
    if not isinstance(event, dict):
        return ""

    parts = []

    for key in (
        "status", "statusName", "statusText", "state",
        "period", "periodName", "matchStatus",
    ):
        value = event.get(key)

        if isinstance(value, dict):
            for subkey in ("label", "name", "text", "value", "short"):
                nested = value.get(subkey)
                if isinstance(nested, str):
                    parts.append(nested)
        elif isinstance(value, str):
            parts.append(value)

    return " ".join(parts)


# ============================================================
# ВОССТАНОВЛЕНИЕ ПРОВЕРОК ПОСЛЕ ПЕРЕЗАПУСКА
# ============================================================

def restore_pending_checks():
    """Восстанавливает ожидающие сигналы из основной БД."""
    restored = {}
    now = int(time.time())

    try:
        rows = db.get_pending_live_signals()
    except Exception as e:
        print(f"❌ Не удалось загрузить проверки из БД: {e}", flush=True)
        return restored

    for row in rows:
        key = str(row.get("game_id") or "").strip()

        if not key:
            continue

        match_name = str(row.get("match_name") or "").strip()
        team1 = str(row.get("team1") or "").strip()
        team2 = str(row.get("team2") or "").strip()

        if not team1 or not team2:
            for separator in (" — ", " – ", " - ", " vs ", " VS "):
                if separator in match_name:
                    parts = match_name.split(separator, 1)

                    if len(parts) == 2:
                        team1 = team1 or parts[0].strip()
                        team2 = team2 or parts[1].strip()
                        break

        old_s1 = row.get("old_s1")
        old_s2 = row.get("old_s2")

        if old_s1 is None or old_s2 is None:
            raw_score = str(row.get("score") or "").strip()
            match = re.search(
                r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$",
                raw_score,
            )

            if match:
                old_s1 = int(match.group(1))
                old_s2 = int(match.group(2))

        if old_s1 is None or old_s2 is None:
            print(
                f"⚠️ Сигнал {key}: исходный счёт отсутствует; "
                "автоматическая проверка невозможна",
                flush=True,
            )
            continue

        try:
            old_s1 = int(old_s1)
            old_s2 = int(old_s2)
        except (TypeError, ValueError):
            print(f"⚠️ Сигнал {key}: некорректный исходный счёт", flush=True)
            continue

        sent_at = int(row.get("sent_at") or now)
        signal_ts = int(row.get("signal_ts") or sent_at)

        date_str = row.get("date_str")

        if not date_str:
            date_str = datetime.fromtimestamp(
                signal_ts,
                MOSCOW_TZ,
            ).strftime("%Y-%m-%d")

        message_id = row.get("message_id")

        try:
            message_id = int(message_id) if message_id else None
        except (TypeError, ValueError):
            message_id = None

        try:
            attempts = int(row.get("attempts") or 0)
        except (TypeError, ValueError):
            attempts = 0

        try:
            check_after = int(row.get("check_after") or now)
        except (TypeError, ValueError):
            check_after = now

        info = {
            "team1": team1,
            "team2": team2,
            "match": match_name or (
                f"{team1} — {team2}"
                if team1 and team2
                else f"Матч {key}"
            ),
            "date_str": date_str,
            "old_s1": old_s1,
            "old_s2": old_s2,
            "minute": int(row.get("minute") or 0),
            "signal_ts": signal_ts,
            "message_id": message_id,
            "base_text": row.get("base_text") or "",
            "strategy": row.get("strategy") or "не указана",
            "odd": row.get("odds"),
            "check_after": min(check_after, now),
            "attempts": attempts,
            "market_type": row.get("market_type"),  # <-- Восстанавливаем тип рынка
        }

        restored[key] = info

        try:
            persist_check(key, info)
        except Exception as e:
            print(
                f"⚠️ Не удалось обновить данные сигнала {key}: {e}",
                flush=True,
            )

        if not team1 or not team2:
            print(
                f"⚠️ Сигнал {key}: не хватает названий команд "
                "для поиска в Ruscore",
                flush=True,
            )

    print(
        f"♻️ Восстановлено ожидающих проверок: {len(restored)}",
        flush=True,
    )

    return restored


def persist_check(game_id, info):
    try:
        # ВАЖНО: Если в базе нет колонки market_type, 
        # этот код выдаст ошибку. Добавь колонку в БД (в database.py),
        # или закомментируй строку с market_type ниже.
        return db.update_live_signal_check(
            str(game_id),
            {
                "team1": info.get("team1"),
                "team2": info.get("team2"),
                "old_s1": info.get("old_s1"),
                "old_s2": info.get("old_s2"),
                "date_str": info.get("date_str"),
                "signal_ts": info.get("signal_ts"),
                "message_id": info.get("message_id"),
                "base_text": info.get("base_text"),
                "check_after": info.get("check_after"),
                "attempts": info.get("attempts", 0),
                "market_type": info.get("market_type"), # <-- Сохраняем в БД
            },
        )
    except Exception as e:
        print(
            f"❌ Не удалось сохранить проверку {game_id}: {e}",
            flush=True,
        )
        return False


def _schedule_retry(key, info, now, delay=None):
    """Планирует следующую попытку проверки результата."""
    try:
        info["attempts"] = int(info.get("attempts", 0)) + 1
    except (TypeError, ValueError):
        info["attempts"] = 1

    if delay is None:
        delay = CHECK_REPEAT_AFTER

    if info["attempts"] >= CHECK_MAX_ATTEMPTS:
        delay = max(int(delay), 3600)

    info["check_after"] = now + max(1, int(delay))
    persist_check(key, info)


# ============================================================
# РЕДАКТИРОВАНИЕ И ПОВТОРНОЕ ОБНОВЛЕНИЕ TELEGRAM
# ============================================================

def _build_result_line(row):
    """Создаёт строку результата для завершённого сигнала из БД."""
    status = str(row.get("status") or "")
    final_score = str(row.get("final_score") or "—")

    old_s1 = row.get("old_s1")
    old_s2 = row.get("old_s2")
    minute = row.get("minute") or 0

    if status == "WIN":
        signal_ts = int(
            row.get("signal_ts")
            or row.get("sent_at")
            or time.time()
        )
        result_ts = int(
            row.get("result_updated_at")
            or time.time()
        )
        elapsed = max(0, (result_ts - signal_ts) // 60)

        return (
            "✅ <b>ЗАШЛО</b>\n"
            f"📊 Было: {old_s1 if old_s1 is not None else 0}-"
            f"{old_s2 if old_s2 is not None else 0} "
            f"({minute}')\n"
            f"📊 Стало: {final_score}\n"
            f"⏱ ~{elapsed} мин"
        )

    return (
        "❌ <b>НЕ ЗАШЛО</b>\n"
        f"📊 Итог: {final_score}\n"
        "ℹ️ После сигнала новых голов не было."
    )


def _edit_completed_signal(game_id, row, result_text=None):
    """
    Пытается обновить сообщение Telegram.
    При успехе отмечает сообщение в БД; при ошибке планирует повтор.
    """
    message_id = row.get("message_id")
    base_text = row.get("base_text")

    if not message_id or not base_text:
        print(
            f"⚠️ Telegram: у сигнала {game_id} нет message_id "
            "или исходного текста. Повторить редактирование нельзя.",
            flush=True,
        )
        return False

    if not result_text:
        result_text = row.get("telegram_result_text")

    if not result_text:
        result_text = format_with_result(
            base_text,
            _build_result_line(row),
        )

        try:
            db.save_live_telegram_result(game_id, result_text)
        except Exception as e:
            print(
                f"⚠️ Не удалось сохранить текст результата {game_id}: {e}",
                flush=True,
            )

    try:
        edited = edit_telegram(
            message_id,
            result_text,
        )
    except Exception as e:
        print(
            f"❌ Ошибка редактирования Telegram для {game_id}: {e}",
            flush=True,
        )
        edited = False

    if edited:
        try:
            db.mark_live_telegram_updated(game_id)
        except Exception as e:
            print(
                f"⚠️ Сообщение {game_id} изменено, "
                f"но статус обновления не сохранён: {e}",
                flush=True,
            )
            try:
                db.schedule_live_telegram_retry(game_id, 60)
            except Exception:
                pass

        return True

    try:
        attempts = int(row.get("telegram_edit_attempts") or 0)
    except (TypeError, ValueError):
        attempts = 0

    # Увеличиваем интервал при многократных ошибках, чтобы
    # не отправлять запросы в Telegram слишком часто.
    retry_delay = min(60 * (2 ** min(attempts, 4)), 900)

    try:
        db.schedule_live_telegram_retry(
            game_id,
            delay=retry_delay,
        )
    except Exception as e:
        print(
            f"❌ Не удалось запланировать повтор Telegram {game_id}: {e}",
            flush=True,
        )

    print(
        f"🔁 Telegram: обновление сигнала {game_id} не удалось. "
        f"Повтор через {retry_delay} сек.",
        flush=True,
    )

    return False


def retry_pending_telegram_updates():
    """
    Повторно редактирует сообщения завершённых сигналов,
    если предыдущая попытка Telegram не удалась.
    Вызывать из основного цикла main.py.
    """
    try:
        rows = db.get_live_telegram_pending()
    except Exception as e:
        print(
            f"❌ Не удалось получить очередь обновлений Telegram: {e}",
            flush=True,
        )
        return

    if not rows:
        return

    print(
        f"🔁 Очередь Telegram: сообщений для обновления — {len(rows)}",
        flush=True,
    )

    for row in rows:
        game_id = str(row.get("game_id") or "").strip()

        if not game_id:
            continue

        try:
            result_text = row.get("telegram_result_text") or ""

            if not result_text:
                result_text = format_with_result(
                    row.get("base_text") or "",
                    _build_result_line(row),
                )

                db.save_live_telegram_result(
                    game_id,
                    result_text,
                )

            _edit_completed_signal(
                game_id,
                row,
                result_text=result_text,
            )

        except Exception as e:
            print(
                f"❌ Ошибка повторного обновления Telegram "
                f"для сигнала {game_id}: {e}",
                flush=True,
            )

            try:
                db.schedule_live_telegram_retry(
                    game_id,
                    delay=300,
                )
            except Exception as db_error:
                print(
                    f"❌ Не удалось запланировать повтор "
                    f"для {game_id}: {db_error}",
                    flush=True,
                )


# ============================================================
# ФИКСАЦИЯ РЕЗУЛЬТАТА
# ============================================================

def _finish_signal(key, info, won, score1, score2, now):
    """Сохраняет результат в БД и обновляет сообщение Telegram."""
    final_score = f"{score1}-{score2}"

    if won:
        elapsed = max(
            0,
            (now - int(info.get("signal_ts") or now)) // 60,
        )

        result_line = (
            "✅ <b>ЗАШЛО</b>\n"
            f"📊 Было: {info.get('old_s1', 0)}-"
            f"{info.get('old_s2', 0)} "
            f"({info.get('minute', 0)}')\n"
            f"📊 Стало: {final_score}\n"
            f"⏱ ~{elapsed} мин"
        )

        outcome = "hit"
        label = "ЗАШЛО"

    else:
        result_line = (
            "❌ <b>НЕ ЗАШЛО</b>\n"
            f"📊 Итог: {final_score}\n"
            "ℹ️ После сигнала новых голов не было."
        )

        outcome = "miss"
        label = "НЕ ЗАШЛО"

    try:
        saved = db.update_live_result(
            str(key),
            bool(won),
            final_score=final_score,
        )
    except Exception as e:
        print(f"❌ Ошибка записи результата в БД: {e}", flush=True)
        saved = False

    if not saved:
        print(
            f"❌ База не подтвердила результат: "
            f"{info.get('match')} ({key}); повторим проверку",
            flush=True,
        )
        _schedule_retry(key, info, now)
        return False

    # После подтверждения исхода обновляем обучающую выборку.
    try:
        labeled = ml.sync_confirmed_results()

        if labeled:
            print(
                f"🧠 OLD ML: размечено новых результатов: {labeled}",
                flush=True,
            )
    except Exception as e:
        print(
            f"⚠️ OLD ML: ошибка синхронизации результатов: {e}",
            flush=True,
        )

    # Формируем и сохраняем готовый текст до попытки редактирования.
    # Если Telegram недоступен, текст останется в БД для повтора.
    result_text = format_with_result(
        info.get("base_text") or "",
        result_line,
    )

    try:
        db.save_live_telegram_result(str(key), result_text)
    except Exception as e:
        print(
            f"⚠️ Не удалось сохранить текст результата {key}: {e}",
            flush=True,
        )

    try:
        row = {
            "game_id": str(key),
            "status": "WIN" if won else "LOSE",
            "final_score": final_score,
            "old_s1": info.get("old_s1", 0),
            "old_s2": info.get("old_s2", 0),
            "minute": info.get("minute", 0),
            "signal_ts": info.get("signal_ts"),
            "sent_at": info.get("signal_ts"),
            "result_updated_at": now,
            "message_id": info.get("message_id"),
            "base_text": info.get("base_text"),
            "telegram_result_text": result_text,
            "telegram_edit_attempts": 0,
        }

        if info.get("message_id") and info.get("base_text"):
            _edit_completed_signal(
                str(key),
                row,
                result_text=result_text,
            )
        else:
            print(
                f"ℹ️ Сигнал {key}: нет message_id или base_text; "
                "результат сохранён в базе, отредактировать сообщение нельзя",
                flush=True,
            )

    except Exception as e:
        print(
            f"⚠️ Результат сохранён, но обновление Telegram "
            f"не выполнено для {key}: {e}",
            flush=True,
        )

        try:
            db.schedule_live_telegram_retry(str(key), delay=60)
        except Exception:
            pass

    log_result_record({
        "record_type": "result",
        "game_id": str(key),
        "timestamp": now,
        "match": info.get("match"),
        "strategy": info.get("strategy"),
        "odd": info.get("odd"),
        "outcome": outcome,
        "final_score": final_score,
    })

    print(
        f"{'✅' if won else '❌'} {label}: "
        f"{info.get('match')} | итог {final_score}",
        flush=True,
    )

    return True


# ============================================================
# ВСПОМОГАТЕЛЬНАЯ ПРОВЕРКА СЧЁТА
# ============================================================

def _check_market_win(market_type, score1, score2, old_s1, old_s2):
    """
    Проверяет, зашел ли сигнал, в зависимости от типа рынка.
    """
    if score1 is None or score2 is None:
        return False

    try:
        s1 = int(score1)
        s2 = int(score2)
        o1 = int(old_s1)
        o2 = int(old_s2)
    except (TypeError, ValueError):
        return False

    if market_type == "individual_home":
        # Для ИТ Хозяев ждем гол именно от хозяев
        return s1 > o1
        
    elif market_type == "individual_away":
        # Для ИТ Гостей ждем гол именно от гостей
        return s2 > o2
        
    else:
        # Старая логика (следующий гол от любой команды)
        return s1 > o1 or s2 > o2


def _get_dates_to_check(info, now):
    """Возвращает дату сигнала и соседние даты."""
    dates = []
    primary_date = info.get("date_str")

    if primary_date:
        dates.append(str(primary_date))

    try:
        signal_ts = int(info.get("signal_ts") or now)
        signal_date = datetime.fromtimestamp(
            signal_ts,
            MOSCOW_TZ,
        ).date()

        for offset in (0, -1, 1):
            candidate = (
                signal_date + timedelta(days=offset)
            ).strftime("%Y-%m-%d")

            if candidate not in dates:
                dates.append(candidate)

    except Exception:
        pass

    if not dates:
        dates.append(
            datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")
        )

    return dates


# ============================================================
# ОСНОВНАЯ ПРОВЕРКА РЕЗУЛЬТАТОВ
# ============================================================

def check_pending_results(pending_checks):
    if not pending_checks:
        return

    now = int(time.time())
    due_keys = []

    for key, info in list(pending_checks.items()):
        try:
            check_after = int(info.get("check_after") or 0)
        except (TypeError, ValueError):
            check_after = 0

        if now >= check_after:
            due_keys.append(str(key))

    if not due_keys:
        return

    print(
        f"🔍 Проверка результатов: ожидают {len(due_keys)} матч(ей)",
        flush=True,
    )

    live_games = fetch_1xlite_live_games()

    for key in due_keys:
        info = pending_checks.get(key)

        if not info:
            continue

        match_name = info.get("match") or key
        market_type = info.get("market_type") # <-- Берем тип рынка

        try:
            old_s1 = int(info["old_s1"])
            old_s2 = int(info["old_s2"])
        except (KeyError, TypeError, ValueError):
            print(
                f"⚠️ {match_name}: нет корректного исходного счёта",
                flush=True,
            )
            _schedule_retry(key, info, now)
            continue

        score1 = score2 = None
        finished = False
        live_game = find_1xlite_game(live_games, key)

        # ----------------------------------------------------
        # 1. LIVE-ЛЕНТА 1XLITE
        # ----------------------------------------------------

        if live_game is not None:
            score1, score2 = parse_1xlite_score(live_game)
            finished = is_1xlite_finished(live_game)

            print(
                f"📡 1xLite live: {match_name} | "
                f"счёт={score1}-{score2} | "
                f"завершён={finished}",
                flush=True,
            )

            # Используем новую умную проверку
            if _check_market_win(market_type, score1, score2, old_s1, old_s2):
                if _finish_signal(
                    key, info, True, score1, score2, now
                ):
                    pending_checks.pop(key, None)
                continue

            if (
                score1 is not None
                and score2 is not None
                and finished
            ):
                if _finish_signal(
                    key, info, False, score1, score2, now
                ):
                    pending_checks.pop(key, None)
                continue

        # ----------------------------------------------------
        # 2. ОТДЕЛЬНЫЙ ЗАПРОС МАТЧА ПО ID
        # ----------------------------------------------------

        if (
            live_game is None
            or score1 is None
            or score2 is None
            or not finished
        ):
            print(
                f"🔎 GetGameZip: запрашиваем матч ID={key} "
                f"({match_name})",
                flush=True,
            )

            detailed_game = fetch_1xlite_game_by_id(key)

            if detailed_game is not None:
                detail_s1, detail_s2 = parse_1xlite_score(
                    detailed_game
                )
                detail_finished = is_1xlite_finished(
                    detailed_game
                )

                sc = detailed_game.get("SC") or {}
                raw_status = (
                    sc.get("I")
                    if isinstance(sc, dict)
                    else None
                )

                print(
                    f"📡 1xLite GetGameZip: {match_name} | "
                    f"счёт={detail_s1}-{detail_s2} | "
                    f"завершён={detail_finished} | "
                    f"SC.I={raw_status!r}",
                    flush=True,
                )

                if detail_s1 is not None and detail_s2 is not None:
                    score1, score2 = detail_s1, detail_s2
                    finished = detail_finished

                    # Используем новую умную проверку
                    if _check_market_win(market_type, score1, score2, old_s1, old_s2):
                        if _finish_signal(
                            key, info, True, score1, score2, now
                        ):
                            pending_checks.pop(key, None)
                        continue

                    if finished:
                        if _finish_signal(
                            key, info, False, score1, score2, now
                        ):
                            pending_checks.pop(key, None)
                        continue

        # ----------------------------------------------------
        # 3. RUSCORE — РЕЗЕРВНЫЙ ИСТОЧНИК
        # ----------------------------------------------------

        team1 = str(info.get("team1") or "").strip()
        team2 = str(info.get("team2") or "").strip()

        if team1 and team2:
            event = None

            for date_str in _get_dates_to_check(info, now):
                try:
                    events = fetch_ruscore_events(date_str)
                except Exception as e:
                    print(
                        f"⚠️ Ruscore: ошибка загрузки событий "
                        f"на {date_str}: {e}",
                        flush=True,
                    )
                    continue

                if not events:
                    continue

                event = find_match(events, team1, team2)

                if event:
                    info["date_str"] = date_str
                    break

            if event is None:
                print(
                    f"🔁 {match_name}: матч не найден в Ruscore; "
                    "повторим позже",
                    flush=True,
                )
                _schedule_retry(key, info, now)
                continue

            ruscore_status = get_ruscore_status(event)
            print(
                f"📡 Ruscore: {match_name} | "
                f"статус={ruscore_status!r}",
                flush=True,
            )

            try:
                r_s1, r_s2 = parse_score_for_match(event)
            except Exception as e:
                print(
                    f"⚠️ Ruscore: не удалось разобрать счёт "
                    f"для {match_name}: {e}",
                    flush=True,
                )
                r_s1, r_s2 = None, None

            if r_s1 is not None and r_s2 is not None:
                score1, score2 = r_s1, r_s2

                print(
                    f"📡 Ruscore: счёт={score1}-{score2}",
                    flush=True,
                )

                # Умная проверка по типу рынка
                if _check_market_win(
                    market_type, score1, score2, old_s1, old_s2
                ):
                    if _finish_signal(
                        key, info, True, score1, score2, now
                    ):
                        pending_checks.pop(key, None)
                    continue

                # Если счёт не изменился, но матч завершён — фиксируем «не зашло»
                if is_finished_status(ruscore_status):
                    if _finish_signal(
                        key, info, False, score1, score2, now
                    ):
                        pending_checks.pop(key, None)
                    continue

                # Данных достаточно, но результата пока нет — повторим позже
                _schedule_retry(key, info, now)
                continue

            else:
                print(
                    f"⚠️ Ruscore: счёт не распознан для {match_name}",
                    flush=True,
                )

                # Если статус явно говорит «завершён», но счёта нет —
                # не можем корректно закрыть сигнал, повторим позже
                _schedule_retry(key, info, now)
                continue

        # ----------------------------------------------------
        # 4. НЕДОСТАТОЧНО ДАННЫХ
        # ----------------------------------------------------

        print(
            f"⚠️ {match_name}: недостаточно данных для проверки "
            "(нет 1xLite и Ruscore); повторим позже",
            flush=True,
        )
        _schedule_retry(key, info, now)

from config import *
from telegram_bot import send_telegram, edit_telegram, format_with_result
from stats_parser import *
from ruscore import fetch_ruscore_events, find_match, parse_score_for_match
import database as db
import goal_model as ml


# ============================================================
# ЖУРНАЛ РЕЗУЛЬТАТОВ
# ============================================================

def log_result_record(record):
    try:
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        print(f"⚠️ Не удалось записать {RESULTS_FILE}: {e}", flush=True)


# ============================================================
# ПОЛУЧЕНИЕ РЕЗУЛЬТАТОВ ИЗ 1XLITE
# ============================================================

def fetch_1xlite_live_games():
    """Получает текущую live-ленту для проверки сигналов."""
    url = f"{BASE_URL}/service-api/main-live-feed/v3/games1x2"

    params = {
        "cfView": 3,
        "count": 40,
        "fcountry": 1,
        "gr": 2336,
        "grMode": 4,
        "lng": "ru",
        "ref": 1,
    }

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            print(
                f"⚠️ 1xLite live: HTTP {response.status_code}",
                flush=True,
            )
            return None

        data = response.json()

        if isinstance(data, list):
            return [g for g in data if isinstance(g, dict)]

        if isinstance(data, dict):
            for field in (
                "Value", "value", "games", "Games", "events", "Events"
            ):
                value = data.get(field)
                if isinstance(value, list):
                    return [g for g in value if isinstance(g, dict)]

        print("⚠️ 1xLite live: неизвестный формат ответа", flush=True)
        return None

    except Exception as e:
        print(f"⚠️ Ошибка запроса live-ленты 1xLite: {e}", flush=True)
        return None


def fetch_1xlite_game_by_id(game_id):
    """Запрашивает конкретный матч по ID."""
    url = f"{BASE_URL}/service-api/LiveFeed/GetGameZip"

    params = {
        "id": str(game_id),
        "lng": "ru",
        "cfview": 0,
        "isSubGames": "true",
        "GroupEvents": "true",
        "allEventsGroupSubGames": "true",
        "countevents": 250,
        "partner": 36,
    }

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=12,
        )

        if response.status_code != 200:
            print(
                f"⚠️ GetGameZip: HTTP {response.status_code}, ID={game_id}",
                flush=True,
            )
            return None

        data = response.json()

        if not isinstance(data, dict):
            print(
                f"⚠️ GetGameZip: ответ не является объектом, ID={game_id}",
                flush=True,
            )
            return None

        game = data.get("Value")

        if isinstance(game, dict):
            game["_requested_id"] = str(game_id)
            return game

        if any(k in data for k in ("SC", "scores", "id", "ID")):
            data["_requested_id"] = str(game_id)
            return data

        print(
            f"⚠️ GetGameZip не вернул данные матча, ID={game_id}",
            flush=True,
        )
        return None

    except Exception as e:
        print(f"⚠️ Ошибка GetGameZip для ID={game_id}: {e}", flush=True)
        return None

# ============================================================
# ПОЛУЧЕНИЕ КОЭФФИЦИЕНТА НА ИНДИВИДУАЛЬНЫЙ ТОТАЛ
# ============================================================

def get_odd_individual_total(game, side="home", target=0.5):
    """
    Ищет коэффициент на Индивидуальный Тотал команды.

    side="home" — ИТ Хозяев.
    side="away" — ИТ Гостей.

    target — линия тотала (0.5, 1.5, 2.5 и т.д.).

    Поля 1xLite (GetGameZip):
        T / type      — тип события (9=общий тотал, 10=ИТ1, 11=ИТ2)
        P / parameter — линия
        C / cf        — коэффициент
    """

    if not isinstance(game, dict):
        return None

    try:
        target = float(target)
    except (TypeError, ValueError):
        target = 0.5

    if side not in ("home", "away"):
        return None

    # ИТ в 1xLite обычно находятся в группе 17 ("Тоталы").
    # На всякий случай проверяем все группы.
    groups = game.get("centralBlockEventGroups") or []

    if not isinstance(groups, list):
        return None

    for grp in groups:
        if not isinstance(grp, dict):
            continue

        event_lists = grp.get("events") or []

        if not isinstance(event_lists, list):
            continue

        for event_list in event_lists:
            if not isinstance(event_list, list):
                continue

            for item in event_list:
                if not isinstance(item, dict):
                    continue

                item_type = item.get("T", item.get("type"))
                parameter = item.get("P", item.get("parameter"))
                odd = item.get("C", item.get("cf"))

                try:
                    item_type = (
                        int(item_type)
                        if item_type is not None
                        else 0
                    )
                    parameter = float(parameter)
                    odd = float(odd)
                except (TypeError, ValueError):
                    continue

                # Проверяем нужную линию.
                if abs(parameter - target) > 0.001:
                    continue

                # Отбрасываем некорректные коэффициенты.
                if odd <= 1.0:
                    continue

                # ИТ хозяев.
                if side == "home" and item_type == 10:
                    return odd

                # ИТ гостей.
                if side == "away" and item_type == 11:
                    return odd

    return None 


def find_1xlite_game(games, game_id):
    """Ищет матч по точному ID."""
    if not games:
        return None

    target = str(game_id)

    for game in games:
        if not isinstance(game, dict):
            continue

        candidates = (
            game.get("id"),
            game.get("ID"),
            game.get("I"),
            game.get("_requested_id"),
        )

        if any(
            value is not None and str(value) == target
            for value in candidates
        ):
            return game

    return None


def _parse_score_value(value):
    """Разбирает счёт из строки или словаря."""
    if isinstance(value, str):
        match = re.search(
            r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$",
            value,
        )
        if match:
            return int(match.group(1)), int(match.group(2))

    if isinstance(value, dict):
        home = value.get("home", value.get("s1", value.get("S1")))
        away = value.get("away", value.get("s2", value.get("S2")))

        try:
            if home is not None and away is not None:
                return int(home), int(away)
        except (TypeError, ValueError):
            pass

    return None, None


def parse_1xlite_score(game):
    """Разбирает счёт из известных вариантов ответа 1xLite."""
    if not isinstance(game, dict):
        return None, None

    scores = game.get("scores") or {}

    if isinstance(scores, dict):
        for key in ("fullScore", "score", "currentScore", "result"):
            s1, s2 = _parse_score_value(scores.get(key))
            if s1 is not None and s2 is not None:
                return s1, s2

        s1, s2 = _parse_score_value(scores)
        if s1 is not None and s2 is not None:
            return s1, s2

    sc = game.get("SC") or {}

    if isinstance(sc, dict):
        fs = sc.get("FS") or {}

        if isinstance(fs, dict):
            try:
                s1 = fs.get("S1")
                s2 = fs.get("S2")

                if s1 is not None and s2 is not None:
                    return int(s1), int(s2)
            except (TypeError, ValueError):
                pass

        for key in ("FS", "S", "score", "Score"):
            s1, s2 = _parse_score_value(sc.get(key))
            if s1 is not None and s2 is not None:
                return s1, s2

    for key in ("fullScore", "score", "Score", "result"):
        s1, s2 = _parse_score_value(game.get(key))
        if s1 is not None and s2 is not None:
            return s1, s2

    return None, None


# ============================================================
# ПРОВЕРКА ЗАВЕРШЕНИЯ МАТЧА
# ============================================================

def _collect_status_text(value):
    """Собирает текстовые статусы из вложенных объектов."""
    parts = []

    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in {
                "fs", "score", "scores", "s1", "s2", "value"
            }:
                if str(key).lower() in {"s1", "s2"}:
                    continue

            if isinstance(nested, (dict, list)):
                parts.extend(_collect_status_text(nested))
            elif nested is not None and isinstance(nested, str):
                parts.append(nested)

    elif isinstance(value, list):
        for nested in value:
            parts.extend(_collect_status_text(nested))

    return parts


def is_finished_status(status):
    """Распознаёт явные текстовые признаки завершения матча."""
    if isinstance(status, dict):
        text = " ".join(_collect_status_text(status))
    else:
        text = str(status or "")

    text = text.lower().replace("ё", "е")
    text = " ".join(
        text.replace("_", " ").replace("-", " ").split()
    )

    finished_values = {
        "finished", "ended", "ft", "final", "complete", "completed",
        "full time", "match finished", "match ended",
        "завершен", "завершена", "матч завершен",
        "окончен", "окончена", "закончен", "закончена",
        "матч окончен", "матч закончен", "игра завершена",
        "завершение матча",
    }

    if text in finished_values:
        return True

    prefixes = (
        "finished ", "ended ", "completed ", "full time ",
        "match finished ", "match ended ", "завершен ",
        "завершена ", "матч завершен ", "окончен ",
        "окончена ", "закончен ", "закончена ",
    )

    return text.startswith(prefixes)


def is_1xlite_finished(game):
    """Проверяет завершение по текстовым статусам и явным флагам."""
    if not isinstance(game, dict):
        return False

    scores = game.get("scores") or {}
    sc = game.get("SC") or {}

    status_values = [
        game.get("status"),
        game.get("statusName"),
        game.get("statusText"),
        game.get("statusLine"),
        game.get("statusLineStr"),
        game.get("periodName"),
        game.get("currentPeriodName"),
    ]

    if isinstance(scores, dict):
        status_values.extend([
            scores.get("status"),
            scores.get("statusName"),
            scores.get("statusText"),
            scores.get("statusLine"),
            scores.get("statusLineStr"),
            scores.get("currentPeriodName"),
        ])

    if isinstance(sc, dict):
        status_values.extend([
            sc.get("status"),
            sc.get("statusName"),
            sc.get("statusText"),
            sc.get("periodName"),
            sc.get("currentPeriodName"),
        ])

    for value in status_values:
        if value is not None and is_finished_status(value):
            return True

    for container in (game, scores, sc):
        if not isinstance(container, dict):
            continue

        for field in ("isFinished", "finished", "isEnded", "ended"):
            value = container.get(field)

            if value is True or value == 1:
                return True

            if isinstance(value, str):
                if value.strip().lower() in (
                    "true", "yes", "finished", "ended"
                ):
                    return True

    return False


def get_ruscore_status(event):
    """Извлекает статус Ruscore из разных вариантов структуры."""
    if not isinstance(event, dict):
        return ""

    parts = []

    for key in (
        "status", "statusName", "statusText", "state",
        "period", "periodName", "matchStatus",
    ):
        value = event.get(key)

        if isinstance(value, dict):
            for subkey in ("label", "name", "text", "value", "short"):
                nested = value.get(subkey)
                if isinstance(nested, str):
                    parts.append(nested)
        elif isinstance(value, str):
            parts.append(value)

    return " ".join(parts)


# ============================================================
# ВОССТАНОВЛЕНИЕ ПРОВЕРОК ПОСЛЕ ПЕРЕЗАПУСКА
# ============================================================

def restore_pending_checks():
    """Восстанавливает ожидающие сигналы из основной БД."""
    restored = {}
    now = int(time.time())

    try:
        rows = db.get_pending_live_signals()
    except Exception as e:
        print(f"❌ Не удалось загрузить проверки из БД: {e}", flush=True)
        return restored

    for row in rows:
        key = str(row.get("game_id") or "").strip()

        if not key:
            continue

        match_name = str(row.get("match_name") or "").strip()
        team1 = str(row.get("team1") or "").strip()
        team2 = str(row.get("team2") or "").strip()

        if not team1 or not team2:
            for separator in (" — ", " – ", " - ", " vs ", " VS "):
                if separator in match_name:
                    parts = match_name.split(separator, 1)

                    if len(parts) == 2:
                        team1 = team1 or parts[0].strip()
                        team2 = team2 or parts[1].strip()
                        break

        old_s1 = row.get("old_s1")
        old_s2 = row.get("old_s2")

        if old_s1 is None or old_s2 is None:
            raw_score = str(row.get("score") or "").strip()
            match = re.search(
                r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$",
                raw_score,
            )

            if match:
                old_s1 = int(match.group(1))
                old_s2 = int(match.group(2))

        if old_s1 is None or old_s2 is None:
            print(
                f"⚠️ Сигнал {key}: исходный счёт отсутствует; "
                "автоматическая проверка невозможна",
                flush=True,
            )
            continue

        try:
            old_s1 = int(old_s1)
            old_s2 = int(old_s2)
        except (TypeError, ValueError):
            print(f"⚠️ Сигнал {key}: некорректный исходный счёт", flush=True)
            continue

        sent_at = int(row.get("sent_at") or now)
        signal_ts = int(row.get("signal_ts") or sent_at)

        date_str = row.get("date_str")

        if not date_str:
            date_str = datetime.fromtimestamp(
                signal_ts,
                MOSCOW_TZ,
            ).strftime("%Y-%m-%d")

        message_id = row.get("message_id")

        try:
            message_id = int(message_id) if message_id else None
        except (TypeError, ValueError):
            message_id = None

        try:
            attempts = int(row.get("attempts") or 0)
        except (TypeError, ValueError):
            attempts = 0

        try:
            check_after = int(row.get("check_after") or now)
        except (TypeError, ValueError):
            check_after = now

        info = {
            "team1": team1,
            "team2": team2,
            "match": match_name or (
                f"{team1} — {team2}"
                if team1 and team2
                else f"Матч {key}"
            ),
            "date_str": date_str,
            "old_s1": old_s1,
            "old_s2": old_s2,
            "minute": int(row.get("minute") or 0),
            "signal_ts": signal_ts,
            "message_id": message_id,
            "base_text": row.get("base_text") or "",
            "strategy": row.get("strategy") or "не указана",
            "odd": row.get("odds"),
            "check_after": min(check_after, now),
            "attempts": attempts,
            "market_type": row.get("market_type"),  # <-- Восстанавливаем тип рынка
        }

        restored[key] = info

        try:
            persist_check(key, info)
        except Exception as e:
            print(
                f"⚠️ Не удалось обновить данные сигнала {key}: {e}",
                flush=True,
            )

        if not team1 or not team2:
            print(
                f"⚠️ Сигнал {key}: не хватает названий команд "
                "для поиска в Ruscore",
                flush=True,
            )

    print(
        f"♻️ Восстановлено ожидающих проверок: {len(restored)}",
        flush=True,
    )

    return restored


def persist_check(game_id, info):
    try:
        # ВАЖНО: Если в базе нет колонки market_type, 
        # этот код выдаст ошибку. Добавь колонку в БД (в database.py),
        # или закомментируй строку с market_type ниже.
        return db.update_live_signal_check(
            str(game_id),
            {
                "team1": info.get("team1"),
                "team2": info.get("team2"),
                "old_s1": info.get("old_s1"),
                "old_s2": info.get("old_s2"),
                "date_str": info.get("date_str"),
                "signal_ts": info.get("signal_ts"),
                "message_id": info.get("message_id"),
                "base_text": info.get("base_text"),
                "check_after": info.get("check_after"),
                "attempts": info.get("attempts", 0),
                "market_type": info.get("market_type"), # <-- Сохраняем в БД
            },
        )
    except Exception as e:
        print(
            f"❌ Не удалось сохранить проверку {game_id}: {e}",
            flush=True,
        )
        return False


def _schedule_retry(key, info, now, delay=None):
    """Планирует следующую попытку проверки результата."""
    try:
        info["attempts"] = int(info.get("attempts", 0)) + 1
    except (TypeError, ValueError):
        info["attempts"] = 1

    if delay is None:
        delay = CHECK_REPEAT_AFTER

    if info["attempts"] >= CHECK_MAX_ATTEMPTS:
        delay = max(int(delay), 3600)

    info["check_after"] = now + max(1, int(delay))
    persist_check(key, info)


# ============================================================
# РЕДАКТИРОВАНИЕ И ПОВТОРНОЕ ОБНОВЛЕНИЕ TELEGRAM
# ============================================================

def _build_result_line(row):
    """Создаёт строку результата для завершённого сигнала из БД."""
    status = str(row.get("status") or "")
    final_score = str(row.get("final_score") or "—")

    old_s1 = row.get("old_s1")
    old_s2 = row.get("old_s2")
    minute = row.get("minute") or 0

    if status == "WIN":
        signal_ts = int(
            row.get("signal_ts")
            or row.get("sent_at")
            or time.time()
        )
        result_ts = int(
            row.get("result_updated_at")
            or time.time()
        )
        elapsed = max(0, (result_ts - signal_ts) // 60)

        return (
            "✅ <b>ЗАШЛО</b>\n"
            f"📊 Было: {old_s1 if old_s1 is not None else 0}-"
            f"{old_s2 if old_s2 is not None else 0} "
            f"({minute}')\n"
            f"📊 Стало: {final_score}\n"
            f"⏱ ~{elapsed} мин"
        )

    return (
        "❌ <b>НЕ ЗАШЛО</b>\n"
        f"📊 Итог: {final_score}\n"
        "ℹ️ После сигнала новых голов не было."
    )


def _edit_completed_signal(game_id, row, result_text=None):
    """
    Пытается обновить сообщение Telegram.
    При успехе отмечает сообщение в БД; при ошибке планирует повтор.
    """
    message_id = row.get("message_id")
    base_text = row.get("base_text")

    if not message_id or not base_text:
        print(
            f"⚠️ Telegram: у сигнала {game_id} нет message_id "
            "или исходного текста. Повторить редактирование нельзя.",
            flush=True,
        )
        return False

    if not result_text:
        result_text = row.get("telegram_result_text")

    if not result_text:
        result_text = format_with_result(
            base_text,
            _build_result_line(row),
        )

        try:
            db.save_live_telegram_result(game_id, result_text)
        except Exception as e:
            print(
                f"⚠️ Не удалось сохранить текст результата {game_id}: {e}",
                flush=True,
            )

    try:
        edited = edit_telegram(
            message_id,
            result_text,
        )
    except Exception as e:
        print(
            f"❌ Ошибка редактирования Telegram для {game_id}: {e}",
            flush=True,
        )
        edited = False

    if edited:
        try:
            db.mark_live_telegram_updated(game_id)
        except Exception as e:
            print(
                f"⚠️ Сообщение {game_id} изменено, "
                f"но статус обновления не сохранён: {e}",
                flush=True,
            )
            try:
                db.schedule_live_telegram_retry(game_id, 60)
            except Exception:
                pass

        return True

    try:
        attempts = int(row.get("telegram_edit_attempts") or 0)
    except (TypeError, ValueError):
        attempts = 0

    # Увеличиваем интервал при многократных ошибках, чтобы
    # не отправлять запросы в Telegram слишком часто.
    retry_delay = min(60 * (2 ** min(attempts, 4)), 900)

    try:
        db.schedule_live_telegram_retry(
            game_id,
            delay=retry_delay,
        )
    except Exception as e:
        print(
            f"❌ Не удалось запланировать повтор Telegram {game_id}: {e}",
            flush=True,
        )

    print(
        f"🔁 Telegram: обновление сигнала {game_id} не удалось. "
        f"Повтор через {retry_delay} сек.",
        flush=True,
    )

    return False


def retry_pending_telegram_updates():
    """
    Повторно редактирует сообщения завершённых сигналов,
    если предыдущая попытка Telegram не удалась.
    Вызывать из основного цикла main.py.
    """
    try:
        rows = db.get_live_telegram_pending()
    except Exception as e:
        print(
            f"❌ Не удалось получить очередь обновлений Telegram: {e}",
            flush=True,
        )
        return

    if not rows:
        return

    print(
        f"🔁 Очередь Telegram: сообщений для обновления — {len(rows)}",
        flush=True,
    )

    for row in rows:
        game_id = str(row.get("game_id") or "").strip()

        if not game_id:
            continue

        try:
            result_text = row.get("telegram_result_text") or ""

            if not result_text:
                result_text = format_with_result(
                    row.get("base_text") or "",
                    _build_result_line(row),
                )

                db.save_live_telegram_result(
                    game_id,
                    result_text,
                )

            _edit_completed_signal(
                game_id,
                row,
                result_text=result_text,
            )

        except Exception as e:
            print(
                f"❌ Ошибка повторного обновления Telegram "
                f"для сигнала {game_id}: {e}",
                flush=True,
            )

            try:
                db.schedule_live_telegram_retry(
                    game_id,
                    delay=300,
                )
            except Exception as db_error:
                print(
                    f"❌ Не удалось запланировать повтор "
                    f"для {game_id}: {db_error}",
                    flush=True,
                )


# ============================================================
# ФИКСАЦИЯ РЕЗУЛЬТАТА
# ============================================================

def _finish_signal(key, info, won, score1, score2, now):
    """Сохраняет результат в БД и обновляет сообщение Telegram."""
    final_score = f"{score1}-{score2}"

    if won:
        elapsed = max(
            0,
            (now - int(info.get("signal_ts") or now)) // 60,
        )

        result_line = (
            "✅ <b>ЗАШЛО</b>\n"
            f"📊 Было: {info.get('old_s1', 0)}-"
            f"{info.get('old_s2', 0)} "
            f"({info.get('minute', 0)}')\n"
            f"📊 Стало: {final_score}\n"
            f"⏱ ~{elapsed} мин"
        )

        outcome = "hit"
        label = "ЗАШЛО"

    else:
        result_line = (
            "❌ <b>НЕ ЗАШЛО</b>\n"
            f"📊 Итог: {final_score}\n"
            "ℹ️ После сигнала новых голов не было."
        )

        outcome = "miss"
        label = "НЕ ЗАШЛО"

    try:
        saved = db.update_live_result(
            str(key),
            bool(won),
            final_score=final_score,
        )
    except Exception as e:
        print(f"❌ Ошибка записи результата в БД: {e}", flush=True)
        saved = False

    if not saved:
        print(
            f"❌ База не подтвердила результат: "
            f"{info.get('match')} ({key}); повторим проверку",
            flush=True,
        )
        _schedule_retry(key, info, now)
        return False

    # После подтверждения исхода обновляем обучающую выборку.
    try:
        labeled = ml.sync_confirmed_results()

        if labeled:
            print(
                f"🧠 OLD ML: размечено новых результатов: {labeled}",
                flush=True,
            )
    except Exception as e:
        print(
            f"⚠️ OLD ML: ошибка синхронизации результатов: {e}",
            flush=True,
        )

    # Формируем и сохраняем готовый текст до попытки редактирования.
    # Если Telegram недоступен, текст останется в БД для повтора.
    result_text = format_with_result(
        info.get("base_text") or "",
        result_line,
    )

    try:
        db.save_live_telegram_result(str(key), result_text)
    except Exception as e:
        print(
            f"⚠️ Не удалось сохранить текст результата {key}: {e}",
            flush=True,
        )

    try:
        row = {
            "game_id": str(key),
            "status": "WIN" if won else "LOSE",
            "final_score": final_score,
            "old_s1": info.get("old_s1", 0),
            "old_s2": info.get("old_s2", 0),
            "minute": info.get("minute", 0),
            "signal_ts": info.get("signal_ts"),
            "sent_at": info.get("signal_ts"),
            "result_updated_at": now,
            "message_id": info.get("message_id"),
            "base_text": info.get("base_text"),
            "telegram_result_text": result_text,
            "telegram_edit_attempts": 0,
        }

        if info.get("message_id") and info.get("base_text"):
            _edit_completed_signal(
                str(key),
                row,
                result_text=result_text,
            )
        else:
            print(
                f"ℹ️ Сигнал {key}: нет message_id или base_text; "
                "результат сохранён в базе, отредактировать сообщение нельзя",
                flush=True,
            )

    except Exception as e:
        print(
            f"⚠️ Результат сохранён, но обновление Telegram "
            f"не выполнено для {key}: {e}",
            flush=True,
        )

        try:
            db.schedule_live_telegram_retry(str(key), delay=60)
        except Exception:
            pass

    log_result_record({
        "record_type": "result",
        "game_id": str(key),
        "timestamp": now,
        "match": info.get("match"),
        "strategy": info.get("strategy"),
        "odd": info.get("odd"),
        "outcome": outcome,
        "final_score": final_score,
    })

    print(
        f"{'✅' if won else '❌'} {label}: "
        f"{info.get('match')} | итог {final_score}",
        flush=True,
    )

    return True


# ============================================================
# ВСПОМОГАТЕЛЬНАЯ ПРОВЕРКА СЧЁТА
# ============================================================

def _check_market_win(market_type, score1, score2, old_s1, old_s2):
    """
    Проверяет, зашел ли сигнал, в зависимости от типа рынка.
    """
    if score1 is None or score2 is None:
        return False

    try:
        s1 = int(score1)
        s2 = int(score2)
        o1 = int(old_s1)
        o2 = int(old_s2)
    except (TypeError, ValueError):
        return False

    if market_type == "individual_home":
        # Для ИТ Хозяев ждем гол именно от хозяев
        return s1 > o1
        
    elif market_type == "individual_away":
        # Для ИТ Гостей ждем гол именно от гостей
        return s2 > o2
        
    else:
        # Старая логика (следующий гол от любой команды)
        return s1 > o1 or s2 > o2


def _get_dates_to_check(info, now):
    """Возвращает дату сигнала и соседние даты."""
    dates = []
    primary_date = info.get("date_str")

    if primary_date:
        dates.append(str(primary_date))

    try:
        signal_ts = int(info.get("signal_ts") or now)
        signal_date = datetime.fromtimestamp(
            signal_ts,
            MOSCOW_TZ,
        ).date()

        for offset in (0, -1, 1):
            candidate = (
                signal_date + timedelta(days=offset)
            ).strftime("%Y-%m-%d")

            if candidate not in dates:
                dates.append(candidate)

    except Exception:
        pass

    if not dates:
        dates.append(
            datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")
        )

    return dates


# ============================================================
# ОСНОВНАЯ ПРОВЕРКА РЕЗУЛЬТАТОВ
# ============================================================

def check_pending_results(pending_checks):
    if not pending_checks:
        return

    now = int(time.time())
    due_keys = []

    for key, info in list(pending_checks.items()):
        try:
            check_after = int(info.get("check_after") or 0)
        except (TypeError, ValueError):
            check_after = 0

        if now >= check_after:
            due_keys.append(str(key))

    if not due_keys:
        return

    print(
        f"🔍 Проверка результатов: ожидают {len(due_keys)} матч(ей)",
        flush=True,
    )

    live_games = fetch_1xlite_live_games()

    for key in due_keys:
        info = pending_checks.get(key)

        if not info:
            continue

        match_name = info.get("match") or key
        market_type = info.get("market_type") # <-- Берем тип рынка

        try:
            old_s1 = int(info["old_s1"])
            old_s2 = int(info["old_s2"])
        except (KeyError, TypeError, ValueError):
            print(
                f"⚠️ {match_name}: нет корректного исходного счёта",
                flush=True,
            )
            _schedule_retry(key, info, now)
            continue

        score1 = score2 = None
        finished = False
        live_game = find_1xlite_game(live_games, key)

        # ----------------------------------------------------
        # 1. LIVE-ЛЕНТА 1XLITE
        # ----------------------------------------------------

        if live_game is not None:
            score1, score2 = parse_1xlite_score(live_game)
            finished = is_1xlite_finished(live_game)

            print(
                f"📡 1xLite live: {match_name} | "
                f"счёт={score1}-{score2} | "
                f"завершён={finished}",
                flush=True,
            )

            # Используем новую умную проверку
            if _check_market_win(market_type, score1, score2, old_s1, old_s2):
                if _finish_signal(
                    key, info, True, score1, score2, now
                ):
                    pending_checks.pop(key, None)
                continue

            if (
                score1 is not None
                and score2 is not None
                and finished
            ):
                if _finish_signal(
                    key, info, False, score1, score2, now
                ):
                    pending_checks.pop(key, None)
                continue

        # ----------------------------------------------------
        # 2. ОТДЕЛЬНЫЙ ЗАПРОС МАТЧА ПО ID
        # ----------------------------------------------------

        if (
            live_game is None
            or score1 is None
            or score2 is None
            or not finished
        ):
            print(
                f"🔎 GetGameZip: запрашиваем матч ID={key} "
                f"({match_name})",
                flush=True,
            )

            detailed_game = fetch_1xlite_game_by_id(key)

            if detailed_game is not None:
                detail_s1, detail_s2 = parse_1xlite_score(
                    detailed_game
                )
                detail_finished = is_1xlite_finished(
                    detailed_game
                )

                sc = detailed_game.get("SC") or {}
                raw_status = (
                    sc.get("I")
                    if isinstance(sc, dict)
                    else None
                )

                print(
                    f"📡 1xLite GetGameZip: {match_name} | "
                    f"счёт={detail_s1}-{detail_s2} | "
                    f"завершён={detail_finished} | "
                    f"SC.I={raw_status!r}",
                    flush=True,
                )

                if detail_s1 is not None and detail_s2 is not None:
                    score1, score2 = detail_s1, detail_s2
                    finished = detail_finished

                    # Используем новую умную проверку
                    if _check_market_win(market_type, score1, score2, old_s1, old_s2):
                        if _finish_signal(
                            key, info, True, score1, score2, now
                        ):
                            pending_checks.pop(key, None)
                        continue

                    if finished:
                        if _finish_signal(
                            key, info, False, score1, score2, now
                        ):
                            pending_checks.pop(key, None)
                        continue

        # ----------------------------------------------------
        # 3. RUSCORE — РЕЗЕРВНЫЙ ИСТОЧНИК
        # ----------------------------------------------------

        team1 = str(info.get("team1") or "").strip()
        team2 = str(info.get("team2") or "").strip()

        if team1 and team2:
            event = None

            for date_str in _get_dates_to_check(info, now):
                try:
                    events = fetch_ruscore_events(date_str)
                except Exception as e:
                    print(
                        f"⚠️ Ruscore: ошибка загрузки событий "
                        f"на {date_str}: {e}",
                        flush=True,
                    )
                    continue

                if not events:
                    continue

                event = find_match(events, team1, team2)

                if event:
                    info["date_str"] = date_str
                    break

            if event is None:
                print(
                    f"🔁 {match_name}: матч не найден в Ruscore; "
                    "повторим позже",
                    flush=True,
                )
                _schedule_retry(key, info, now)
                continue

            ruscore_status = get_ruscore_status(event)
            print(
                f"📡 Ruscore: {match_name} | "
                f"статус={ruscore_status!r}",
                flush=True,
            )

            try:
                r_s1, r_s2 = parse_score_for_match(event)
            except Exception as e:
                print(
                    f"⚠️ Ruscore: не удалось разобрать счёт "
                    f"для {match_name}: {e}",
                    flush=True,
                )
                r_s1, r_s2 = None, None

            if r_s1 is not None and r_s2 is not None:
                score1, score2 = r_s1, r_s2

                print(
                    f"📡 Ruscore: счёт={score1}-{score2}",
                    flush=True,
                )

                # Умная проверка по типу рынка
                if _check_market_win(
                    market_type, score1, score2, old_s1, old_s2
                ):
                    if _finish_signal(
                        key, info, True, score1, score2, now
                    ):
                        pending_checks.pop(key, None)
                    continue

                # Если счёт не изменился, но матч завершён — фиксируем «не зашло»
                if is_finished_status(ruscore_status):
                    if _finish_signal(
                        key, info, False, score1, score2, now
                    ):
                        pending_checks.pop(key, None)
                    continue

                # Данных достаточно, но результата пока нет — повторим позже
                _schedule_retry(key, info, now)
                continue

            else:
                print(
                    f"⚠️ Ruscore: счёт не распознан для {match_name}",
                    flush=True,
                )

                # Если статус явно говорит «завершён», но счёта нет —
                # не можем корректно закрыть сигнал, повторим позже
                _schedule_retry(key, info, now)
                continue

        # ----------------------------------------------------
        # 4. НЕДОСТАТОЧНО ДАННЫХ
        # ----------------------------------------------------

        print(
            f"⚠️ {match_name}: недостаточно данных для проверки "
            "(нет 1xLite и Ruscore); повторим позже",
            flush=True,
        )
        _schedule_retry(key, info, now)