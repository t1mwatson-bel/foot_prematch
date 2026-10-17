import time
import json
import requests
import threading
from datetime import datetime
from flask import Flask, render_template_string
from collections import defaultdict

from config import BOT_TOKEN, CHAT_ID, API, MIN_SCORE, CHECK_INTERVAL, HOURS_BEFORE
from nbbet_stats import get_match_data, is_placeholder
from checklist import check_10_criteria
from onexbet import get_prematch_games, parse_prematch_game
import database as db

# =====================================================================
# ВЕБ-СЕРВЕР (САЙТ)
# =====================================================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Статистика Бота</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Inter, Arial, sans-serif; background: radial-gradient(circle at top, #101828 0%, #06090f 45%, #03050a 100%); color: #fff; margin: 0; padding: 20px; min-height: 100vh; }
        .container { max-width: 1400px; margin: auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .logo { font-size: 32px; font-weight: 900; letter-spacing: 3px; text-shadow: 0 0 10px rgba(0, 255, 200, .6), 0 0 20px rgba(0, 200, 255, .5); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }
        .card { background: linear-gradient(145deg, rgba(20, 30, 50, .65), rgba(10, 15, 25, .45)); border: 1px solid rgba(0, 200, 255, .15); border-radius: 18px; padding: 22px; text-align: center; box-shadow: 0 10px 30px rgba(0, 0, 0, .45); }
        .card h3 { color: #8995a8; font-size: 13px; margin-bottom: 10px; text-transform: uppercase; }
        .val { font-size: 32px; font-weight: 800; }
        .green { color: #4cff9b; text-shadow: 0 0 12px rgba(76, 255, 155, .7); }
        .red { color: #ff5d70; text-shadow: 0 0 12px rgba(255, 93, 112, .7); }
        .blue { color: #65aaff; }
        .orange { color: #ffbd66; }
        .section { background: rgba(255, 255, 255, .03); border: 1px solid rgba(0, 200, 255, .12); border-radius: 20px; padding: 22px; margin-bottom: 25px; }
        .section-title { font-size: 20px; font-weight: 800; margin-bottom: 18px; text-shadow: 0 0 8px rgba(0, 255, 200, .5); }
        .chart-container { height: 300px; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; color: #7e8ba0; font-size: 12px; text-transform: uppercase; padding: 13px; border-bottom: 1px solid rgba(0, 200, 255, .15); }
        td { padding: 14px 13px; border-bottom: 1px solid rgba(255, 255, 255, .05); font-size: 14px; }
        tr:hover td { background: rgba(0, 200, 255, .04); }
    </style>
</head>
<body>
<div class="container">
    <div class="header"><div class="logo">🤖 ПРЕМАТЧ-БОТ</div></div>
    <div class="grid">
        <div class="card"><h3>Профит</h3><div class="val {{ 'green' if total_profit >= 0 else 'red' }}">{{ "%+.2f"|format(total_profit) }}</div></div>
        <div class="card"><h3>ROI</h3><div class="val {{ 'green' if roi >= 0 else 'red' }}">{{ "%.1f"|format(roi) }}%</div></div>
        <div class="card"><h3>Зашло / Не зашло</h3><div class="val"><span class="green">{{ wins }}</span> / <span class="red">{{ loses }}</span></div></div>
        <div class="card"><h3>В ожидании</h3><div class="val orange">{{ pendings }}</div></div>
    </div>
    <div class="section">
        <div class="section-title">📈 График профита</div>
        <div class="chart-container"><canvas id="profitChart"></canvas></div>
    </div>
    <div class="section">
        <div class="section-title">📜 Все сигналы</div>
        <table>
            <thead><tr><th>Дата</th><th>Матч</th><th>Лига</th><th>Кэф</th><th>Оценка</th><th>Статус</th><th>Профит</th></tr></thead>
            <tbody>
                {% for s in signals %}
                <tr>
                    <td>{{ s.sent_at | timestamp_to_date }}</td>
                    <td><strong>{{ s.match_name }}</strong></td>
                    <td>{{ s.league }}</td>
                    <td>{{ "%.2f"|format(s.odds) }}</td>
                    <td>{{ s.score }}/10</td>
                    <td class="{{ 'green' if s.status=='WIN' else 'red' if s.status=='LOSE' else 'orange' }}">{{ s.status }}</td>
                    <td class="{{ 'green' if s.profit>0 else 'red' if s.profit<0 else '' }}">{{ "%+.2f"|format(s.profit) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
<script>
    new Chart(document.getElementById('profitChart').getContext('2d'), {
        type: 'line',
        data: { labels: {{ chart_labels | safe }}, datasets: [{ label: 'Профит', data: {{ chart_data | safe }}, borderColor: '#00ffe0', backgroundColor: 'rgba(0, 255, 224, 0.1)', borderWidth: 3, fill: true, tension: 0.3 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { grid: { color: '#1e293b' }, ticks: { color: '#64748b' } }, x: { grid: { display: false }, ticks: { color: '#64748b' } } } }
    });
</script>
</body>
</html>
"""

@app.template_filter('timestamp_to_date')
def timestamp_to_date(ts):
    if not ts: return "-"
    return datetime.fromtimestamp(ts).strftime('%d.%m %H:%M')

@app.route('/')
def index():
    signals = db.get_all_signals()
    wins = sum(1 for s in signals if s['status'] == 'WIN')
    loses = sum(1 for s in signals if s['status'] == 'LOSE')
    pendings = sum(1 for s in signals if s['status'] == 'PENDING')
    total_profit = sum(s['profit'] for s in signals)
    total_bets = wins + loses
    roi = (total_profit / total_bets * 100) if total_bets > 0 else 0.0

    daily_profit = defaultdict(float)
    for s in signals:
        if s['status'] in ['WIN', 'LOSE']:
            day = datetime.fromtimestamp(s['sent_at']).strftime('%d.%m')
            daily_profit[day] += s['profit']
    
    chart_labels = []
    chart_data = []
    cumulative = 0
    for day in sorted(daily_profit.keys(), key=lambda d: datetime.strptime(d, '%d.%m')):
        cumulative += daily_profit[day]
        chart_labels.append(day)
        chart_data.append(round(cumulative, 2))

    return render_template_string(HTML_TEMPLATE, signals=signals, wins=wins, loses=loses, pendings=pendings, total_profit=total_profit, roi=roi, chart_labels=str(chart_labels).replace("'", '"'), chart_data=chart_data)

@app.route('/health')
@app.route('/healthcheck')
def health():
    return "OK", 200

def run_web():
    # Bothost требует порт 3000
    app.run(host='0.0.0.0', port=3000, use_reloader=False)

# =====================================================================
# БОТ ЛОГИКА
# =====================================================================
def send_telegram(text):
    try:
        r = requests.post(API + "/sendMessage", json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=15)
        if r.status_code == 200: return r.json()["result"]["message_id"]
    except Exception as e: print(f"❌ TG send: {e}", flush=True)
    return None

def format_signal(match_data, score, reasons, home_stats, away_stats):
    start_str = datetime.fromtimestamp(match_data["start_ts"]).strftime("%d.%m %H:%M")
    lines = [
        f"🎯 <b>ПРЕМАТЧ-СИГНАЛ: {score}/10</b>",
        f"🏆 {match_data['league']}",
        f"⚽ <b>{match_data['match']}</b>",
        f"🕐 Старт: {start_str} МСК", "",
        f"📊 <b>Статистика:</b>",
        f"<b>{match_data['team1']}</b>: xG {home_stats.get('avg_xg', 0):.2f} | Забивает {home_stats.get('avg_scored_home', 0):.2f} | Пропускает {home_stats.get('avg_missed_home', 0):.2f}",
        f"<b>{match_data['team2']}</b>: xG {away_stats.get('avg_xg', 0):.2f} | Забивает {away_stats.get('avg_scored_away', 0):.2f} | Пропускает {away_stats.get('avg_missed_away', 0):.2f}",
        "", f"📋 <b>ЧЕК-ЛИСТ:</b>"
    ]
    for r in reasons: lines.append(f"  {r}")
    lines.append("")
    lines.append(f"💰 <b>Кэф ТБ 2.5: {match_data['odd_tb25']}</b>")
    lines.append(f"💡 <b>СИГНАЛ: ТБ 2.5</b>")
    return "\\n".join(lines)

def check_match(match_data):
    nbbet_data = get_match_data(team1=match_data["team1"], team2=match_data["team2"])
    if not nbbet_data: return None
    home_stats, away_stats = nbbet_data.get("home_stats"), nbbet_data.get("away_stats")
    if not home_stats or not away_stats: return None
    score, reasons = check_10_criteria(home_stats, away_stats, match_data["odd_tb25"], nbbet_data)
    return {"score": score, "reasons": reasons, "home_stats": home_stats, "away_stats": away_stats, "nbbet_data": nbbet_data}

def bot_loop():
    print("🚀 БОТ ЗАПУЩЕН", flush=True)
    db.init_db()
    nbbet_cache = {}
    while True:
        try:
            now = int(time.time())
            print(f"\\n🔄 Проверка: {datetime.now().strftime('%H:%M:%S')}", flush=True)
            games = get_prematch_games()
            target_games = []
            for g in games:
                parsed = parse_prematch_game(g)
                if parsed and 0 < parsed["start_ts"] - now <= HOURS_BEFORE * 3600:
                    target_games.append(parsed)

            for m in target_games:
                if is_placeholder(m['team1']) or is_placeholder(m['team2']): continue
                cache_key = f"{m['team1']}_{m['team2']}_{m['start_ts']}"
                if cache_key in nbbet_cache: continue

                print(f"   🔍 {m['match']}...", end=" ", flush=True)
                result = check_match(m)
                if not result:
                    print(f"❌ нет данных", flush=True); time.sleep(1); continue

                score = result["score"]
                print(f"score={score}/10", flush=True)

                if score >= MIN_SCORE:
                    text = format_signal(m, score, result["reasons"], result["home_stats"], result["away_stats"])
                    if send_telegram(text):
                        db.save_signal({**m, "match_slug": result["nbbet_data"].get("match_slug"), "score": score, "reasons": result["reasons"], "home_stats": result["home_stats"], "away_stats": result["away_stats"]})
                        print(f"      📤 СИГНАЛ ОТПРАВЛЕН", flush=True)
                        nbbet_cache[cache_key] = True
                        time.sleep(2)
                else:
                    for r in result["reasons"]: print(f"      {r}", flush=True)
                    nbbet_cache[cache_key] = True
                time.sleep(1)

            if len(nbbet_cache) > 500: nbbet_cache.clear()
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"❌ Ошибка: {e}", flush=True)
            time.sleep(60)

if __name__ == "__main__":
    # Запускаем сайт в фоне на порту 3000
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Запускаем бота
    bot_loop()
