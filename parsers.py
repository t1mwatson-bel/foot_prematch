import re
from datetime import datetime

from config import (
    MOSCOW_TZ,
    GAME_CYCLE,
    ENABLE_LAST_10,
)


# =====================================================================
# SUITS
# =====================================================================

SUITS = {
    "\u2660": "\u2660\ufe0f",  # ♠
    "\u2663": "\u2663\ufe0f",  # ♣
    "\u2666": "\u2666\ufe0f",  # ♦
    "\u2665": "\u2665\ufe0f",  # ♥
}

# Зеркальные масти: ♥️ <-> ♣️, ♦️ <-> ♠️
MIRROR_SUITS = {
    "\u2665\ufe0f": "\u2663\ufe0f",  # ♥ -> ♣
    "\u2663\ufe0f": "\u2665\ufe0f",  # ♣ -> ♥
    "\u2666\ufe0f": "\u2660\ufe0f",  # ♦ -> ♠
    "\u2660\ufe0f": "\u2666\ufe0f",  # ♠ -> ♦
}


def normalize_suit(suit):
    if suit is None:
        return None

    suit = str(suit).strip()
    suit = suit.replace("\ufe0f", "")

    return SUITS.get(suit)


def mirror_suit(suit):
    """Меняет масть на зеркальную: ♥️->♣️, ♦️->♠️ и наоборот."""
    if not suit:
        return suit
    normalized = normalize_suit(suit)
    if not normalized:
        return suit
    return MIRROR_SUITS.get(normalized, normalized)


def normalize_rank(rank):
    if rank is None:
        return None

    rank = str(rank).strip().upper()

    if rank == "А":
        rank = "A"

    if rank in {
        "6", "7", "8", "9", "10",
        "J", "Q", "K", "A",
    }:
        return rank

    return None


def card_to_text(card):
    if not card:
        return ""

    rank = normalize_rank(card.get("rank"))
    suit = normalize_suit(card.get("suit"))

    if not rank or not suit:
        return ""

    return f"{rank}{suit}"


def cards_to_text(cards):
    result = []

    for card in cards:
        value = card_to_text(card)
        if value:
            result.append(value)

    return " ".join(result)


# =====================================================================
# CYBER 21 SCORE
# =====================================================================

CARD_VALUES = {
    "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 2, "Q": 3, "K": 4, "A": 11,
}


def cyber21_score(cards):
    total = 0

    for card in cards:
        rank = normalize_rank(card.get("rank"))
        if rank in CARD_VALUES:
            total += CARD_VALUES[rank]

    return total


# =====================================================================
# PARSE CARDS
# =====================================================================

CARD_RE = re.compile(
    r"(10|[6-9AJQK])\s*"
    r"(\u2660|\u2663|\u2666|\u2665)"
    r"\ufe0f?"
)


def parse_cards(text):
    result = []

    if not text:
        return result

    for match in CARD_RE.finditer(text):
        rank = normalize_rank(match.group(1))
        suit = normalize_suit(match.group(2))

        if not rank or not suit:
            continue

        result.append({
            "rank": rank,
            "suit": suit,
        })

    return result


# =====================================================================
# PARSE GAME MESSAGE
# =====================================================================

def parse_game_message(text):
    if not text:
        return None

    number_match = re.search(r"#N(\d+)", text)
    if not number_match:
        return None

    game_number = int(number_match.group(1))

    groups = re.findall(r"\(([^()]*)\)", text)
    if len(groups) < 2:
        return None

    player_text = groups[0]
    dealer_text = groups[1]

    player_cards = parse_cards(player_text)
    dealer_cards = parse_cards(dealer_text)

    if not player_cards:
        return None

    player_score = cyber21_score(player_cards)
    dealer_score = cyber21_score(dealer_cards)

    id_match = re.search(r"ID:\s*(\d+)", text)
    game_id = id_match.group(1) if id_match else None

    is_draw = bool(re.search(r"#X\b", text))
    is_ochko = bool(re.search(r"#O\b", text))
    is_r = bool(re.search(r"#R\b", text))
    is_g = bool(re.search(r"#G\b", text))
    is_finished = bool(re.search(r"✅", text))

    return {
        "game_number": game_number,
        "game_id": game_id,
        "player_cards": player_cards,
        "dealer_cards": dealer_cards,
        "player_score": player_score,
        "dealer_score": dealer_score,
        "is_draw": is_draw,
        "is_ochko": is_ochko,
        "is_r": is_r,
        "is_g": is_g,
        "is_finished": is_finished,
        "raw_text": text,
    }


# =====================================================================
# ANOMALY CHECK
# =====================================================================

def has_anomaly(game):
    """True, если в игре есть любой из флагов #R / #O / #X / #G."""
    if not game:
        return True
    return bool(
        game.get("is_r") or
        game.get("is_ochko") or
        game.get("is_draw") or
        game.get("is_g")
    )


# =====================================================================
# LOG GAME
# =====================================================================

def log_game(game):
    player = game.get("player_cards", [])
    dealer = game.get("dealer_cards", [])

    print("", flush=True)
    print("────────────────────────────────────", flush=True)
    print(f"🔒 ИГРА ЗАФИКСИРОВАНА #N{game['game_number']}", flush=True)
    print(f"👤 P: {game['player_score']} ({cards_to_text(player)})", flush=True)
    print(f"🎰 D: {game['dealer_score']} ({cards_to_text(dealer)})", flush=True)

    if game.get("is_draw"):
        print("🔰 #X — НИЧЬЯ", flush=True)

    if game.get("is_ochko"):
        print("⭕ #O — ОЧКО", flush=True)

    if game.get("is_r"):
        print("⚠️ #R — АНОМАЛИЯ", flush=True)

    if game.get("is_g"):
        print("🎯 #G — ФЛАГ G", flush=True)

    print("────────────────────────────────────", flush=True)


# =====================================================================
# GAME NUMBER (cycle)
# =====================================================================

def add_game_offset(number, offset, cycle):
    return ((int(number) - 1 + int(offset)) % cycle) + 1


# =====================================================================
# ALGORITHM: ПОСЛЕДНЯЯ 10 → ДИЛЕР
# =====================================================================

def get_last_card_prediction(game, cycle, games_cache=None):
    """
    Триггер по игроку (последняя карта = 10), прогноз на дилера.

    Доп. фильтры:
      - ни в триггере, ни за 1 игру до, ни за 1 игру после
        нет #R / #O / #X / #G;
      - у дилера есть карты в игре ДО и ПОСЛЕ триггера.
    """
    player = game.get("player_cards", [])
    dealer = game.get("dealer_cards", [])

    if not player:
        return None

    # 1. У дилера должно быть 0 карт в триггере
    if dealer:
        return None

    # 2. Нет очка в триггере
    if game.get("is_ochko"):
        return None

    # 3. Последняя карта игрока должна быть 10
    last_card = player[-1]
    last_rank = normalize_rank(last_card.get("rank"))

    if last_rank != "10":
        return None

    # 4. Ровно ОДНА 10 у игрока
    tens_count = sum(
        1 for card in player
        if normalize_rank(card.get("rank")) == "10"
    )

    if tens_count > 1:
        print(f"⚠️ #N{game['game_number']}: >1 десятки — пропуск", flush=True)
        return None

    # 5. У игрока минимум 3 карты
    if len(player) < 3:
        print(f"⚠️ #N{game['game_number']}: у игрока <3 карт — пропуск", flush=True)
        return None

    # 6. Игра завершена
    if "✅" not in game.get("raw_text", ""):
        return None

    # -----------------------------------------------------------------
    # 7. ПРОВЕРКИ ДО / ПОСЛЕ ТРИГГЕРА
    # -----------------------------------------------------------------
    if games_cache is not None:
        prev_number = add_game_offset(game["game_number"], -1, cycle)
        next_number = add_game_offset(game["game_number"], +1, cycle)

        prev_game = games_cache.get(prev_number)
        next_game = games_cache.get(next_number)

        # 7.1. Сама игра-триггер не должна содержать аномалий
        if has_anomaly(game):
            print(
                f"⚠️ #N{game['game_number']}: аномалия в триггере — пропуск",
                flush=True,
            )
            return None

        # 7.2. Игра ДО: должна быть в кэше, без аномалий,
        #      и у дилера должны быть карты
        if prev_game is None:
            print(
                f"⚠️ #N{game['game_number']}: игра до (#N{prev_number}) не в кэше — пропуск",
                flush=True,
            )
            return None

        if has_anomaly(prev_game):
            print(
                f"⚠️ #N{game['game_number']}: аномалия в игре до (#N{prev_number}) — пропуск",
                flush=True,
            )
            return None

        if not prev_game.get("dealer_cards"):
            print(
                f"⚠️ #N{game['game_number']}: у дилера нет карт в игре до (#N{prev_number}) — пропуск",
                flush=True,
            )
            return None

        # 7.3. Игра ПОСЛЕ: те же проверки
        if next_game is None:
            print(
                f"⚠️ #N{game['game_number']}: игра после (#N{next_number}) не в кэше — пропуск",
                flush=True,
            )
            return None

        if has_anomaly(next_game):
            print(
                f"⚠️ #N{game['game_number']}: аномалия в игре после (#N{next_number}) — пропуск",
                flush=True,
            )
            return None

        if not next_game.get("dealer_cards"):
            print(
                f"⚠️ #N{game['game_number']}: у дилера нет карт в игре после (#N{next_number}) — пропуск",
                flush=True,
            )
            return None

    # -----------------------------------------------------------------
    # 8. Зеркальная масть
    # -----------------------------------------------------------------
    raw_suit = normalize_suit(last_card.get("suit"))
    if not raw_suit:
        return None

    predicted_suit = mirror_suit(raw_suit)

    target_offset = len(player)
    target_number = add_game_offset(game["game_number"], target_offset, cycle)

    return {
        "algorithm": "последняя 10 → дилер",
        "trigger_number": game["game_number"],
        "trigger_game_id": game.get("game_id"),
        "target_number": target_number,
        "predicted_suit": predicted_suit,
        "predicted_for": "dealer",
        "trigger_player": [card_to_text(c) for c in player],
        "trigger_dealer": [card_to_text(c) for c in dealer],
        "trigger_player_score": game["player_score"],
        "trigger_dealer_score": game["dealer_score"],
        "status": "pending",
        "created_at": datetime.now(MOSCOW_TZ).isoformat(),
        "result_game": None,
        "found_card": None,
        "dogon": None,
        "message_id": None,
        "sent": False,
        "target_offset": target_offset,
    }


# =====================================================================
# ОБЩАЯ ФУНКЦИЯ ЗАПУСКА АЛГОРИТМОВ
# =====================================================================

def get_algorithm_predictions(game, cycle, games_cache=None):
    predictions = []

    if ENABLE_LAST_10:
        p1 = get_last_card_prediction(game, cycle, games_cache)
        if p1:
            predictions.append(p1)

    return predictions


# =====================================================================
# CHECK DEALER SUIT (проверка результата по ДИЛЕРУ)
# =====================================================================

def check_prediction_suit(game, predicted_suit):
    """
    Проверяем масть в картах ДИЛЕРА, а не игрока.
    predicted_suit уже должен быть в зеркальном формате.
    """
    dealer_cards = game.get("dealer_cards", [])
    target = normalize_suit(predicted_suit)

    for card in dealer_cards:
        suit = normalize_suit(card.get("suit"))

        if suit == target:
            return card_to_text(card)

    return None