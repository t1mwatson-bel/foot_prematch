# =====================================================================
# 10-БАЛЛЬНЫЙ ЧЕК-ЛИСТ
# =====================================================================

THRESHOLDS = {
    "over_pct": 0.55,
    "pair_total": 2.70,
    "xg_sum": 2.70,
    "home_scored": 1.50,
    "away_scored": 1.20,
    "missed": 1.00,
    "btts_pct": 0.55,
    "value_odd": 1.75,
}


def check_10_criteria(home_stats, away_stats, odd_tb25):
    """Считает баллы по 10 критериям. Возвращает (score, reasons)."""
    score = 0
    reasons = []

    if not home_stats or not away_stats:
        return 0, ["❌ Нет статистики для одной из команд"]

    # Критерий 1: Частота верховых
    if home_stats["over_pct"] > THRESHOLDS["over_pct"] and away_stats["over_pct"] > THRESHOLDS["over_pct"]:
        score += 1
        reasons.append(f"✅ Частота верховых: {home_stats['over_pct']*100:.0f}% / {away_stats['over_pct']*100:.0f}%")
    else:
        reasons.append(f"❌ Частота верховых: {home_stats['over_pct']*100:.0f}% / {away_stats['over_pct']*100:.0f}%")

    # Критерий 2: Средний тотал пары
    pair_total = (home_stats["avg_total"] + away_stats["avg_total"]) / 2
    if pair_total > THRESHOLDS["pair_total"]:
        score += 1
        reasons.append(f"✅ Средний тотал пары: {pair_total:.2f}")
    else:
        reasons.append(f"❌ Средний тотал пары: {pair_total:.2f}")

    # Критерий 3: Средний xG пары
    xg_avg = (home_stats["avg_xg"] + away_stats["avg_xg"]) / 2
    if xg_avg > THRESHOLDS["xg_sum"]:
        score += 1
        reasons.append(f"✅ Средний xG пары: {xg_avg:.2f}")
    else:
        reasons.append(f"❌ Средний xG пары: {xg_avg:.2f}")

    # Критерий 4: Атака хозяев
    if home_stats["avg_scored_home"] > THRESHOLDS["home_scored"]:
        score += 1
        reasons.append(f"✅ Хозяева забивают дома: {home_stats['avg_scored_home']:.2f}")
    else:
        reasons.append(f"❌ Хозяева забивают дома: {home_stats['avg_scored_home']:.2f}")

    # Критерий 5: Атака гостей
    if away_stats["avg_scored_away"] > THRESHOLDS["away_scored"]:
        score += 1
        reasons.append(f"✅ Гости забивают на выезде: {away_stats['avg_scored_away']:.2f}")
    else:
        reasons.append(f"❌ Гости забивают на выезде: {away_stats['avg_scored_away']:.2f}")

    # Критерий 6: Оборона
    if home_stats["avg_missed_home"] > THRESHOLDS["missed"] and away_stats["avg_missed_away"] > THRESHOLDS["missed"]:
        score += 1
        reasons.append(f"✅ Обе пропускают: {home_stats['avg_missed_home']:.2f} / {away_stats['avg_missed_away']:.2f}")
    else:
        reasons.append(f"❌ Обе пропускают: {home_stats['avg_missed_home']:.2f} / {away_stats['avg_missed_away']:.2f}")

    # Критерий 7: BTTS
    if home_stats["btts_pct"] > THRESHOLDS["btts_pct"] and away_stats["btts_pct"] > THRESHOLDS["btts_pct"]:
        score += 1
        reasons.append(f"✅ BTTS: {home_stats['btts_pct']*100:.0f}% / {away_stats['btts_pct']*100:.0f}%")
    else:
        reasons.append(f"❌ BTTS: {home_stats['btts_pct']*100:.0f}% / {away_stats['btts_pct']*100:.0f}%")

    # Критерий 8: Травмы (пока нет источника)
    reasons.append("⏳ Травмы: нет источника")

    # Критерий 9: Мотивация (пока нет источника)
    reasons.append("⏳ Мотивация: нет источника")

    # Критерий 10: Value
    if odd_tb25 and odd_tb25 > THRESHOLDS["value_odd"]:
        score += 1
        reasons.append(f"✅ Value: кэф ТБ 2.5 = {odd_tb25}")
    else:
        reasons.append(f"❌ Value: кэф ТБ 2.5 = {odd_tb25}")

    return score, reasons