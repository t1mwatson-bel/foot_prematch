import os
from datetime import datetime
from collections import Counter, defaultdict

from config import (
    MOSCOW_TZ,
    STATS_HTML_FILE,
    START_BALANCE,
    LOGO_URL,
    BOT_LINK,
    BRAND_NAME,
)

import bank as bank_module


def generate_html_for_algorithm(algorithm, predictions, bank_state, file_name):
    """Генерирует HTML-страницу для конкретного алгоритма."""

    # Алиасы названия алгоритма (старое + новое + промежуточное)
    BAS_ALIASES = {"Bas_v2.0", "последняя 10", "последняя 10 → дилер"}

    algo_predictions = [
        p for p in predictions
        if p.get("algorithm") == algorithm
        or (algorithm == "Bas_v2.0" and p.get("algorithm") in BAS_ALIASES)
    ]

    total = len(algo_predictions)
    win = sum(1 for p in algo_predictions if p.get("status") == "win")
    lose = sum(1 for p in algo_predictions if p.get("status") == "lose")
    pending = sum(1 for p in algo_predictions if p.get("status") == "pending")
    expired = sum(1 for p in algo_predictions if p.get("status") == "expired")

    decided = win + lose
    winrate = round(win / decided * 100, 1) if decided else 0.0

    balance = bank_state.get("balance", START_BALANCE)
    start_balance = bank_state.get("start_balance", START_BALANCE)
    profit = balance - start_balance

    total_staked = sum(
        p.get("bet_amount", 0) for p in algo_predictions
        if p.get("status") in ("win", "lose")
    )
    roi = round(profit / total_staked * 100, 1) if total_staked else 0.0

    current_bet = bank_state.get("current_bet", 0)
    current_step = bank_state.get("step", 0)

    # Догоны
    dogons = Counter()
    dogons_win = Counter()
    for p in algo_predictions:
        if p.get("status") in ("win", "lose"):
            d = p.get("dogon")
            if d is not None:
                dogons[d] += 1
                if p.get("status") == "win":
                    dogons_win[d] += 1

    # Масти
    suits = Counter()
    suits_win = Counter()
    for p in algo_predictions:
        s = p.get("predicted_suit")
        if s:
            suits[s] += 1
            if p.get("status") == "win":
                suits_win[s] += 1

    # Динамика по дням
    daily_balance = {}
    history = bank_state.get("history", [])
    for entry in history:
        time_str = entry.get("time", "")
        if len(time_str) >= 10:
            day = time_str[:10]
            daily_balance[day] = entry.get("balance_after", 0)

    days = defaultdict(lambda: {"win": 0, "lose": 0})
    for p in algo_predictions:
        if p.get("status") not in ("win", "lose"):
            continue
        created = p.get("created_at") or ""
        day = created[:10] if len(created) >= 10 else "?"
        days[day][p["status"]] += 1

    rows = []
    for p in algo_predictions[-30:][::-1]:
        status = p.get("status", "?")
        mark = {"win": "✅", "lose": "❌", "pending": "⏳",
                "expired": "🗑️"}.get(status, "?")
        target = p.get("target_number", "?")
        suit = p.get("predicted_suit", "").replace("\ufe0f", "")
        dogon = p.get("dogon")
        dogon_str = f"Д{dogon}" if dogon is not None else ""

        bets = p.get("bets") or [p.get("bet_amount", 0)]
        dogon_idx = p.get("dogon") or 0
        bet = bets[dogon_idx] if dogon_idx < len(bets) else bets[-1]

        created = (p.get("created_at") or "")[:16].replace("T", " ")
        rows.append(
            f"<tr><td>{mark}</td><td>#N{target}</td><td>{suit}</td>"
            f"<td>{bet:.0f} ₽</td><td>{dogon_str}</td>"
            f"<td>{status}</td><td>{created}</td></tr>"
        )
    rows_html = "\n".join(rows) or '<tr><td colspan="7">Нет данных</td></tr>'

    dogon_rows = ""
    for d in sorted(dogons.keys()):
        played = dogons[d]
        won = dogons_win.get(d, 0)
        wr = round(won / played * 100, 1) if played else 0
        dogon_rows += (
            f"<tr><td>Д{d}</td><td>{played}</td>"
            f"<td>{won}</td><td>{wr}%</td></tr>"
        )

    suit_rows = ""
    for s, cnt in suits.items():
        won = suits_win.get(s, 0)
        wr = round(won / cnt * 100, 1) if cnt else 0
        s_clean = s.replace("\ufe0f", "")
        suit_rows += (
            f"<tr><td>{s_clean}</td><td>{cnt}</td>"
            f"<td>{won}</td><td>{wr}%</td></tr>"
        )

    day_rows = ""
    for day in sorted(set(list(days.keys()) + list(daily_balance.keys())), reverse=True)[:30]:
        d = days.get(day, {"win": 0, "lose": 0})
        w, l = d["win"], d["lose"]
        total_d = w + l
        wr = round(w / total_d * 100, 1) if total_d else 0
        day_bal = daily_balance.get(day, "-")
        bal_str = f"{day_bal:.0f} ₽" if isinstance(day_bal, (int, float)) else day_bal
        day_rows += (
            f"<tr><td>{day}</td><td>{total_d}</td>"
            f"<td>{w}</td><td>{l}</td><td>{wr}%</td><td>{bal_str}</td></tr>"
        )

    updated = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    profit_class = "win" if profit >= 0 else "lose"

    # ... дальше HTML без изменений (тот же, что у тебя) ...