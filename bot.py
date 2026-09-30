# =====================================================================
# PREMATCH BOT — ГЛАВНЫЙ
# =====================================================================
import time
import json
import requests
from datetime import datetime

from config import BOT_TOKEN, CHAT_ID, API, MIN_SCORE, CHECK_INTERVAL, HOURS_BEFORE
from understat import fetch_understat, get_team_stats
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

    # Иконки для причин
    lines = [
        f"🎯 <b>ПРЕМАТЧ-СИГНАЛ: {score}/10</b>",
        f"🏆 {match_data['league']}",
        f"⚽ <b>{match_data['match']}</b>",
        f"🕐 Старт: {start_str} МСК",
        "",
        f"📊 <b>Статистика (последние 10 матчей):</b>",
        f"<b>{match_data['team1']}</b>:",
        f"  xG: {home_stats['avg_xg']:.2f} | Забивает: {home_stats['avg_scored']:.2f} | Пропускает: {home_stats['avg_missed']:.2f}",
        f"  Тотал: {home_stats['avg_total']:.2f} | BTTS: {home_stats['btts_pct']*100:.0f}% | Верх: {home_stats['over_pct']*100:.0f}%",
        f"<b>{match_data['team2']}</b>:",
        f"  xG: {away_stats['avg_xg']:.2f} | Забивает: {away_stats['avg_scored']:.2f} | Пропускает: {away_stats['avg_missed']:.2f}",
        f"  Тотал: {away_stats['avg_total']:.2f} | BTTS: {away_stats['btts_pct']*100:.0f}% | Верх: {away_stats['over_pct']*100:.0f}%",
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
def check_match(match_data, understat_data):
    """Считает чек-лист для одного матча."""
    home_stats = get_team_stats(match_data["team1"], match_data["league"], understat_data)
    away_stats = get_team_stats(match_data["team2"], match_data["league"], understat_data)

    if not home_stats or not away_stats:
        return None

    score, reasons = check_10_criteria(home_stats, away_stats, match_data["odd_tb25"])

    if score >= MIN_SCORE:
        return {
            "score": score,
            "reasons": reasons,
            "home_stats": home_stats,
            "away_stats": away_stats,
        }
    return None


# =====================================================================
# ГЛАВНЫЙ ЦИКЛ
# =====================================================================
def main_loop():
    print("🚀 PREMATCH BOT ЗАПУЩЕН", flush=True)
    print(f"📋 MIN_SCORE: {MIN_SCORE}", flush=True)
    print(f"⏱ CHECK_INTERVAL: {CHECK_INTERVAL}с", flush=True)
    print(f"⏰ HOURS_BEFORE: {HOURS_BEFORE}ч", flush=True)

    init_db()

    # Кэш Understat по лигам
    understat_cache = {}

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
                # Время до старта
                delta = parsed["start_ts"] - now
                if 0 < delta <= HOURS_BEFORE * 3600:
                    target_games.append(parsed)

            print(f"   🎯 Наших матчей (за {HOURS_BEFORE}ч): {len(target_games)}", flush=True)

            if not target_games:
                print(f"   💤 Нет матчей. Ждём {CHECK_INTERVAL}с", flush=True)
                time.sleep(CHECK_INTERVAL)
                continue

            # Группируем по лигам
            by_league = {}
            for m in target_games:
                by_league.setdefault(m["league"], []).append(m)

            # Для каждой лиги — загружаем Understat
            for league, matches in by_league.items():
                print(f"\n   🏆 {league}: {len(matches)} матчей", flush=True)

                # Кэш Understat
                if league not in understat_cache:
                    understat_cache[league] = fetch_understat(league)

                data = understat_cache[league]
                if not data:
                    print(f"      ❌ Нет данных Understat для {league}", flush=True)
                    continue

                # Проверяем каждый матч
                for m in matches:
                    result = check_match(m, data)
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
                            print(f"      📤 СИГНАЛ: {m['match']} ({result['score']}/10)", flush=True)
                            time.sleep(2)
                    else:
                        print(f"      ⏸ {m['match']}: < {MIN_SCORE}", flush=True)

            # Статистика
            stats = get_stats()
            print(f"\n📊 Всего сигналов: {stats['total']} | ✅ {stats['wins']} | ❌ {stats['loses']}", flush=True)

            # Ждём
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