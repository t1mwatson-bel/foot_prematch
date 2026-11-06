
# -*- coding: utf-8 -*-

import json
from datetime import datetime

from flask import Flask, render_template_string

import model_stats
from config import MOSCOW_TZ


app = Flask(__name__)


# ============================================================
# HTML + CSS
# ============================================================

HTML_TEMPLATE = r"""
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">

<title>❄️ OLD PREMATCH STATS 🎄</title>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
:root {
  color-scheme: dark;
  --bg:#050b19;
  --panel:rgba(10,23,45,.91);
  --border:rgba(117,164,226,.34);
  --text:#eef5ff;
  --muted:#a6b8d4;
  --green:#41e6a1;
  --red:#ff6b81;
  --blue:#6dc5ff;
  --yellow:#ffd36b;
  --gold:#ffc65c;
}

*{box-sizing:border-box}

html{min-height:100%}

body{
  margin:0;
  min-height:100vh;
  color:var(--text);
  font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
  background:
    radial-gradient(ellipse at 50% 0%,rgba(40,83,145,.55),transparent 45%),
    radial-gradient(ellipse at 0% 45%,rgba(16,73,126,.32),transparent 40%),
    radial-gradient(ellipse at 100% 65%,rgba(111,53,21,.22),transparent 35%),
    linear-gradient(180deg,#071329 0%,#050b19 55%,#09152a 100%);
  background-attachment:fixed;
  overflow-x:hidden;
}

.snow{
  position:fixed;
  top:-50px;
  left:0;
  width:100%;
  height:100vh;
  pointer-events:none;
  z-index:5;
  background-image:
    radial-gradient(4px 4px at 10% 10%,#fff 50%,transparent 100%),
    radial-gradient(3px 3px at 20% 40%,#fff 50%,transparent 100%),
    radial-gradient(5px 5px at 30% 70%,#fff 50%,transparent 100%),
    radial-gradient(2px 2px at 40% 20%,#fff 50%,transparent 100%),
    radial-gradient(4px 4px at 50% 80%,#fff 50%,transparent 100%),
    radial-gradient(3px 3px at 60% 30%,#fff 50%,transparent 100%),
    radial-gradient(5px 5px at 70% 60%,#fff 50%,transparent 100%),
    radial-gradient(2px 2px at 80% 10%,#fff 50%,transparent 100%),
    radial-gradient(4px 4px at 90% 90%,#fff 50%,transparent 100%);
  background-size:200px 200px;
  animation:snowfall 8s linear infinite;
  opacity:.6;
}

@keyframes snowfall{
  0%{
    background-position:0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0,0 0;
  }
  100%{
    background-position:0 200px,0 200px,0 200px,0 200px,
                         0 200px,0 200px,0 200px,0 200px,0 200px;
  }
}

.garland{
  position:fixed;
  top:0;
  left:0;
  width:100%;
  height:10px;
  display:flex;
  justify-content:space-between;
  z-index:100;
}

.garland span{
  width:8px;
  height:12px;
  border-radius:50%;
  animation:blink 1.5s infinite alternate;
}

.garland span:nth-child(odd){
  animation-delay:.5s;
  background:#ff4b4b;
  box-shadow:0 0 10px #ff4b4b;
}

.garland span:nth-child(even){
  animation-delay:1s;
  background:#4bff4b;
  box-shadow:0 0 10px #4bff4b;
}

.garland span:nth-child(3n){
  background:#4b4bff;
  box-shadow:0 0 10px #4b4bff;
  animation-delay:.2s;
}

.garland span:nth-child(4n){
  background:#ffff4b;
  box-shadow:0 0 10px #ffff4b;
  animation-delay:.8s;
}

@keyframes blink{
  from{opacity:.3}
  to{opacity:1}
}

.decor{
  position:fixed;
  z-index:1;
  pointer-events:none;
  font-size:clamp(34px,5vw,70px);
  opacity:.45;
  filter:drop-shadow(0 0 12px rgba(255,190,70,.4));
}

.decor-left{left:8px;top:160px}
.decor-right{right:8px;top:280px}
.decor-bottom-left{left:12px;bottom:18px}
.decor-bottom-right{right:12px;bottom:18px}

.wrap{
  position:relative;
  z-index:2;
  width:min(1250px,94%);
  margin:0 auto;
  padding:28px 0 50px;
}

header{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:16px;
  flex-wrap:wrap;
  margin-bottom:24px;
}

.logo{
  font-size:clamp(25px,4vw,36px);
  font-weight:900;
  letter-spacing:2px;
  text-shadow:0 0 25px rgba(92,170,255,.3);
}

.logo span{color:var(--blue)}

.sub,.updated{
  color:var(--muted);
  font-size:13px;
  margin-top:5px;
}

.updated{font-size:12px}

.cards{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:12px;
  margin-bottom:18px;
}

.card,.panel{
  background:linear-gradient(
    145deg,
    rgba(20,43,74,.95),
    rgba(7,17,35,.96)
  );
  border:1px solid var(--border);
  border-radius:16px;
  box-shadow:
    0 12px 40px rgba(0,0,0,.38),
    inset 0 1px 0 rgba(255,255,255,.035);
}

.card{
  padding:18px;
  min-width:0;
}

.card .label{
  color:var(--muted);
  font-size:12px;
  margin-bottom:10px;
}

.card .value{
  font-size:clamp(20px,2.5vw,29px);
  font-weight:800;
  overflow-wrap:anywhere;
}

.green{color:var(--green)}
.red{color:var(--red)}
.blue{color:var(--blue)}
.yellow{color:var(--yellow)}

.panel{
  padding:20px;
  margin-bottom:18px;
  backdrop-filter:blur(12px);
}

.panel h2{
  margin:0 0 16px;
  font-size:17px;
}

.chart-wrap{height:260px}

.table-wrap{overflow-x:auto}

table{
  width:100%;
  border-collapse:collapse;
  min-width:950px;
}

th,td{
  padding:13px 12px;
  border-bottom:1px solid var(--border);
  text-align:left;
  font-size:13px;
  vertical-align:top;
}

th{
  color:var(--muted);
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.6px;
}

tr:last-child td{border-bottom:0}

.match{
  font-weight:700;
  min-width:190px;
}

.small{
  color:var(--muted);
  font-size:11px;
  margin-top:5px;
}

.pill{
  display:inline-block;
  padding:5px 9px;
  border-radius:20px;
  font-size:11px;
  font-weight:800;
  white-space:nowrap;
}

.pill-WIN{
  color:var(--green);
  background:#41e6a118;
}

.pill-LOSE{
  color:var(--red);
  background:#ff6b8118;
}

.pill-PENDING{
  color:var(--yellow);
  background:#ffd36b18;
}

.empty{
  text-align:center;
  padding:32px;
  color:var(--muted);
}

footer{
  text-align:center;
  color:var(--muted);
  font-size:12px;
  padding-top:8px;
}

.models-section{
  border-color:rgba(255,198,92,.45);
  background:
    radial-gradient(ellipse at 50% 0%,rgba(255,198,92,.12),transparent 65%),
    linear-gradient(145deg,rgba(20,35,58,.97),rgba(5,15,31,.97));
}

.models-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:14px;
  margin:20px 0;
}

.model-card{
  background:rgba(4,14,30,.75);
  border:1px solid rgba(255,198,92,.28);
  border-radius:15px;
  padding:17px;
  min-width:0;
}

.model-title{
  font-size:17px;
  font-weight:900;
  margin-bottom:15px;
  color:var(--gold);
}

.model-metrics{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:10px;
}

.model-metric{
  background:rgba(255,255,255,.035);
  border-radius:10px;
  padding:11px;
}

.model-metric-label{
  color:var(--muted);
  font-size:11px;
  margin-bottom:6px;
}

.model-metric-value{
  font-size:21px;
  font-weight:900;
  overflow-wrap:anywhere;
}

.model-name{
  color:var(--gold);
  font-weight:800;
}

@media(max-width:850px){
  .cards{grid-template-columns:repeat(2,minmax(0,1fr))}
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

<div class="garland">
  <span></span><span></span><span></span><span></span>
  <span></span><span></span><span></span><span></span>
  <span></span><span></span><span></span><span></span>
  <span></span><span></span><span></span><span></span>
  <span></span><span></span><span></span><span></span>
</div>

<div class="snow"></div>

<div class="decor decor-left">🎄</div>
<div class="decor decor-right">🎄</div>
<div class="decor decor-bottom-left">🎁</div>
<div class="decor decor-bottom-right">🎁</div>

<div class="wrap">

<header>
  <div>
    <div class="logo">❄️ <span>OLD</span> PREMATCH STATS 🎅</div>
    <div class="sub">Статистика двух независимых прематч-моделей</div>
  </div>
  <div class="updated">Обновлено: {{ updated }}</div>
</header>

<section class="cards">
  <div class="card">
    <div class="label">🎯 Всего прогнозов</div>
    <div class="value">{{ total }}</div>
  </div>

  <div class="card">
    <div class="label">✅ Зашло</div>
    <div class="value green">{{ wins }}</div>
  </div>

  <div class="card">
    <div class="label">❌ Не зашло</div>
    <div class="value red">{{ loses }}</div>
  </div>

  <div class="card">
    <div class="label">⏳ Ожидают результата</div>
    <div class="value yellow">{{ pending }}</div>
  </div>
</section>

<section class="cards">
  <div class="card">
    <div class="label">📈 Проходимость</div>
    <div class="value blue">{{ accuracy }}%</div>
    <div class="small">Только завершённые прогнозы</div>
  </div>

  <div class="card">
    <div class="label">💰 Общая прибыль</div>
    <div class="value {{ 'green' if profit >= 0 else 'red' }}">
      {{ '%+.2f'|format(profit) }}
    </div>
  </div>

  <div class="card">
    <div class="label">📊 ROI</div>
    <div class="value {{ 'green' if roi >= 0 else 'red' }}">
      {{ '%+.2f'|format(roi) }}%
    </div>
    <div class="small">Единичная ставка на каждый прогноз</div>
  </div>

  <div class="card">
    <div class="label">🎲 Средний коэффициент</div>
    <div class="value">{{ "%.2f"|format(average_odds) }}</div>
  </div>
</section>


<!-- СТАТИСТИКА МОДЕЛЕЙ -->

<section class="panel models-section">

  <h2>🧠 OLD PREMATCH MODELS 🎁</h2>

  <div class="small">
    Раздельная статистика двух независимых прематч-моделей
  </div>

  <div class="models-grid">

    {% for model_name in ["OLD CHECKLIST 10", "OLD GOALS MODEL"] %}

      {% set st = model_stats_data.get(model_name, {}) %}

      <div class="model-card">

        <div class="model-title">{{ model_name }}</div>

        <div class="model-metrics">

          <div class="model-metric">
            <div class="model-metric-label">Всего прогнозов</div>
            <div class="model-metric-value">{{ st.get("total", 0) }}</div>
          </div>

          <div class="model-metric">
            <div class="model-metric-label">Проходимость</div>
            <div class="model-metric-value blue">{{ st.get("accuracy", 0) }}%</div>
          </div>

          <div class="model-metric">
            <div class="model-metric-label">Зашло</div>
            <div class="model-metric-value green">{{ st.get("wins", 0) }}</div>
          </div>

          <div class="model-metric">
            <div class="model-metric-label">Не зашло</div>
            <div class="model-metric-value red">{{ st.get("losses", 0) }}</div>
          </div>

          <div class="model-metric">
            <div class="model-metric-label">Ожидают</div>
            <div class="model-metric-value yellow">{{ st.get("pending", 0) }}</div>
          </div>

          <div class="model-metric">
            <div class="model-metric-label">Средний коэффициент</div>
            <div class="model-metric-value">{{ "%.2f"|format(st.get("average_odds", 0)|float) }}</div>
          </div>

          <div class="model-metric">
            <div class="model-metric-label">Прибыль</div>
            <div class="model-metric-value {{ 'green' if st.get('profit', 0)|float >= 0 else 'red' }}">
              {{ "%+.2f"|format(st.get("profit", 0)|float) }}
            </div>
          </div>

          <div class="model-metric">
            <div class="model-metric-label">ROI</div>
            <div class="model-metric-value {{ 'green' if st.get('roi', 0)|float >= 0 else 'red' }}">
              {{ "%+.2f"|format(st.get("roi", 0)|float) }}%
            </div>
          </div>

        </div>
      </div>

    {% endfor %}

  </div>


  <h2>📊 Сравнение моделей</h2>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Модель</th>
          <th>Всего</th>
          <th>WIN</th>
          <th>LOSE</th>
          <th>Ожидание</th>
          <th>Проходимость</th>
          <th>Средний КФ</th>
          <th>Прибыль</th>
          <th>ROI</th>
        </tr>
      </thead>

      <tbody>
        {% for model_name in ["OLD CHECKLIST 10", "OLD GOALS MODEL"] %}
          {% set st = model_stats_data.get(model_name, {}) %}

          <tr>
            <td class="model-name">{{ model_name }}</td>
            <td>{{ st.get("total", 0) }}</td>
            <td class="green">{{ st.get("wins", 0) }}</td>
            <td class="red">{{ st.get("losses", 0) }}</td>
            <td class="yellow">{{ st.get("pending", 0) }}</td>
            <td>{{ st.get("accuracy", 0) }}%</td>
            <td>{{ "%.2f"|format(st.get("average_odds", 0)|float) }}</td>
            <td>{{ "%+.2f"|format(st.get("profit", 0)|float) }}</td>
            <td>{{ "%+.2f"|format(st.get("roi", 0)|float) }}%</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

</section>


<!-- ИСТОРИЯ ПРЕМАТЧ-ПРОГНОЗОВ -->

<section class="panel">

  <h2>🔮 История прематч-прогнозов</h2>

  <div class="table-wrap">
    <table>

      <thead>
        <tr>
          <th>Время</th>
          <th>Модель</th>
          <th>Матч</th>
          <th>Лига</th>
          <th>Коэффициент</th>
          <th>Вероятность</th>
          <th>Прогноз</th>
          <th>Итоговый счёт</th>
          <th>Результат</th>
          <th>Прибыль</th>
        </tr>
      </thead>

      <tbody>

        {% for p in model_predictions %}

          {% set pred = p.get("prediction", {}) %}

          <tr>

            <td>{{ p.get("created_at_text", "—") }}</td>

            <td class="model-name">
              {{ p.get("model_name", "—") }}
            </td>

            <td class="match">
              {{ p.get("team1", "—") }} — {{ p.get("team2", "—") }}
            </td>

            <td>{{ p.get("league") or "—" }}</td>

            <td>
              {{ "%.2f"|format(p.get("odds_over", 0)|float) if p.get("odds_over") else "—" }}
            </td>

            <td>
              {% if p.get("probability_display") %}
                {{ p.get("probability_display") }}
              {% else %}
                —
              {% endif %}
            </td>

            <td>{{ p.get("prediction_display", "ТБ 2.5") }}</td>

            <td>{{ p.get("final_score") or "—" }}</td>

            <td>
              <span class="pill pill-{{ p.get('outcome', 'PENDING') }}">
                {% if p.get("outcome") == "WIN" %}
                  ЗАШЛО
                {% elif p.get("outcome") == "LOSE" %}
                  НЕ ЗАШЛО
                {% else %}
                  ОЖИДАНИЕ
                {% endif %}
              </span>
            </td>

            <td class="{{ 'green' if p.get('profit', 0)|float > 0 else ('red' if p.get('profit', 0)|float < 0 else '') }}">
              {{ "%+.2f"|format(p.get("profit", 0)|float) }}
            </td>

          </tr>

        {% else %}

          <tr>
            <td colspan="10" class="empty">
              Пока нет прематч-прогнозов
            </td>
          </tr>

        {% endfor %}

      </tbody>
    </table>
  </div>

</section>


<!-- ГРАФИК ПРЕМАТЧ-ПРИБЫЛИ -->

<section class="panel">

  <h2>📈 Накопленная прибыль прематч-моделей</h2>

  <div class="chart-wrap">
    <canvas id="profitChart"></canvas>
  </div>

</section>


<footer>
  OLD · Статистика прематч-моделей · ❄️ С Наступающим Новым Годом! 🎄
</footer>

</div>


<script>
const labels = {{ chart_labels|safe }};
const values = {{ chart_data|safe }};

new Chart(document.getElementById('profitChart'), {
  type:'line',

  data:{
    labels:labels,
    datasets:[{
      label:'Накопленная прибыль',
      data:values,
      borderColor:'#6dc5ff',
      backgroundColor:'rgba(109,197,255,0.13)',
      fill:true,
      tension:.25,
      pointRadius:3,
      pointBackgroundColor:'#fff'
    }]
  },

  options:{
    responsive:true,
    maintainAspectRatio:false,

    plugins:{
      legend:{
        labels:{color:'#eef5ff'}
      }
    },

    scales:{
      x:{
        ticks:{color:'#a6b8d4'},
        grid:{color:'#253b59'}
      },
      y:{
        ticks:{color:'#a6b8d4'},
        grid:{color:'#253b59'}
      }
    }
  }
});
</script>

</body>
</html>
"""


# ============================================================
# ПОДГОТОВКА ВЕРОЯТНОСТИ
# ============================================================

def get_probability(prediction):
    if not isinstance(prediction, dict):
        return None

    value = prediction.get("probability_percent")

    if value is None:
        value = prediction.get("probability")

    if value is None:
        value = prediction.get("probability_over_2_5")

    if value is None:
        return None

    try:
        value = float(value)

        # Значение от 0 до 1 переводим в проценты.
        if 0 <= value <= 1:
            value *= 100

        return round(value, 1)

    except (TypeError, ValueError):
        return None


# ============================================================
# НАЗВАНИЕ ПРОГНОЗА
# ============================================================

def get_prediction_display(prediction):
    if not isinstance(prediction, dict):
        return "ТБ 2.5"

    value = (
        prediction.get("prediction")
        or prediction.get("recommendation")
        or prediction.get("market")
        or prediction.get("score")
    )

    if value is None:
        return "ТБ 2.5"

    return str(value)


# ============================================================
# ГЛАВНАЯ СТРАНИЦА
# ============================================================

@app.route("/")
def index():

    model_stats_data = {}
    model_predictions = []

    try:
        model_stats.init_db()

        model_stats_data = (
            model_stats.get_all_model_stats() or {}
        )

        # Берём расширенную историю, чтобы расчёт среднего
        # коэффициента и графика не ограничивался 100 записями.
        model_predictions = (
            model_stats.get_recent_predictions(limit=10000) or []
        )

    except Exception as exc:
        print(
            f"⚠️ OLD Web: ошибка загрузки прематч-статистики: {exc}",
            flush=True
        )

    # ========================================================
    # ПОДГОТОВКА СТАТИСТИКИ И ИСТОРИИ
    # ========================================================

    total = 0
    wins = 0
    loses = 0
    pending = 0
    profit = 0.0
    odds_values = []

    for model_name in (
        "OLD CHECKLIST 10",
        "OLD GOALS MODEL"
    ):

        if model_name not in model_stats_data:
            model_stats_data[model_name] = {
                "model_name": model_name,
                "total": 0,
                "wins": 0,
                "losses": 0,
                "pending": 0,
                "accuracy": 0,
                "profit": 0,
                "roi": 0,
                "average_odds": 0,
            }

    for prediction in model_predictions:

        # Время создания.
        created_ts = prediction.get("created_ts")

        try:
            if created_ts:
                prediction["created_at_text"] = (
                    datetime.fromtimestamp(
                        int(created_ts),
                        MOSCOW_TZ
                    ).strftime("%d.%m.%Y %H:%M")
                )
            else:
                prediction["created_at_text"] = "—"

        except (TypeError, ValueError, OSError):
            prediction["created_at_text"] = "—"

        # Данные модели.
        pred = prediction.get("prediction") or {}

        if not isinstance(pred, dict):
            pred = {}

        probability = get_probability(pred)

        prediction["probability_display"] = (
            f"{probability:.1f}%"
            if probability is not None
            else None
        )

        prediction["prediction_display"] = (
            get_prediction_display(pred)
        )

        # Коэффициенты.
        odds = prediction.get("odds_over")

        try:
            odds = float(odds)

            if odds > 1:
                odds_values.append(odds)

        except (TypeError, ValueError):
            pass

    # ========================================================
    # ДОПОЛНЕНИЕ СТАТИСТИКИ МОДЕЛЕЙ
    # ========================================================

    for model_name in (
        "OLD CHECKLIST 10",
        "OLD GOALS MODEL"
    ):

        st = model_stats_data[model_name]

        # Приводим названия полей к одному формату.
        st["losses"] = (
            st.get("losses")
            or st.get("loses")
            or 0
        )

        st["wins"] = st.get("wins") or 0
        st["pending"] = st.get("pending") or 0
        st["total"] = st.get("total") or 0

        # Средний коэффициент по сохранённым прогнозам модели.
        model_odds = []

        for prediction in model_predictions:

            if prediction.get("model_name") != model_name:
                continue

            try:
                value = float(
                    prediction.get("odds_over") or 0
                )

                if value > 1:
                    model_odds.append(value)

            except (TypeError, ValueError):
                pass

        st["average_odds"] = (
            round(sum(model_odds) / len(model_odds), 2)
            if model_odds else 0
        )

        # Общие показатели.
        total += st["total"]
        wins += st["wins"]
        loses += st["losses"]
        pending += st["pending"]

        profit += float(st.get("profit") or 0)

    settled = wins + loses

    accuracy = (
        round(wins / settled * 100, 2)
        if settled else 0
    )

    roi = (
        round(profit / settled * 100, 2)
        if settled else 0
    )

    average_odds = (
        round(sum(odds_values) / len(odds_values), 2)
        if odds_values else 0
    )

    # ========================================================
    # ГРАФИК НАКОПЛЕННОЙ ПРЕМАТЧ-ПРИБЫЛИ
    # ========================================================

    settled_predictions = [
        p for p in model_predictions
        if p.get("outcome") in ("WIN", "LOSE")
    ]

    settled_predictions.sort(
        key=lambda p: (
            int(p.get("result_ts") or 0),
            int(p.get("id") or 0)
        )
    )

    chart_labels = []
    chart_data = []

    cumulative = 0.0

    for prediction in settled_predictions:

        cumulative += float(
            prediction.get("profit") or 0
        )

        timestamp = (
            prediction.get("result_ts")
            or prediction.get("created_ts")
        )

        try:
            label = datetime.fromtimestamp(
                int(timestamp),
                MOSCOW_TZ
            ).strftime("%d.%m %H:%M")

        except (TypeError, ValueError, OSError):
            label = "—"

        chart_labels.append(label)
        chart_data.append(round(cumulative, 2))

    # ========================================================
    # ОТОБРАЖЕНИЕ
    # ========================================================

    return render_template_string(
        HTML_TEMPLATE,

        total=total,
        wins=wins,
        loses=loses,
        pending=pending,

        accuracy=accuracy,
        profit=round(profit, 2),
        roi=roi,
        average_odds=average_odds,

        updated=datetime.now(
            MOSCOW_TZ
        ).strftime("%d.%m.%Y %H:%M:%S"),

        model_stats_data=model_stats_data,
        model_predictions=model_predictions,

        chart_labels=json.dumps(
            chart_labels,
            ensure_ascii=False
        ),

        chart_data=json.dumps(chart_data),
    )


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":

    model_stats.init_db()

    app.run(
        host="0.0.0.0",
        port=3000,
        use_reloader=False
    )
