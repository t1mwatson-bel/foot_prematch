# =====================================================================
# ТЕСТОВЫЙ ЗАПУСК
# =====================================================================
from understat import fetch_understat, get_team_stats
from checklist import check_10_criteria

# Тест: Боруссия — Вердер (Бундеслига)
HOME = "Боруссия"
AWAY = "Вердер"
LEAGUE = "Бундеслига"
ODD_TB25 = 1.35  # пример кэфа

print("=" * 60)
print(f"🔍 ТЕСТ: {HOME} — {AWAY} ({LEAGUE})")
print("=" * 60)

# Получаем данные Understat
data = fetch_understat(LEAGUE)
if not data:
    print("❌ Не удалось получить данные Understat")
    exit(1)

# Получаем статистику команд
home_stats = get_team_stats(HOME, LEAGUE, data)
away_stats = get_team_stats(AWAY, LEAGUE, data)

if not home_stats:
    print(f"❌ Команда '{HOME}' не найдена в Understat")
    exit(1)
if not away_stats:
    print(f"❌ Команда '{AWAY}' не найдена в Understat")
    exit(1)

# Выводим статистику
print(f"\n📊 {HOME} (Understat: {home_stats['team']}):")
for k, v in home_stats.items():
    print(f"   {k}: {v}")

print(f"\n📊 {AWAY} (Understat: {away_stats['team']}):")
for k, v in away_stats.items():
    print(f"   {k}: {v}")

# Считаем чек-лист
score, reasons = check_10_criteria(home_stats, away_stats, ODD_TB25)

print(f"\n{'=' * 60}")
print(f"📋 ЧЕК-ЛИСТ: {score}/10")
print(f"{'=' * 60}")
for r in reasons:
    print(f"  {r}")

if score >= 8:
    print(f"\n🎯 СИГНАЛ: ТБ 2.5 (кэф {ODD_TB25})")
else:
    print(f"\n⏸️ Пропуск (нужно >= 8 баллов)")