from flask import Flask, render_template_string
import database as db
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# Красивый HTML-шаблон прямо внутри кода
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Статистика Бота</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background: #121212; color: #fff; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: auto; }
        .stats { display: flex; gap: 20px; margin-bottom: 30px; }
        .card { background: #1e1e1e; padding: 20px; border-radius: 8px; flex: 1; text-align: center; border: 1px solid #333; }
        .card h3 { margin: 0 0 10px 0; color: #888; font-size: 14px; text-transform: uppercase; }
        .card .val { font-size: 28px; font-weight: bold; }
        .win { color: #4caf50; }
        .lose { color: #f44336; }
        .pending { color: #ffeb3b; }
        .profit-pos { color: #4caf50; }
        .profit-neg { color: #f44336; }
        table { width: 100%; border-collapse: collapse; background: #1e1e1e; border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #2a2a2a; font-weight: bold; color: #aaa; }
        tr:hover { background: #2a2a2a; }
        .chart-container { background: #1e1e1e; padding: 20px; border-radius: 8px; margin-bottom: 30px; border: 1px solid #333; height: 300px; }
    </style>
</head>
<body>
<div class="container">
    <h1>🤖 Статистика ПРЕМАТЧ-Бота</h1>
    
    <div class="stats">
        <div class="card">
            <h3>Профит (у.е.)</h3>
            <div class="val {{ 'profit-pos' if total_profit >= 0 else 'profit-neg' }}">{{ "%.2f"|format(total_profit) }}</div>
        </div>
        <div class="card">
            <h3>ROI</h3>
            <div class="val {{ 'profit-pos' if roi >= 0 else 'profit-neg' }}">{{ "%.1f"|format(roi) }}%</div>
        </div>
        <div class="card">
            <h3>Сигналов (WIN/LOSE)</h3>
            <div class="val"><span class="win">{{ wins }}</span> / <span class="lose">{{ loses }}</span></div>
        </div>
        <div class="card">
            <h3>В ожидании</h3>
            <div class="val pending">{{ pendings }}</div>
        </div>
    </div>

    <div class="chart-container">
        <canvas id="profitChart"></canvas>
    </div>

    <table>
        <thead>
            <tr>
                <th>Дата</th>
                <th>Матч</th>
                <th>Лига</th>
                <th>Кэф</th>
                <th>Счет (score)</th>
                <th>Статус</th>
                <th>Профит</th>
            </tr>
        </thead>
        <tbody>
            {% for s in signals %}
            <tr>
                <td>{{ s.sent_at | timestamp_to_date }}</td>
                <td>{{ s.match_name }}</td>
                <td>{{ s.league }}</td>
                <td>{{ "%.2f"|format(s.odds) }}</td>
                <td>{{ s.score }}/10</td>
                <td class="{{ 'win' if s.status=='WIN' else 'lose' if s.status=='LOSE' else 'pending' }}">
                    {{ s.status }}
                </td>
                <td class="{{ 'profit-pos' if s.profit > 0 else 'profit-neg' if s.profit < 0 else '' }}">
                    {{ "%+.2f"|format(s.profit) }}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<script>
    // Данные для графика из Python
    const labels = {{ chart_labels | safe }};
    const data = {{ chart_data | safe }};

    const ctx = document.getElementById('profitChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Общий профит по дням',
                data: data,
                borderColor: '#4caf50',
                backgroundColor: 'rgba(76, 175, 80, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: '#333' }, ticks: { color: '#888' } },
                x: { grid: { display: false }, ticks: { color: '#888' } }
            }
        }
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
    
    # Считаем статистику
    wins = sum(1 for s in signals if s['status'] == 'WIN')
    loses = sum(1 for s in signals if s['status'] == 'LOSE')
    pendings = sum(1 for s in signals if s['status'] == 'PENDING')
    
    total_profit = sum(s['profit'] for s in signals)
    total_bets = wins + loses
    roi = (total_profit / total_bets * 100) if total_bets > 0 else 0.0

    # Готовим данные для графика (по дням)
    daily_profit = defaultdict(float)
    for s in signals:
        if s['status'] in ['WIN', 'LOSE']:
            day = datetime.fromtimestamp(s['sent_at']).strftime('%d.%m')
            daily_profit[day] += s['profit']
    
    # Считаем накопительный итог
    chart_labels = []
    chart_data = []
    cumulative = 0
    for day in sorted(daily_profit.keys(), key=lambda d: datetime.strptime(d, '%d.%m')):
        cumulative += daily_profit[day]
        chart_labels.append(day)
        chart_data.append(round(cumulative, 2))

    return render_template_string(
        HTML_TEMPLATE,
        signals=signals,
        wins=wins,
        loses=loses,
        pendings=pendings,
        total_profit=total_profit,
        roi=roi,
        chart_labels=str(chart_labels).replace("'", '"'),
        chart_data=chart_data
    )

if __name__ == '__main__':
    db.init_db()
    # Слушаем порт 8080
    app.run(host='0.0.0.0', port=8080)
