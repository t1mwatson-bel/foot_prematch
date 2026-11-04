from datetime import datetime

def parse_prematch_game(game):
    """
    Парсит один матч из линии 1xBet.
    Возвращает словарь с командами, временем и коэффициентами.
    """
    try:
        # 1. Основная инфа
        team1 = game["opponent1"]["fullName"]
        team2 = game["opponent2"]["fullName"]
        start_ts = game["startTs"]
        game_id = game["id"]
        liga = game.get("liga", {}).get("name", "Неизвестная лига")
        sport = game.get("sport", {}).get("name", "Футбол")

        # 2. Коэффициенты
        odds = {
            "1": None, "X": None, "2": None,
            "TB": {},   # словарь тоталов: {2.5: {'over': 1.8, 'under': 2.0}, ...}
            "OZ_Yes": None, "OZ_No": None,
            "ITB1": {}, "ITB2": {}  # индивидуальные тоталы
        }

        # 3. Парсим eventGroups (там исходы и ОЗ)
        for group in game.get("eventGroups", []):
            for event_list in group.get("events", []):
                for ev in event_list:
                    ev_type = ev.get("type")
                    cf = ev.get("cf")
                    param = ev.get("parameter")
                    
                    if ev_type == 1: odds["1"] = cf
                    elif ev_type == 2: odds["X"] = cf
                    elif ev_type == 3: odds["2"] = cf
                    elif ev_type == 180: odds["OZ_Yes"] = cf
                    elif ev_type == 181: odds["OZ_No"] = cf
                    # Индивидуальные тоталы
                    elif ev_type == 11 and param is not None:
                        odds["ITB1"].setdefault(param, {})["over"] = cf
                    elif ev_type == 12 and param is not None:
                        odds["ITB1"].setdefault(param, {})["under"] = cf
                    elif ev_type == 13 and param is not None:
                        odds["ITB2"].setdefault(param, {})["over"] = cf
                    elif ev_type == 14 and param is not None:
                        odds["ITB2"].setdefault(param, {})["under"] = cf

        # 4. Парсим centralBlockEventGroups (там полные тоталы)
        for group in game.get("centralBlockEventGroups", []):
            if group.get("groupId") != 17:  # 17 = Тоталы
                continue
            for event_list in group.get("events", []):
                for ev in event_list:
                    ev_type = ev.get("type")
                    cf = ev.get("cf")
                    param = ev.get("parameter")
                    
                    if param is None: continue
                    
                    if ev_type == 9:  # ТБ
                        odds["TB"].setdefault(param, {})["over"] = cf
                    elif ev_type == 10:  # ТМ
                        odds["TB"].setdefault(param, {})["under"] = cf

        return {
            "game_id": game_id,
            "team1": team1,
            "team2": team2,
            "liga": liga,
            "sport": sport,
            "start_time": datetime.fromtimestamp(start_ts),
            "start_ts": start_ts,
            "odds": odds,
            "raw": game,  # на всякий случай
        }
    except Exception as e:
        print(f"⚠️ Ошибка парсинга: {e}", flush=True)
        return None
