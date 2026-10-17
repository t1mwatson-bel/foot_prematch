# web.py
from flask import Flask, render_template_string
import database as db
from datetime import datetime
from collections import defaultdict

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
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .container { max-width: 1100px; margin: auto; }
        h1 { font-weight: 600; margin-bottom: 30px; color: #38bdf8; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; text-align: center; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .card h3 { margin: 0 0 10px 0; color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; }
        .card .val { font-size: 32px; font-weight: 700; }
        .win { color: #10b981; }
        .lose { color: #ef4444; }
        .pending { color: #f59e0b; }
        .profit-pos { color: #10b981; }
        .profit-neg { color: #ef4444; }
        .chart-container { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 30px; border: 1px solid #334155; height: 350px; }
        table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 12px; overflow: hidden; border: 1px solid #334155; }
        th, td { padding: 14px; text-align: left; border-bottom: 1px solid #334155; }
        th { background: #0f172a; font-weight: 600; color: #94a3b8; font-size: 13px; text-transform: uppercase; }
        tr:hover { background: #334155; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .badge-win { background: rgba(16, 185, 129, 0.2); color: #10b981; }
        .badge-lose { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
        .badge-pending { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
    </style>
</head>
<body>
<div class="container">
    <h1>🤖 Статистика Бота</h1>
    
    <div class="stats">
        <div class="card">
            <h3>Общий профит (у.е.)</h3>
            <div class="val {{ 'profit-pos' if total_profit >= 0 else 'profit-neg' }}">{{ "%.2f"|format(total_profit) }}</div>
        </div>
        <div class="card">
            <h3>ROI</h3>
            <div class="val {{ 'profit-pos' if roi >= 0 else 'profit-neg' }}">{{ "%.1f"|format(roi) }}%</div>
        </div>
        <div class="card">
            <h3>Зашло / Не зашло</h3>
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
                <th>Оценка</th>
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
                <td>
                    {% if s.status == 'WIN' %}
                        <span class="badge badge-win">WIN</span>
                    {% elif s.status == 'LOSE' %}
                        <span class="badge badge-lose">LOSE</span>
                    {% else %}
                        <span class="badge badge-pending">PENDING</span>
                    {% endif %}
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
    const labels = {{ chart_labels | safe }};
    const data = {{ chart_data | safe }};

    const ctx = document.getElementById('profitChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Общий профит',
                data: data,
                borderColor: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.1)',
                borderWidth: 3,
                pointBackgroundColor: '#0f172a',
                pointBorderColor: '#38bdf8',
                pointBorderWidth: 2,
                pointRadius: 4,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
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
    app.run(host='0.0.0.0', port=8080)
