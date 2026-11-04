import json
import re
import os

def extract_avg_goals(preview_text, team_name, is_home=None):
    """
    is_home=True — берём первую пару (хозяева),
    is_home=False — вторую (гости).
    """
    if not preview_text or not team_name:
        return None, None

    clean = re.sub(r"<[^>]+>", "", preview_text).replace(",", ".")
    pattern = r"забивает\s+([\d.]+)\s*(?:гола\s+за\s+игру)?\s*[,.]?\s*пропускает\s+([\d.]+)"
    matches = re.findall(pattern, clean)

    if not matches:
        return None, None

    def clean_num(s):
        s = s.rstrip("., ")
        try:
            return float(s)
        except ValueError:
            return None

    if is_home is True:
        return clean_num(matches[0][0]), clean_num(matches[0][1])
    if is_home is False and len(matches) >= 2:
        return clean_num(matches[1][0]), clean_num(matches[1][1])

    return clean_num(matches[0][0]), clean_num(matches[0][1])


def parse_nb_bet_html(file_path="match_page.html"):
    print(f"📂 Парсер: файл {file_path} существует: {os.path.exists(file_path)}", flush=True)
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL
    )
    if not match:
        print(f"❌ Не найден тег __NEXT_DATA__", flush=True)
        return None

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка JSON: {e}", flush=True)
        return None

    try:
        match_data = data["props"]["initialState"]["pageSoccerEvent"]["match"]
    except KeyError as e:
        print(f"❌ Не найден pageSoccerEvent.match: {e}", flush=True)
        return None

    team1 = match_data.get("7", {}).get("1", "?")
    team2 = match_data.get("8", {}).get("1", "?")
    print(f"📄 DEBUG: team1='{team1}', team2='{team2}'", flush=True)

    odds_1x2 = match_data.get("5", {})
    coef_1 = odds_1x2.get("1")
    coef_x = odds_1x2.get("2")
    coef_2 = odds_1x2.get("3")
    coef_tb_2_5 = odds_1x2.get("15")
    coef_tm_2_5 = odds_1x2.get("16")

    preview_text = match_data.get("27", {}).get("1", "")

    avg_scored_home, avg_conceded_home = extract_avg_goals(preview_text, team1, is_home=True)
    avg_scored_away, avg_conceded_away = extract_avg_goals(preview_text, team2, is_home=False)

    print(f"✅ Голы хозяев: забивает={avg_scored_home}, пропускает={avg_conceded_home}", flush=True)
    print(f"✅ Голы гостей: забивает={avg_scored_away}, пропускает={avg_conceded_away}", flush=True)

    return {
        "team1": team1,
        "team2": team2,
        "coef_1": coef_1,
        "coef_x": coef_x,
        "coef_2": coef_2,
        "coef_tb_2_5": coef_tb_2_5,
        "coef_tm_2_5": coef_tm_2_5,
        "avg_scored_home": avg_scored_home,
        "avg_conceded_home": avg_conceded_home,
        "avg_scored_away": avg_scored_away,
        "avg_conceded_away": avg_conceded_away,
        "preview_text": preview_text,
    }
