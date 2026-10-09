# =====================================================================
# PREMATCH BOT — ГЛАВНЫЙ (nb-bet версия)
# =====================================================================
import time
import json
import requests
from datetime import datetime

from config import BOT_TOKEN, CHAT_ID, API, MIN_SCORE, CHECK_INTERVAL, HOURS_BEFORE
from nbbet_stats import get_match_data
from checklist import check_10_criteria
from onexbet import get_prematch_games, parse_prematch_game
from database import init_db, save_signal, get_stats


# =====================================================================
# TELEGRAM
# =====================================================================
def send_telegram(text):
    try:
        r = requests.post(
            API + "/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["result"]["message_id"]
        else:
            print(f"❌ TG: {r.text}", flush=True)
    except Exception as e:
        print(f"❌ TG send: {e}", flush=True)
    return None


# =====================================================================
# ФОРМАТ СИГНАЛА
# =====================================================================
def format_signal(match_data, score, reasons, home_stats, away_stats):
    start_dt = datetime.fromtimestamp(match_data["start_ts"])
    start_str = start_dt.strftime("%d.%m %H:%M")

    lines = [
        f"🎯 <b>ПРЕМАТЧ-СИГНАЛ: {score}/10</b>",
        f"🏆 {match_data['league']}",
        f"⚽ <b>{match_data['match']}</b>",
        f"🕐 Старт: {start_str} МСК",
        "",
        f"📊 <b>Статистика (nb-bet):</b>",
        f"<b>{match_data['team1']}</b>:",
        f"  xG: {home_stats.get('avg_xg', 0):.2f} | Забивает: {home_stats.get('avg_scored_home', 0):.2f} | Пропускает: {home_stats.get('avg_missed_home', 0):.2f}",
        f"  Тотал: {home_stats.get('avg_total', 0):.2f} | BTTS: {home_stats.get('btts_pct', 0)*100:.0f}% | Верх: {home_stats.get('over_pct', 0)*100:.0f}%",
        f"  Углы: {home_stats.get('corners', '—')} | ЖК: {home_stats.get('yellow_cards', '—')} | Владение: {home_stats.get('possession', '—')}%",
        f"<b>{match_data['team2']}</b>:",
        f"  xG: {away_stats.get('avg_xg', 0):.2f} | Забивает: {away_stats.get('avg_scored_away', 0):.2f} | Пропускает: {away_stats.get('avg_missed_away', 0):.2f}",
        f"  Тотал: {away_stats.get('avg_total', 0):.2f} | BTTS: {away_stats.get('btts_pct', 0)*100:.0f}% | Верх: {away_stats.get('over_pct', 0)*100:.0f}%",
        f"  Углы: {away_stats.get('corners', '—')} | ЖК: {away_stats.get('yellow_cards', '—')} | Владение: {away_stats.get('possession', '—')}%",
        "",
        f"📋 <b>ЧЕК-ЛИСТ:</b>",
    ]
    for r in reasons:
        lines.append(f"  {r}")

    lines.append("")
    lines.append(f"💰 <b>Кэф ТБ 2.5: {match_data['odd_tb25']}</b>")
    lines.append(f"💡 <b>СИГНАЛ: ТБ 2.5</b>")

    return "\n".join(lines)


# =====================================================================
# ПРОВЕРКА МАТЧА
# =====================================================================
def check_match(match_data):
    """
    Считает чек-лист для одного матча через nb-bet.
    Возвращает ВСЕГДА (score, reasons, home_stats, away_stats) или None.
    """
    nbbet_data = get_match_data(
        team1=match_data["team1"],
        team2=match_data["team2"],
    )

    if not nbbet_data:
        return None

    home_stats = nbbet_data.get("home_stats")
    away_stats = nbbet_data.get("away_stats")

    if not home_stats or not away_stats:
        return None

    score, reasons = check_10_criteria(home_stats, away_stats, match_data["odd_tb25"])

    return {
        "score": score,
        "reasons": reasons,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "nbbet_data": nbbet_data,
    }


# =====================================================================
# ГЛАВНЫЙ ЦИКЛ
# =====================================================================
def main_loop():
    print("🚀 PREMATCH BOT (nb-bet) ЗАПУЩЕН", flush=True)
    print(f"📋 MIN_SCORE: {MIN_SCORE}", flush=True)
    print(f"⏱ CHECK_INTERVAL: {CHECK_INTERVAL}с", flush=True)
    print(f"⏰ HOURS_BEFORE: {HOURS_BEFORE}ч", flush=True)

    init_db()

    # Кэш: slug матча → данные nb-bet (чтобы не дёргать API повторно)
    nbbet_cache = {}

    while True:
        try:
            now = int(time.time())
            print(f"\n🔄 Проверка: {datetime.now().strftime('%H:%M:%S')}", flush=True)

            # Получаем прематч-линию
            games = get_prematch_games()
            print(f"   📋 Матчей в линии: {len(games)}", flush=True)

            # Фильтруем: только наши лиги и ближайшие HOURS_BEFORE
            target_games = []
            for g in games:
                parsed = parse_prematch_game(g)
                if not parsed:
                    continue
                delta = parsed["start_ts"] - now
                if 0 < delta <= HOURS_BEFORE * 3600:
                    target_games.append(parsed)

            print(f"   🎯 Наших матчей (за {HOURS_BEFORE}ч): {len(target_games)}", flush=True)

            if not target_games:
                print(f"   💤 Нет матчей. Ждём {CHECK_INTERVAL}с", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue

            # Проверяем каждый матч
            for m in target_games:
                # Пропускаем плейсхолдеры
                if is_placeholder(m['team1']) or is_placeholder(m['team2']):
                    continue

                cache_key = f"{m['team1']}_{m['team2']}_{m['start_ts']}"
                if cache_key in nbbet_cache:
                    continue

                print(f"   🔍 {m['match']}...", end=" ", flush=True)

                result = check_match(m)
                nbbet_cache[cache_key] = True

                if result:
                    score = result["score"]
                    reasons = result["reasons"]

                    print(f"score={score}/10", flush=True)

                    if score >= MIN_SCORE:
                        text = format_signal(
                            m, score, reasons,
                            result["home_stats"], result["away_stats"]
                        )
                        if send_telegram(text):
                            save_signal({
                                **m,
                                "score": score,
                                "reasons": reasons,
                                "home_stats": result["home_stats"],
                                "away_stats": result["away_stats"],
                            })
                            print(f"      📤 СИГНАЛ ОТПРАВЛЕН", flush=True)
                            time.sleep(2)
                    else:
                        for r in reasons:
                            print(f"      {r}", flush=True)
                else:
                    print(f"❌ нет данных", flush=True)

                print(f"   🔍 {m['match']}...", end=" ", flush=True)

                result = check_match(m)

                # Запоминаем, что проверяли
                nbbet_cache[cache_key] = True

                if result:
                    text = format_signal(
                        m, result["score"], result["reasons"],
                        result["home_stats"], result["away_stats"]
                    )
                    if send_telegram(text):
                        save_signal({
                            **m,
                            "score": result["score"],
                            "reasons": result["reasons"],
                            "home_stats": result["home_stats"],
                            "away_stats": result["away_stats"],
                        })
                        print(f"📤 СИГНАЛ ({result['score']}/10)", flush=True)
                        time.sleep(2)
                else:
                    print(f"< {MIN_SCORE}", flush=True)

            # Чистим кэш (чтобы не рос бесконечно)
            if len(nbbet_cache) > 500:
                nbbet_cache.clear()

            # Статистика
            stats = get_stats()
            print(f"\n📊 Всего сигналов: {stats['total']} | ✅ {stats['wins']} | ❌ {stats['loses']}", flush=True)

            print(f"⏱ Следующая проверка через {CHECK_INTERVAL}с", flush=True)
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("⏹️ Остановлен", flush=True)
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}", flush=True)
            import traceback
            traceback.print_exc()
            time.sleep(60)


if __name__ == "__main__":
    main_loop()
