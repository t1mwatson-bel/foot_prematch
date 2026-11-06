# -*- coding: utf-8 -*-

import json
from datetime import datetime

from flask import Flask, render_template_string, jsonify

import database as db
import model_stats


app = Flask(__name__)


# ============================================================
# HTML + CSS (С НОВОГОДНИМ НАСТРОЕНИЕМ)
# ============================================================

HTML_TEMPLATE = r"""
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>❄️ OLD — Live Statistics 🎄</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
:root {
  color-scheme: dark;
  --bg:#050b19; --panel:rgba(10,23,45,.91);
  --border:rgba(117,164,226,.34); --text:#eef5ff;
  --muted:#a6b8d4; --green:#41e6a1; --red:#ff6b81;
  --blue:#6dc5ff; --yellow:#ffd36b; --gold:#ffc65c; --snow:#ffffff;
}
*{box-sizing:border-box}
html{min-height:100%}
body{
  margin:0;min-height:100vh;color:var(--text);
  font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
  background:
    radial-gradient(ellipse at 50% 0%,rgba(40,83,145,.55),transparent 45%),
    radial-gradient(ellipse at 0% 45%,rgba(16,73,126,.32),transparent 40%),
    radial-gradient(ellipse at 100% 65%,rgba(111,53,21,.22),transparent 35%),
    linear-gradient(180deg,#071329 0%,#050b19 55%,#09152a 100%);
  background-attachment:fixed;overflow-x:hidden;
}

/* --- НОВОГОДНИЙ СНЕГ --- */
.snow {
  position: fixed;
  top: -50px;
  left: 0;
  width: 100%;
  height: 100vh;
  pointer-events: none;
  z-index: 5;
  background-image: 
    radial-gradient(4px 4px at 10% 10%, #fff 50%, transparent 100%),
    radial-gradient(3px 3px at 20% 40%, #fff 50%, transparent 100%),
    radial-gradient(5px 5px at 30% 70%, #fff 50%, transparent 100%),
    radial-gradient(2px 2px at 40% 20%, #fff 50%, transparent 100%),
    radial-gradient(4px 4px at 50% 80%, #fff 50%, transparent 100%),
    radial-gradient(3px 3px at 60% 30%, #fff 50%, transparent 100%),
    radial-gradient(5px 5px at 70% 60%, #fff 50%, transparent 100%),
    radial-gradient(2px 2px at 80% 10%, #fff 50%, transparent 100%),
    radial-gradient(4px 4px at 90% 90%, #fff 50%, transparent 100%);
  background-size: 200px 200px;
  animation: snowfall 8s linear infinite;
  opacity: 0.6;
}
@keyframes snowfall {
  0% { background-position: 0px 0px, 0px 0px, 0px 0px, 0px 0px, 0px 0px, 0px 0px, 0px 0px, 0px 0px, 0px 0px; }
  100% { background-position: 0px 200px, 0px 200px, 0px 200px, 0px 200px, 0px 200px, 0px 200px, 0px 200px, 0px 200px, 0px 200px; }
}

/* --- ГИРЛЯНДА --- */
.garland {
  position: fixed; top: 0; left: 0; width: 100%; height: 10px;
  display: flex; justify-content: space-between; z-index: 100;
}
.garland span {
  width: 8px; height: 12px; border-radius: 50%;
  animation: blink 1.5s infinite alternate;
}
.garland span:nth-child(odd) { animation-delay: 0.5s; background: #ff4b4b; box-shadow: 0 0 10px #ff4b4b; }
.garland span:nth-child(even) { animation-delay: 1s; background: #4bff4b; box-shadow: 0 0 10px #4bff4b; }
.garland span:nth-child(3n) { background: #4b4bff; box-shadow: 0 0 10px #4b4bff; animation-delay: 0.2s; }
.garland span:nth-child(4n) { background: #ffff4b; box-shadow: 0 0 10px #ffff4b; animation-delay: 0.8s; }
@keyframes blink { from { opacity: 0.3; } to { opacity: 1; } }

.decor{
  position:fixed;z-index:1;pointer-events:none;font-size:clamp(34px,5vw,70px);
  opacity:.45;filter:drop-shadow(0 0 12px rgba(255,190,70,.4));
}
.decor-left{left:8px;top:160px}.decor-right{right:8px;top:280px}
.decor-bottom-left{left:12px;bottom:18px}.decor-bottom-right{right:12px;bottom:18px}
.wrap{position:relative;z-index:2;width:min(1250px,94%);margin:0 auto;padding:28px 0 50px}
header{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:24px}

.logo{font-size:clamp(25px,4vw,36px);font-weight:900;letter-spacing:2px;text-shadow:0 0 25px rgba(92,170,255,.3)}
.logo span{color:var(--blue)}
.sub,.updated{color:var(--muted);font-size:13px;margin-top:5px}
.updated{font-size:12px}
.cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-bottom:18px}
.card,.panel{
  background:linear-gradient(145deg,rgba(20,43,74,.95),rgba(7,17,35,.96));
  border:1px solid var(--border);border-radius:16px;
  box-shadow:0 12px 40px rgba(0,0,0,.38),inset 0 1px 0 rgba(255,255,255,.035);
}
.card{padding:18px;min-width:0}
.card .label{color:var(--muted);font-size:12px;margin-bottom:10px}
.card .value{font-size:clamp(20px,2.5vw,29px);font-weight:800;overflow-wrap:anywhere}
.green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}.yellow{color:var(--yellow)}
.panel{padding:20px;margin-bottom:18px;backdrop-filter:blur(12px)}
.panel h2{margin:0 0 16px;font-size:17px}
.chart-wrap{height:260px}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:760px}
th,td{padding:13px 12px;border-bottom:1px solid var(--border);text-align:left;font-size:13px;vertical-align:top}
th{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.6px}
tr:last-child td{border-bottom:0}
.match{font-weight:700;min-width:190px}
.small{color:var(--muted);font-size:11px;margin-top:5px}
.pill{display:inline-block;padding:5px 9px;border-radius:20px;font-size:11px;font-weight:800;white-space:nowrap}
.pill-WIN{color:var(--green);background:#41e6a118}
.pill-LOSE{color:var(--red);background:#ff6b8118}
.pill-PENDING{color:var(--yellow);background:#ffd36b18}
.empty{text-align:center;padding:32px;color:var(--muted)}
footer{text-align:center;color:var(--muted);font-size:12px;padding-top:8px}

/* OLD PREMATCH MODELS */
.models-section{
  border-color:rgba(255,198,92,.45);
  background:radial-gradient(ellipse at 50% 0%,rgba(255,198,92,.12),transparent 65%),
             linear-gradient(145deg,rgba(20,35,58,.97),rgba(5,15,31,.97));
}
.models-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:20px}
.model-card{background:rgba(4,14,30,.75);border:1px solid rgba(255,198,92,.28);border-radius:15px;padding:17px;min-width:0}
.model-title{font-size:17px;font-weight:900;margin-bottom:15px;color:var(--gold)}
.model-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.model-metric{background:rgba(255,255,255,.035);border-radius:10px;padding:11px}
.model-metric-label{color:var(--muted);font-size:11px;margin-bottom:6px}
.model-metric-value{font-size:21px;font-weight:900;overflow-wrap:anywhere}
.model-name{color:var(--gold);font-weight:800}
.model-table{min-width:950px}

@media(max-width:850px){
  .cards{grid-template-columns:repeat(2,minmax(0,1fr))}
  .card:last-child{grid-column:span 2}
  .panel{padding:14px}
  .models-grid{grid-template-columns:1fr}
  .decor{opacity:.2}
}
@media(max-width:420px){
  .wrap{width:94%;padding-top:18px}
  .card{padding:13px}
}
</style>
</head>

<body>
<!-- НОВОГОДНЯЯ ГИРЛЯНДА -->
<div class="garland">
  <span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span>
</div>

<!-- ПАДАЮЩИЙ СНЕГ -->
<div class="snow"></div>

<div class="decor decor-left">🎄</div>
<div class="decor decor-right">🎄</div>
<div class="decor decor-bottom-left">🎁</div>
<div class="decor decor-bottom-right">🎁</div>

<div class="wrap">
<header>
  <div>
    <div class="logo">❄️ <span>OLD</span> LIVE STATS 🎅</div>
    <div class="sub">Статистика прогнозов на следующий гол до конца матча</div>
  </div>
  <div class="updated">Обновлено: {{ updated }}</div>
</header>

<section class="cards">
  <div class="card"><div class="label">🎯 Всего прогнозов</div><div class="value">{{ total }}</div></div>
  <div class="card"><div class="label">✅ Зашло</div><div class="value green">{{ wins }}</div></div>
  <div class="card"><div class="label">❌ Не зашло</div><div class="value red">{{ loses }}</div></div>
  <div class="card"><div class="label">⏳ Ожидают результата</div><div class="value yellow">{{ pending }}</div></div>
  <div class="card"><div class="label">📈 Проходимость</div><div class="value blue">{{ accuracy }}%</div><div class="small">Только завершённые прогнозы</div></div>
</section>

<section class="cards">
  <div class="card" style="grid-column:span 2">
    <div class="label">💰 Общая прибыль, условные единицы</div>
    <div class="value {{ 'green' if profit >= 0 else 'red' }}">{{ '%+.2f'|format(profit) }}</div>
  </div>
  <div class="card" style="grid-column:span 3">
    <div class="label">📊 ROI по завершённым прогнозам</div>
    <div class="value {{ 'green' if roi >= 0 else 'red' }}">{{ '%+.2f'|format(roi) }}%</div>
    <div class="small">Расчёт по единичной ставке на каждый завершённый сигнал</div>
  </div>
</section>

<!-- OLD PREMATCH MODELS -->
<section class="panel models-section">
  <h2>🧠 OLD PREMATCH MODELS 🎁</h2>
  <div class="small">Раздельная статистика двух независимых прематч-моделей</div>

  <div class="models-grid">
    {% for model_name in ["OLD CHECKLIST 10", "OLD GOALS MODEL"] %}
      {% set st = model_stats_data.get(model_name, {}) %}
      <div class="model-card">
        <div class="model-title">{{ model_name }}</div>
        <div class="model-metrics">
          <div class="model-metric"><div class="model-metric-label">Всего прогнозов</div><div class="model-metric-value">{{ st.get("total", 0) }}</div></div>
          <div class="model-metric"><div class="model-metric-label">Проходимость</div><div class="model-metric-value blue">{{ st.get("accuracy", 0) }}%</div></div>
          <div class="model-metric"><div class="model-metric-label">Зашло</div><div class="model-metric-value green">{{ st.get("wins", 0) }}</div></div>
          <div class="model-metric"><div class="model-metric-label">Не зашло</div><div class="model-metric-value red">{{ st.get("loses", 0) }}</div></div>
          <div class="model-metric"><div class="model-metric-label">Ожидают</div><div class="model-metric-value yellow">{{ st.get("pending", 0) }}</div></div>
          <div class="model-metric"><div class="model-metric-label">Средний коэффициент</div><div class="model-metric-value">{{ "%.2f"|format(st.get("average_odds", 0)|float) }}</div></div>
          <div class="model-metric"><div class="model-metric-label">Прибыль</div><div class="model-metric-value {{ 'green' if st.get('profit', 0)|float >= 0 else 'red' }}">{{ "%+.2f"|format(st.get("profit", 0)|float) }}</div></div>
          <div class="model-metric"><div class="model-metric-label">ROI</div><div class="model-metric-value {{ 'green' if st.get('roi', 0)|float >= 0 else 'red' }}">{{ "%+.2f"|format(st.get("roi", 0)|float) }}%</div></div>
        </div>
      </div>
    {% endfor %}
  </div>

  <h2>📊 Сравнение моделей</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Модель</th><th>Всего</th><th>WIN</th><th>LOSE</th><th>Ожидание</th><th>Проходимость</th><th>Прибыль</th><th>ROI</th></tr></thead>
      <tbody>
      {% for model_name in ["OLD CHECKLIST 10", "OLD GOALS MODEL"] %}
        {% set st = model_stats_data.get(model_name, {}) %}
        <tr>
          <td class="model-name">{{ model_name }}</td>
          <td>{{ st.get("total", 0) }}</td>
          <td class="green">{{ st.get("wins", 0) }}</td>
          <td class="red">{{ st.get("loses", 0) }}</td>
          <td class="yellow">{{ st.get("pending", 0) }}</td>
          <td>{{ st.get("accuracy", 0) }}%</td>
          <td>{{ "%+.2f"|format(st.get("profit", 0)|float) }}</td>
          <td>{{ "%+.2f"|format(st.get("roi", 0)|float) }}%</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</section>

<section class="panel">
  <h2>🔮 История прематч-прогнозов</h2>
  <div class="table-wrap">
    <table class="model-table">
      <thead><tr><th>Время</th><th>Модель</th><th>Матч</th><th>Лига</th><th>Коэффициент</th><th>Вероятность</th><th>Прогноз</th><th>Итоговый счёт</th><th>Результат</th><th>Прибыль</th></tr></thead>
      <tbody>
      {% for p in model_predictions %}
        {% set pred = p.get("prediction", {}) %}
        <tr>
          <td>{{ p.created_at_text }}</td>
          <td class="model-name">{{ p.model_name }}</td>
          <td class="match">{{ p.team1 }} — {{ p.team2 }}</td>
          <td>{{ p.league or "—" }}</td>
          <td>{{ "%.2f"|format(p.odds_over|float) if p.odds_over else "—" }}</td>
          <td>{% if pred is mapping and pred.get("probability") is not none %}{{ "%.1f"|format(pred.get("probability")|float) }}%{% else %}—{% endif %}</td>
          <td>{% if pred is mapping %}{{ pred.get("score", pred.get("recommendation", "ТБ 2.5")) }}{% else %}ТБ 2.5{% endif %}</td>
          <td>{{ p.final_score or "—" }}</td>
          <td><span class="pill pill-{{ p.outcome }}">{% if p.outcome == "WIN" %}ЗАШЛО{% elif p.outcome == "LOSE" %}НЕ ЗАШЛО{% else %}ОЖИДАНИЕ{% endif %}</span></td>
          <td class="{{ 'green' if p.profit|float > 0 else ('red' if p.profit|float < 0 else '') }}">{{ "%+.2f"|format(p.profit|float) }}</td>
        </tr>
      {% else %}
        <tr><td colspan="10" class="empty">Пока нет прематч-прогнозов</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</section>

<section class="panel">
  <h2>📈 Накопленная прибыль</h2>
  <div class="chart-wrap"><canvas id="profitChart"></canvas></div>
</section>

<section class="panel">
  <h2>📋 История лайв-прогнозов</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Время</th><th>Матч</th><th>Лига</th><th>Стратегия</th><th>Счёт при сигнале</th><th>Коэффициент</th><th>Результат</th><th>Прибыль</th></tr></thead>
      <tbody>
      {% for s in signals %}
        <tr>
          <td>{{ s.sent_at_text }}<div class="small">{{ s.minute or 0 }}'</div></td>
          <td class="match">{{ s.match_name or 'Матч не указан' }}{% if s.final_score %}<div class="small">Итог: {{ s.final_score }}</div>{% endif %}</td>
          <td>{{ s.league or '—' }}</td><td>{{ s.strategy or '—' }}</td><td>{{ s.score or '—' }}</td>
          <td>{{ '%.2f'|format(s.odds|float) if s.odds is not none else '—' }}</td>
          <td><span class="pill pill-{{ s.status }}">{{ status_labels.get(s.status, s.status) }}</span></td>
          <td class="{{ 'green' if s.profit|float > 0 else ('red' if s.profit|float < 0 else '') }}">{{ '%+.2f'|format(s.profit|float) }}</td>
        </tr>
      {% else %}
        <tr><td colspan="8" class="empty">Пока нет записанных лайв-прогнозов</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</section>

<footer>OLD · Статистика рассчитывается по данным SQLite · ❄️ С Наступающим Новым Годом! 🎄</footer>
</div>

<script>
const labels = {{ chart_labels|safe }};
const values = {{ chart_data|safe }};
new Chart(document.getElementById('profitChart'), {
  type:'line',
  data:{labels,datasets:[{
    label:'Накопленная прибыль',data:values,
    borderColor:'#6dc5ff',backgroundColor:'rgba(109,197,255,0.13)',
    fill:true,tension:.25,pointRadius:3,pointBackgroundColor:'#fff'
  }]},
  options:{
    responsive:true,maintainAspectRatio:false,
    plugins:{legend:{labels:{color:'#eef5ff'}}},
    scales:{
      x:{ticks:{color:'#a6b8d4'},grid:{color:'#253b59'}},
      y:{ticks:{color:'#a6b8d4'},grid:{color:'#253b59'}}
    }
  }
});
</script>
</body>
</html>
"""


# ============================================================
# ГЛАВНАЯ СТРАНИЦА
# ============================================================

@app.route("/")
def index():
    all_rows = db.get_live_signals()

    signals = [
        row for row in all_rows
        if row.get("game_id") and row.get("match_name")
    ]

    wins = sum(1 for row in signals if row.get("status") == "WIN")
    loses = sum(1 for row in signals if row.get("status") == "LOSE")
    pending = sum(1 for row in signals if row.get("status") == "PENDING")
    settled = wins + loses

    total_profit = 0.0

    for row in signals:
        if row.get("status") == "WIN":
            odds = float(row.get("odds") or 1.0)
            row["profit"] = max(0.0, odds - 1.0)
            total_profit += row["profit"]
        elif row.get("status") == "LOSE":
            row["profit"] = -1.0
            total_profit -= 1.0
        else:
            row["profit"] = 0.0

    profit = total_profit
    accuracy = round(wins / settled * 100, 2) if settled else 0.0
    roi = round(profit / settled * 100, 2) if settled else 0.0

    for row in signals:
        timestamp = row.get("sent_at")
        try:
            row["sent_at_text"] = datetime.fromtimestamp(
                int(timestamp)
            ).strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError, OSError):
            row["sent_at_text"] = "—"

    settled_rows = sorted(
        (row for row in signals if row.get("status") in ("WIN", "LOSE")),
        key=lambda row: int(
            row.get("result_updated_at") or row.get("sent_at") or 0
        )
    )

    chart_labels = []
    chart_data = []
    cumulative = 0.0

    for row in settled_rows:
        timestamp = row.get("result_updated_at") or row.get("sent_at")
        try:
            label = datetime.fromtimestamp(
                int(timestamp)
            ).strftime("%d.%m %H:%M")
        except (TypeError, ValueError, OSError):
            label = "—"

        cumulative += float(row.get("profit") or 0)
        chart_labels.append(label)
        chart_data.append(round(cumulative, 2))

    # ========================================================
    # СТАТИСТИКА ПРЕМАТЧ-МОДЕЛЕЙ
    # ========================================================

    try:
        model_stats.init_db()
        model_stats_data = model_stats.get_all_model_stats() or {}
        model_predictions = model_stats.get_recent_predictions(limit=200) or []
    except Exception as exc:
        print(f"⚠️ OLD Web: ошибка загрузки статистики моделей: {exc}", flush=True)
        model_stats_data = {}
        model_predictions = []

    for prediction in model_predictions:
        try:
            prediction["created_at_text"] = datetime.fromtimestamp(
                int(prediction.get("created_at") or 0)
            ).strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError, OSError):
            prediction["created_at_text"] = "—"

    return render_template_string(
        HTML_TEMPLATE,
        signals=signals,
        total=len(signals),
        wins=wins,
        loses=loses,
        pending=pending,
        accuracy=accuracy,
        profit=profit,
        roi=roi,
        updated=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        chart_labels=json.dumps(chart_labels, ensure_ascii=False),
        chart_data=json.dumps(chart_data),
        status_labels={
            "WIN": "ЗАШЛО",
            "LOSE": "НЕ ЗАШЛО",
            "PENDING": "ОЖИДАНИЕ",
        },
        model_stats_data=model_stats_data,
        model_predictions=model_predictions,
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    db.init_db()
    model_stats.init_db()

    app.run(
        host="0.0.0.0",
        port=3000,
        use_reloader=False
    )