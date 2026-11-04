import json
from stats_parser import parse_prematch_game

# Загружаем JSON из файла
with open("test_line.json", "r", encoding="utf-8") as f:
    games = json.load(f)

print(f"📊 Загружено матчей: {len(games)}")

# Парсим первые 5 матчей для проверки
for game in games[:5]:
    parsed = parse_prematch_game(game)
    if not parsed:
        continue
    
    print(f"\n⚽ {parsed['sport']}: {parsed['team1']} — {parsed['team2']}")
    print(f"   Лига: {parsed['liga']}")
    print(f"   Начало: {parsed['start_time']:%d.%m %H:%M}")
    print(f"   1X2: {parsed['odds']['1']} / {parsed['odds']['X']} / {parsed['odds']['2']}")
    print(f"   ОЗ: да {parsed['odds']['OZ_Yes']} / нет {parsed['odds']['OZ_No']}")
    print(f"   Тоталы (первые 5):")
    for param, vals in list(parsed['odds']['TB'].items())[:5]:
        print(f"      {param}: ТБ {vals.get('over')} / ТМ {vals.get('under')}")
