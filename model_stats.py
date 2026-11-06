
# -*- coding: utf-8 -*-

import json
from datetime import datetime

from flask import Flask, render_template_string, jsonify

import database as db
import match_momentum
import model_stats


app = Flask(__name__)


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def format_timestamp(timestamp):

    try:
        return datetime.fromtimestamp(
            int(timestamp)
        ).strftime("%d.%m.%Y %H:%M")

    except (TypeError, ValueError, OSError):
        return "—"


def get_prediction_display(prediction):

    if not isinstance(prediction, dict):
        return "—"

    probability = prediction.get("probability")

    if probability is not None:
        try:
            return f"{float(probability) * 100:.2f}%"
        except (TypeError, ValueError):
            pass

    score = prediction.get("score")

    if score is not None:
        return f"{score}/10"

    available = prediction.get("available")

    if available is not None:
        return f"{available}/10"

    return "—"


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

<title>OLD — Live Statistics</title>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>

:root {
  color-scheme: dark;

  --bg: #050b19;
  --panel: rgba(10, 23, 45, 0.91);
  --panel2: rgba(15, 32, 58, 0.94);
  --border: rgba(117, 164, 226, 0.34);

  --text: #eef5ff;
  --muted: #a6b8d4;

  --green: #41e6a1;
  --red: #ff6b81;
  --blue: #6dc5ff;
  --yellow: #ffd36b;
  --gold: #ffc65c;
}

* {
  box-sizing: border-box;
}

html {
  min-height: 100%;
}

body {
  margin: 0;
  min-height: 100vh;

  color: var(--text);

  font-family:
    Inter,
    system-ui,
    -apple-system,
    BlinkMacSystemFont,
    sans-serif;

  background:
    radial-gradient(ellipse at 50% 0%, rgba(40, 83, 145, 0.55), transparent 45%),
    radial-gradient(ellipse at 0% 45%, rgba(16, 73, 126, 0.32), transparent 40%),
    radial-gradient(ellipse at 100% 65%, rgba(111, 53, 21, 0.22), transparent 35%),
    linear-gradient(180deg, #071329 0%, #050b19 55%, #09152a 100%);

  background-attachment: fixed;

  overflow-x: hidden;
}

body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;

  background:
    radial-gradient(circle at 3% 20%, rgba(255,255,255,.18), transparent 2px),
    radial-gradient(circle at 15% 65%, rgba(255,255,255,.15), transparent 2px),
    radial-gradient(circle at 90% 25%, rgba(255,210,120,.15), transparent 3px),
    radial-gradient(circle at 97% 70%, rgba(255,255,255,.15), transparent 2px),
    linear-gradient(90deg, rgba(10, 37, 72, .2), transparent 20%, transparent 80%, rgba(10, 37, 72, .2));
}

.snow {
  position: fixed;
  inset: -100px 0 0;
  pointer-events: none;
  z-index: 5;
  opacity: .55;

  background-image:
    radial-gradient(2px 2px at 20px 30px, #fff 50%, transparent 100%),
    radial-gradient(2px 2px at 80px 120px, #fff 50%, transparent 100%),
    radial-gradient(3px 3px at 150px 70px, #fff 50%, transparent 100%),
    radial-gradient(2px 2px at 220px 180px, #fff 50%, transparent 100%),
    radial-gradient(2px 2px at 300px 40px, #fff 50%, transparent 100%),
    radial-gradient(3px 3px at 370px 150px, #fff 50%, transparent 100%);

  background-size: 400px 240px;

  animation: snowfall 18s linear infinite;
}

@keyframes snowfall {
  from {
    transform: translateY(-100px);
  }

  to {
    transform: translateY(240px);
  }
}

.decor {
  position: fixed;
  z-index: 1;
  pointer-events: none;
  font-size: clamp(34px, 5vw, 70px);
  opacity: .72;
  filter: drop-shadow(0 0 12px rgba(255, 190, 70, .4));
}

.decor-left {
  left: 8px;
  top: 160px;
}

.decor-right {
  right: 8px;
  top: 280px;
}

.decor-bottom-left {
  left: 12px;
  bottom: 18px;
}

.decor-bottom-right {
  right: 12px;
  bottom: 18px;
}

.wrap {
  position: relative;
  z-index: 2;

  width: min(1250px, 94%);
  margin: 0 auto;
  padding: 28px 0 50px;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}

.logo {
  font-size: clamp(25px, 4vw, 36px);
  font-weight: 900;
  letter-spacing: 2px;
  text-shadow: 0 0 25px rgba(92, 170, 255, .3);
}

.logo span {
  color: var(--blue);
}

.sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: 5px;
}

.updated {
  color: var(--muted);
  font-size: 12px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.card,
.panel {
  background:
    linear-gradient(
      145deg,
      rgba(20, 43, 74, .95),
      rgba(7, 17, 35, .96)
    );

  border: 1px solid var(--border);
  border-radius: 16px;

  box-shadow:
    0 12px 40px rgba(0, 0, 0, .38),
    inset 0 1px 0 rgba(255,255,255,.035);
}

.card {
  padding: 18px;
  min-width: 0;
}

.card .label {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 10px;
}

.card .value {
  font-size: clamp(20px, 2.5vw, 29px);
  font-weight: 800;
  overflow-wrap: anywhere;
}

.green { color: var(--green); }
.red { color: var(--red); }
.blue { color: var(--blue); }
.yellow { color: var(--yellow); }

.panel {
  padding: 20px;
  margin-bottom: 18px;
  backdrop-filter: blur(12px);
}

.panel h2 {
  margin: 0 0 16px;
  font-size: 17px;
}

.chart-wrap {
  height: 260px;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

th,
td {
  padding: 13px 12px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  font-size: 13px;
  vertical-align: top;
}

th {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .6px;
}

tr:last-child td {
  border-bottom: 0;
}

.match {
  font-weight: 700;
  min-width: 190px;
}

.small {
  color: var(--muted);
  font-size: 11px;
  margin-top: 5px;
}

.pill {
  display: inline-block;
  padding: 5px 9px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
}

.pill-WIN {
  color: var(--green);
  background: #41e6a118;
}

.pill-LOSE {
  color: var(--red);
  background: #ff6b8118;
}

.pill-PENDING {
  color: var(--yellow);
  background: #ffd36b18;
}

.pill-VOID {
  color: var(--muted);
  background: #a6b8d418;
}

.empty {
  text-align: center;
  padding: 32px;
  color: var(--muted);
}

footer {
  text-align: center;
  color: var(--muted);
  font-size: 12px;
  padding-top: 8px;
}


/* ============================================================
   PREMATCH MODELS
   ============================================================ */

.models-panel {
  border-color: rgba(255, 198, 92, .38);

  background:
    radial-gradient(ellipse at 50% 0%, rgba(160, 112, 35, .13), transparent 65%),
    linear-gradient(145deg, rgba(17, 34, 59, .97), rgba(5, 15, 31, .97));
}

.model-card {
  padding: 18px;
  margin-top: 16px;
  border: 1px solid rgba(117, 164, 226, .3);
  border-radius: 14px;
  background: rgba(4, 14, 30, .48);
}

.model-title {
  font-size: 16px;
  font-weight: 900;
  margin-bottom: 14px;
  color: var(--blue);
}

.model-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.model-metric {
  min-width: 0;
  padding: 13px;
  border-radius: 11px;
  background: rgba(15, 32, 58, .8);
}

.model-metric .label {
  color: var(--muted);
  font-size: 11px;
  margin-bottom: 8px;
}

.model-metric .value {
  font-size: clamp(19px, 2.4vw, 26px);
  font-weight: 900;
  overflow-wrap: anywhere;
}

.model-finance {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 10px;
}

.model-finance .model-metric .value {
  font-size: 23px;
}

.model-description {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.5;
  margin-top: 12px;
}

.model-name {
  font-weight: 800;
  color: var(--blue);
}

@media (max-width: 850px) {

  .cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .card:last-child {
    grid-column: span 2;
  }

  .panel {
    padding: 14px;
  }

  .model-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .model-metric:last-child {
    grid-column: span 2;
  }

  .decor {
    opacity: .25;
  }

}

@media (max-width: 420px) {

  .wrap {
    width: 94%;
    padding-top: 18px;
  }

  .card {
    padding: 13px;
  }

  .model-card {
    padding: 12px;
  }

  .model-metrics {
    gap: 7px;
  }

  .model-metric {
    padding: 11px;
  }

  .model-finance {
    gap: 7px;
  }

}


/* ============================================================
   MOMENTUM
   ============================================================ */

.momentum-panel {
  border-color: rgba(91, 176, 255, .48);

  background:
    radial-gradient(ellipse at 50% 0%, rgba(38, 106, 173, .2), transparent 65%),
    linear-gradient(145deg, rgba(13, 31, 57, .97), rgba(5, 15, 31, .97));
}

.momentum-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.momentum-heading h2 {
  font-size: 20px;
  margin: 0;
}

.momentum-controls {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 18px 0;
}

.momentum-select,
.window-button {
  color: var(--text);
  background: #10243f;
  border: 1px solid #365477;
  border-radius: 10px;
  padding: 11px 13px;
  font-size: 13px;
  outline: none;
}

.momentum-select {
  flex: 1;
  min-width: 220px;
}

.window-button {
  cursor: pointer;
  transition: .2s;
}

.window-button:hover {
  border-color: var(--blue);
}

.window-button.active {
  color: #061323;
  background: var(--blue);
  border-color: var(--blue);
  font-weight: 900;
}

.momentum-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.momentum-box {
  background: rgba(4, 14, 30, .72);
  border: 1px solid rgba(110, 160, 220, .25);
  border-radius: 13px;
  padding: 16px;
  min-width: 0;
}

.momentum-label {
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}

.momentum-number {
  font-size: clamp(22px, 3vw, 32px);
  font-weight: 900;
  overflow-wrap: anywhere;
}

.home-color {
  color: #55c7ff;
}

.away-color {
  color: #ffbd59;
}

.momentum-status {
  display: inline-block;
  border-radius: 30px;
  padding: 7px 13px;
  font-size: 12px;
  font-weight: 800;
  background: rgba(255,255,255,.07);
  border: 1px solid var(--border);
}

.status-rising {
  color: var(--green);
  border-color: rgba(65,230,161,.45);
  background: rgba(65,230,161,.09);
}

.status-falling {
  color: var(--red);
  border-color: rgba(255,107,129,.45);
  background: rgba(255,107,129,.09);
}

.status-stable {
  color: var(--yellow);
  border-color: rgba(255,211,107,.4);
  background: rgba(255,211,107,.08);
}

.status-insufficient {
  color: var(--muted);
}

.momentum-chart-wrap {
  height: 300px;
  position: relative;
}

.momentum-legend {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin: 12px 0;
  font-size: 12px;
  color: var(--muted);
}

.legend-home {
  color: #55c7ff;
}

.legend-away {
  color: #ffbd59;
}

.momentum-note {
  color: var(--muted);
  font-size: 11px;
  margin-top: 12px;
  line-height: 1.5;
}

.momentum-empty {
  text-align: center;
  padding: 35px 12px;
  color: var(--muted);
  line-height: 1.7;
}

@media (max-width: 850px) {

  .momentum-grid {
    grid-template-columns: 1fr;
  }

  .momentum-chart-wrap {
    height: 250px;
  }

}

@media (max-width: 420px) {

  .momentum-controls {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .momentum-select {
    grid-column: span 2;
  }

}

</style>
</head>

<body>

<div class="snow"></div>

<div class="decor decor-left">🎄</div>
<div class="decor decor-right">🎄</div>
<div class="decor decor-bottom-left">🎁</div>
<div class="decor decor-bottom-right">🎁</div>

<div class="wrap">

<header>

  <div>
    <div class="logo"><span>OLD</span> LIVE STATS</div>

    <div class="sub">
      Статистика прогнозов на следующий гол до конца матча
    </div>
  </div>

  <div class="updated">
    Обновлено: {{ updated }}
  </div>

</header>


<!-- ========================================================
     ОСНОВНАЯ ЛАЙВ-СТАТИСТИКА
     ======================================================== -->

<section class="cards">

  <div class="card">
    <div class="label">Всего прогнозов</div>
    <div class="value">{{ total }}</div>
  </div>

  <div class="card">
    <div class="label">Зашло</div>
    <div class="value green">{{ wins }}</div>
  </div>

  <div class="card">
    <div class="label">Не зашло</div>
    <div class="value red">{{ loses }}</div>
  </div>

  <div class="card">
    <div class="label">Ожидают результата</div>
    <div class="value yellow">{{ pending }}</div>
  </div>

  <div class="card">
    <div class="label">Проходимость</div>
    <div class="value blue">{{ accuracy }}%</div>
    <div class="small">Только завершённые прогнозы</div>
  </div>

</section>


<section class="cards">

  <div class="card" style="grid-column: span 2">

    <div class="label">
      Общая прибыль, условные единицы
    </div>

    <div class="value {{ 'green' if profit >= 0 else 'red' }}">
      {{ '%+.2f'|format(profit) }}
    </div>

  </div>

  <div class="card" style="grid-column: span 3">

    <div class="label">
      ROI по завершённым прогнозам
    </div>

    <div class="value {{ 'green' if roi >= 0 else 'red' }}">
      {{ '%+.2f'|format(roi) }}%
    </div>

    <div class="small">
      Расчёт по единичной ставке на каждый завершённый сигнал
    </div>

  </div>

</section>


<!-- ========================================================
     ГРАФИК ЛАЙВ-ПРИБЫЛИ
     ======================================================== -->

<section class="panel">

  <h2>📈 Накопленная прибыль</h2>

  <div class="chart-wrap">
    <canvas id="profitChart"></canvas>
  </div>

</section>


<!-- ========================================================
     OLD PREMATCH MODELS
     ======================================================== -->

<section class="panel models-panel">

  <h2>🧠 OLD PREMATCH MODELS</h2>

  <div class="small">
    Две независимые экспериментальные модели.
    Статистика не смешивается с лайв-прогнозами.
  </div>


  {% for model in models %}

  <div class="model-card">

    <div class="model-title">
      {{ model.model_name }}
    </div>

    <div class="model-metrics">

      <div class="model-metric">
        <div class="label">Всего прогнозов</div>
        <div class="value">{{ model.total }}</div>
      </div>

      <div class="model-metric">
        <div class="label">Зашло</div>
        <div class="value green">{{ model.wins }}</div>
      </div>

      <div class="model-metric">
        <div class="label">Не зашло</div>
        <div class="value red">{{ model.loses }}</div>
      </div>

      <div class="model-metric">
        <div class="label">Ожидают</div>
        <div class="value yellow">{{ model.pending }}</div>
      </div>

      <div class="model-metric">
        <div class="label">Проходимость</div>
        <div class="value blue">{{ model.accuracy }}%</div>
      </div>

    </div>


    <div class="model-finance">

      <div class="model-metric">

        <div class="label">
          Прибыль
        </div>

        <div class="value {{ 'green' if model.profit >= 0 else 'red' }}">
          {{ '%+.2f'|format(model.profit) }}
        </div>

      </div>

      <div class="model-metric">

        <div class="label">
          ROI
        </div>

        <div class="value {{ 'green' if model.roi >= 0 else 'red' }}">
          {{ '%+.2f'|format(model.roi) }}%
        </div>

      </div>

    </div>

    <div class="model-description">
      Средний коэффициент ТБ 2.5:
      {{ '%.3f'|format(model.average_odds) if model.average_odds else '—' }}
      · Статистика рассчитывается только по завершённым прогнозам.
    </div>

  </div>

  {% endfor %}

</section>


<!-- ========================================================
     ИСТОРИЯ ПРЕМАТЧ-МОДЕЛЕЙ
     ======================================================== -->

<section class="panel">

  <h2>📋 История OLD PREMATCH MODELS</h2>

  <div class="table-wrap">

    <table>

      <thead>
        <tr>
          <th>Время записи</th>
          <th>Модель</th>
          <th>Матч</th>
          <th>Дата матча</th>
          <th>Коэффициент ТБ 2.5</th>
          <th>Прогноз</th>
          <th>Итоговый счёт</th>
          <th>Результат</th>
          <th>Прибыль</th>
        </tr>
      </thead>

      <tbody>

      {% for p in model_predictions %}

        <tr>

          <td>
            {{ p.created_at_text }}
          </td>

          <td class="model-name">
            {{ p.model_name }}
          </td>

          <td class="match">
            {{ p.team1 }} — {{ p.team2 }}

            <div class="small">
              {{ p.league or '—' }}
            </div>
          </td>

          <td>
            {{ p.match_date or '—' }}
          </td>

          <td>
            {{ '%.2f'|format(p.odds_over|float) if p.odds_over else '—' }}
          </td>

          <td>
            {{ p.prediction_display }}
          </td>

          <td>
            {{ p.final_score or '—' }}
          </td>

          <td>
            <span class="pill pill-{{ p.outcome }}">
              {{ status_labels.get(p.outcome, p.outcome) }}
            </span>
          </td>

          <td class="{{ 'green' if p.profit|float > 0 else ('red' if p.profit|float < 0 else '') }}">
            {{ '%+.2f'|format(p.profit|float) }}
          </td>

        </tr>

      {% else %}

        <tr>
          <td colspan="9" class="empty">
            Пока нет сохранённых прогнозов новых моделей
          </td>
        </tr>

      {% endfor %}

      </tbody>

    </table>

  </div>

</section>


<!-- ========================================================
     OLD MATCH MOMENTUM
     ======================================================== -->

<section class="panel momentum-panel">

  <div class="momentum-heading">

    <h2>⚡ OLD MATCH MOMENTUM</h2>

    <span id="momentumState" class="momentum-status status-insufficient">
      Ожидание данных
    </span>

  </div>

  <div class="small">
    Импульс команд · Температура матча · Изменение инициативы
  </div>

  <div class="momentum-controls">

    <select id="momentumMatch" class="momentum-select">
      <option value="">Загрузка матчей...</option>
    </select>

    <button class="window-button active" data-window="5" type="button">
      5 минут
    </button>

    <button class="window-button" data-window="10" type="button">
      10 минут
    </button>

    <button class="window-button" data-window="15" type="button">
      15 минут
    </button>

  </div>

  <div id="momentumContent">

    <div class="momentum-empty">
      Загружаем историю Momentum...
    </div>

  </div>

</section>


<!-- ========================================================
     ИСТОРИЯ ЛАЙВ-ПРОГНОЗОВ
     ======================================================== -->

<section class="panel">

  <h2>📋 История лайв-прогнозов</h2>

  <div class="table-wrap">

    <table>

      <thead>
        <tr>
          <th>Время</th>
          <th>Матч</th>
          <th>Лига</th>
          <th>Стратегия</th>
          <th>Счёт при сигнале</th>
          <th>Коэффициент</th>
          <th>Результат</th>
          <th>Прибыль</th>
        </tr>
      </thead>

      <tbody>

      {% for s in signals %}

        <tr>

          <td>
            {{ s.sent_at_text }}
            <div class="small">{{ s.minute or 0 }}'</div>
          </td>

          <td class="match">

            {{ s.match_name or 'Матч не указан' }}

            {% if s.final_score %}
              <div class="small">Итог: {{ s.final_score }}</div>
            {% endif %}

          </td>

          <td>{{ s.league or '—' }}</td>

          <td>{{ s.strategy or '—' }}</td>

          <td>{{ s.score or '—' }}</td>

          <td>
            {{ '%.2f'|format(s.odds|float) if s.odds is not none else '—' }}
          </td>

          <td>
            <span class="pill pill-{{ s.status }}">
              {{ status_labels.get(s.status, s.status) }}
            </span>
          </td>

          <td class="{{ 'green' if s.profit|float > 0 else ('red' if s.profit|float < 0 else '') }}">
            {{ '%+.2f'|format(s.profit|float) }}
          </td>

        </tr>

      {% else %}

        <tr>
          <td colspan="8" class="empty">
            Пока нет записанных лайв-прогнозов
          </td>
        </tr>

      {% endfor %}

      </tbody>

    </table>

  </div>

</section>


<footer>
  OLD · Статистика рассчитывается по данным SQLite · ❄️
</footer>

</div>


<script>

/* ==========================================================
   ГРАФИК ЛАЙВ-ПРИБЫЛИ
   ========================================================== */

const labels = {{ chart_labels|safe }};
const values = {{ chart_data|safe }};

const profitCtx = document.getElementById('profitChart');

new Chart(profitCtx, {

  type: 'line',

  data: {

    labels,

    datasets: [{

      label: 'Накопленная прибыль',

      data: values,

      borderColor: '#6dc5ff',

      backgroundColor: 'rgba(109,197,255,0.13)',

      fill: true,

      tension: 0.25,

      pointRadius: 3,

      pointBackgroundColor: '#ffffff'

    }]

  },

  options: {

    responsive: true,

    maintainAspectRatio: false,

    plugins: {

      legend: {
        labels: {
          color: '#eef5ff'
        }
      }

    },

    scales: {

      x: {
        ticks: { color: '#a6b8d4' },
        grid: { color: '#253b59' }
      },

      y: {
        ticks: { color: '#a6b8d4' },
        grid: { color: '#253b59' }
      }

    }

  }

});


/* ==========================================================
   OLD MATCH MOMENTUM
   ========================================================== */

let momentumChart = null;
let momentumHistory = [];
let selectedWindow = 5;
let currentMatch = null;

const matchSelect = document.getElementById('momentumMatch');
const momentumContent = document.getElementById('momentumContent');
const momentumState = document.getElementById('momentumState');


function setMomentumState(state, label) {

  momentumState.textContent = label;

  momentumState.className = 'momentum-status';

  if (state === 'RISING') {
    momentumState.classList.add('status-rising');
  } else if (state === 'FALLING') {
    momentumState.classList.add('status-falling');
  } else if (state === 'STABLE') {
    momentumState.classList.add('status-stable');
  } else {
    momentumState.classList.add('status-insufficient');
  }

}


function calculateDelta(current, previous, key) {

  const a = Number(current[key] || 0);
  const b = Number(previous[key] || 0);

  const difference = a - b;

  return difference > 0 ? difference : 0;

}


function calculateTeamImpulse(current, previous, side) {

  const n = side === 'home' ? '1' : '2';

  const xg = calculateDelta(current, previous, 'xg' + n);

  const sot = calculateDelta(current, previous, 'shots_on' + n);

  const shots = calculateDelta(current, previous, 'shots_all' + n);

  const corners = calculateDelta(current, previous, 'corners' + n);

  const attacks = calculateDelta(current, previous, 'att' + n);

  return (
    xg * 8.0
    + sot * 2.5
    + shots * 0.8
    + corners * 1.2
    + attacks * 0.08
  );

}


function calculateWindow(history, index, minutes) {

  const current = history[index];

  const target = Number(current.ts) - minutes * 60;

  const tolerance = Math.max(
    150,
    minutes * 60 * 0.35
  );

  let previous = null;

  for (let i = index - 1; i >= 0; i--) {

    const ts = Number(history[i].ts);

    if (ts <= target && ts >= target - tolerance) {
      previous = history[i];
      break;
    }

    if (ts < target - tolerance) {
      break;
    }

  }

  if (!previous) {
    return null;
  }

  const elapsed = Math.max(
    1,
    Number(current.ts) - Number(previous.ts)
  );

  const home = calculateTeamImpulse(
    current,
    previous,
    'home'
  );

  const away = calculateTeamImpulse(
    current,
    previous,
    'away'
  );

  const factor = 300 / elapsed;

  return {

    home: home * factor,

    away: away * factor,

    temperature: (home + away) * factor,

    elapsed: elapsed

  };

}


function getCurrentMomentum() {

  if (!momentumHistory.length) {
    return null;
  }

  const index = momentumHistory.length - 1;

  return calculateWindow(
    momentumHistory,
    index,
    selectedWindow
  );

}


function getStateFromHistory() {

  const current5 = calculateWindow(
    momentumHistory,
    momentumHistory.length - 1,
    5
  );

  const current10 = calculateWindow(
    momentumHistory,
    momentumHistory.length - 1,
    10
  );

  const current15 = calculateWindow(
    momentumHistory,
    momentumHistory.length - 1,
    15
  );

  if (!current5 || (!current10 && !current15)) {
    return {
      state: 'INSUFFICIENT',
      label: 'Недостаточно истории'
    };
  }

  const baselines = [];

  if (current10) baselines.push(current10.temperature);
  if (current15) baselines.push(current15.temperature);

  const baseline = baselines.reduce(
    (sum, value) => sum + value,
    0
  ) / baselines.length;

  if (
    current5.temperature >= Math.max(3, baseline * 1.25)
  ) {
    return {
      state: 'RISING',
      label: 'Активность растёт'
    };
  }

  if (
    current5.temperature <= baseline * 0.70
  ) {
    return {
      state: 'FALLING',
      label: 'Активность снижается'
    };
  }

  return {
    state: 'STABLE',
    label: 'Активность стабильна'
  };

}


function renderMomentum() {

  if (!momentumHistory.length) {

    momentumContent.innerHTML = `
      <div class="momentum-empty">
        Пока нет истории этого матча.<br>
        Дождитесь накопления снимков статистики.
      </div>
    `;

    setMomentumState(
      'INSUFFICIENT',
      'Недостаточно истории'
    );

    return;
  }


  const latest = momentumHistory[momentumHistory.length - 1];

  const result = getCurrentMomentum();

  const homeName = latest.team1 || 'Хозяева';
  const awayName = latest.team2 || 'Гости';

  const state = getStateFromHistory();

  setMomentumState(
    state.state,
    state.label
  );


  if (!result) {

    momentumContent.innerHTML = `
      <div class="momentum-empty">
        Собираем историю для окна ${selectedWindow} минут.<br>
        Нужно немного времени, чтобы накопить данные.
      </div>
    `;

    if (momentumChart) {
      momentumChart.destroy();
      momentumChart = null;
    }

    return;
  }


  const leaderDifference = result.home - result.away;

  let leaderText = 'Равная активность';

  if (
    result.home > result.away * 1.15 &&
    leaderDifference >= 1
  ) {
    leaderText = homeName;
  } else if (
    result.away > result.home * 1.15 &&
    -leaderDifference >= 1
  ) {
    leaderText = awayName;
  }


  const temperature = result.temperature.toFixed(2);

  momentumContent.innerHTML = `

    <div class="momentum-grid">

      <div class="momentum-box">

        <div class="momentum-label">
          Импульс хозяев
        </div>

        <div class="momentum-number home-color">
          ${result.home.toFixed(2)}
        </div>

        <div class="small">
          ${escapeHtml(homeName)}
        </div>

      </div>


      <div class="momentum-box">

        <div class="momentum-label">
          Импульс гостей
        </div>

        <div class="momentum-number away-color">
          ${result.away.toFixed(2)}
        </div>

        <div class="small">
          ${escapeHtml(awayName)}
        </div>

      </div>


      <div class="momentum-box">

        <div class="momentum-label">
          Температура матча
        </div>

        <div class="momentum-number">
          ${temperature}
        </div>

        <div class="small">
          Инициатива: ${escapeHtml(leaderText)}
        </div>

      </div>

    </div>


    <div class="momentum-legend">

      <span class="legend-home">
        ● ${escapeHtml(homeName)}
      </span>

      <span class="legend-away">
        ● ${escapeHtml(awayName)}
      </span>

    </div>


    <div class="momentum-chart-wrap">
      <canvas id="momentumChart"></canvas>
    </div>


    <div class="momentum-note">
      Показатель рассчитан по приросту статистики
      за выбранное окно и приведён к условным пяти минутам.
      Это экспериментальный индекс активности, а не вероятность гола.
    </div>

  `;


  drawMomentumChart(homeName, awayName);

}


function escapeHtml(value) {

  return String(value).replace(/[&<>"']/g, function(character) {

    const entities = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };

    return entities[character];

  });

}


function drawMomentumChart(homeName, awayName) {

  const labels = [];
  const homeData = [];
  const awayData = [];

  for (let i = 0; i < momentumHistory.length; i++) {

    const point = calculateWindow(
      momentumHistory,
      i,
      selectedWindow
    );

    if (!point) {
      continue;
    }

    const timestamp = Number(momentumHistory[i].ts);

    const date = new Date(timestamp * 1000);

    labels.push(
      date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
      })
    );

    homeData.push(Number(point.home.toFixed(2)));
    awayData.push(Number(point.away.toFixed(2)));

  }


  const canvas = document.getElementById('momentumChart');

  if (!canvas) return;

  if (momentumChart) {
    momentumChart.destroy();
  }


  momentumChart = new Chart(canvas, {

    type: 'line',

    data: {

      labels,

      datasets: [

        {

          label: homeName,

          data: homeData,

          borderColor: '#55c7ff',

          backgroundColor: 'rgba(85,199,255,.10)',

          fill: false,

          tension: .28,

          pointRadius: 0,

          borderWidth: 2.5

        },

        {

          label: awayName,

          data: awayData,

          borderColor: '#ffbd59',

          backgroundColor: 'rgba(255,189,89,.10)',

          fill: false,

          tension: .28,

          pointRadius: 0,

          borderWidth: 2.5

        }

      ]

    },

    options: {

      responsive: true,

      maintainAspectRatio: false,

      interaction: {
        intersect: false,
        mode: 'index'
      },

      plugins: {

        legend: {
          display: false
        }

      },

      scales: {

        x: {

          ticks: {
            color: '#a6b8d4',
            maxTicksLimit: 8
          },

          grid: {
            color: 'rgba(100,140,190,.12)'
          }

        },

        y: {

          beginAtZero: true,

          ticks: {
            color: '#a6b8d4'
          },

          grid: {
            color: 'rgba(100,140,190,.16)'
          }

        }

      }

    }

  });

}


/* ==========================================================
   ЗАГРУЗКА МАТЧЕЙ
   ========================================================== */

async function loadMomentumMatches() {

  try {

    const response = await fetch('/api/momentum/matches');

    if (!response.ok) {
      throw new Error('Ошибка получения матчей');
    }

    const matches = await response.json();

    const previousValue = matchSelect.value;

    matchSelect.innerHTML = '';

    if (!matches.length) {

      matchSelect.innerHTML = `
        <option value="">
          Пока нет матчей Momentum
        </option>
      `;

      momentumContent.innerHTML = `
        <div class="momentum-empty">
          Матчи появятся после накопления первых снимков.
        </div>
      `;

      return;
    }


    matches.forEach(function(match) {

      const option = document.createElement('option');

      option.value = match.game_id;

      option.textContent =
        `${match.team1} — ${match.team2} | ${match.score || '—'} | ${match.minute || 0}'`;

      matchSelect.appendChild(option);

    });


    const stillExists = matches.some(
      match => String(match.game_id) === previousValue
    );

    if (stillExists) {
      matchSelect.value = previousValue;
    }

    if (!matchSelect.value) {
      matchSelect.selectedIndex = 0;
    }

    if (
      !currentMatch ||
      String(currentMatch) !== String(matchSelect.value)
    ) {
      currentMatch = matchSelect.value;
      await loadMomentumHistory();
    }

  } catch (error) {

    console.error('OLD Momentum:', error);

    matchSelect.innerHTML = `
      <option value="">
        Ошибка загрузки матчей
      </option>
    `;

  }

}


/* ==========================================================
   ЗАГРУЗКА ИСТОРИИ МАТЧА
   ========================================================== */

async function loadMomentumHistory() {

  const gameId = matchSelect.value;

  if (!gameId) return;

  currentMatch = gameId;

  try {

    const response = await fetch(
      '/api/momentum/' + encodeURIComponent(gameId)
    );

    if (!response.ok) {
      throw new Error('Ошибка истории Momentum');
    }

    momentumHistory = await response.json();

    renderMomentum();

  } catch (error) {

    console.error('OLD Momentum:', error);

    momentumContent.innerHTML = `
      <div class="momentum-empty">
        Не удалось загрузить историю матча.
      </div>
    `;

  }

}


/* ==========================================================
   ПЕРЕКЛЮЧЕНИЕ ОКОН
   ========================================================== */

document.querySelectorAll('.window-button').forEach(function(button) {

  button.addEventListener('click', function() {

    selectedWindow = Number(button.dataset.window);

    document.querySelectorAll('.window-button').forEach(function(item) {
      item.classList.remove('active');
    });

    button.classList.add('active');

    renderMomentum();

  });

});


matchSelect.addEventListener('change', function() {

  loadMomentumHistory();

});


/* ==========================================================
   ЗАПУСК
   ========================================================== */

loadMomentumMatches();

setInterval(function() {
  loadMomentumHistory();
}, 45000);

setInterval(function() {
  loadMomentumMatches();
}, 60000);

</script>

</body>
</html>
"""


# ============================================================
# API MOMENTUM — СПИСОК МАТЧЕЙ
# ============================================================

@app.route("/api/momentum/matches")
def momentum_matches_api():

    try:

        matches = match_momentum.get_recent_momentum_matches(50)

        return jsonify(matches)

    except Exception as exc:

        print(
            f"⚠️ OLD Web: ошибка API Momentum matches: {exc}",
            flush=True
        )

        return jsonify([]), 500


# ============================================================
# API MOMENTUM — ИСТОРИЯ МАТЧА
# ============================================================

@app.route("/api/momentum/<game_id>")
def momentum_history_api(game_id):

    try:

        history = match_momentum.get_momentum_history(
            game_id,
            limit=1000
        )

        return jsonify(history)

    except Exception as exc:

        print(
            f"⚠️ OLD Web: ошибка API Momentum history: {exc}",
            flush=True
        )

        return jsonify([]), 500


# ============================================================
# ГЛАВНАЯ СТРАНИЦА
# ============================================================

@app.route("/")
def index():

    # ========================================================
    # ЛАЙВ-ПРОГНОЗЫ
    # ========================================================

    all_rows = db.get_live_signals()

    signals = [
        dict(row)
        for row in all_rows
        if row.get("game_id") and row.get("match_name")
    ]

    wins = sum(
        1 for row in signals
        if row.get("status") == "WIN"
    )

    loses = sum(
        1 for row in signals
        if row.get("status") == "LOSE"
    )

    pending = sum(
        1 for row in signals
        if row.get("status") == "PENDING"
    )

    settled = wins + loses


    # ========================================================
    # ПЕРЕСЧЁТ ПРИБЫЛИ ЛАЙВ
    # ========================================================

    total_profit = 0.0

    for row in signals:

        if row.get("status") == "WIN":

            odds = safe_float(
                row.get("odds"),
                1.0
            )

            row["profit"] = max(
                0.0,
                odds - 1.0
            )

            total_profit += row["profit"]

        elif row.get("status") == "LOSE":

            row["profit"] = -1.0

            total_profit -= 1.0

        else:

            row["profit"] = 0.0


    profit = total_profit

    accuracy = (
        round(wins / settled * 100, 2)
        if settled else 0.0
    )

    roi = (
        round(profit / settled * 100, 2)
        if settled else 0.0
    )


    # ========================================================
    # ВРЕМЯ ЛАЙВ-ПРОГНОЗОВ
    # ========================================================

    for row in signals:

        row["sent_at_text"] = format_timestamp(
            row.get("sent_at")
        )


    # ========================================================
    # ГРАФИК ПРИБЫЛИ
    # ========================================================

    settled_rows = sorted(
        (
            row for row in signals
            if row.get("status") in ("WIN", "LOSE")
        ),
        key=lambda row: int(
            row.get("result_updated_at")
            or row.get("sent_at")
            or 0
        ),
    )

    chart_labels = []
    chart_data = []

    cumulative = 0.0

    for row in settled_rows:

        timestamp = (
            row.get("result_updated_at")
            or row.get("sent_at")
        )

        label = format_timestamp(timestamp)

        if label != "—":
            try:
                date_obj = datetime.fromtimestamp(
                    int(timestamp)
                )
                label = date_obj.strftime("%d.%m %H:%M")
            except (TypeError, ValueError, OSError):
                label = "—"

        cumulative += safe_float(
            row.get("profit")
        )

        chart_labels.append(label)

        chart_data.append(
            round(cumulative, 2)
        )


    # ========================================================
    # СТАТИСТИКА PREMATCH-МОДЕЛЕЙ
    # ========================================================

    try:

        model_stats.init_db()

        all_model_stats = model_stats.get_all_model_stats()

        models = []

        for model_name in (
            "OLD CHECKLIST 10",
            "OLD GOALS MODEL"
        ):

            model = all_model_stats.get(
                model_name,
                {}
            )

            models.append({

                "model_name": model_name,

                "total": int(model.get("total", 0) or 0),

                "wins": int(model.get("wins", 0) or 0),

                "loses": int(model.get("loses", 0) or 0),

                "pending": int(model.get("pending", 0) or 0),

                "accuracy": safe_float(
                    model.get("accuracy")
                ),

                "profit": safe_float(
                    model.get("profit")
                ),

                "roi": safe_float(
                    model.get("roi")
                ),

                "average_odds": safe_float(
                    model.get("average_odds")
                ),

            })


        model_predictions = model_stats.get_recent_predictions(
            limit=100
        )

        for prediction in model_predictions:

            prediction["created_at_text"] = format_timestamp(
                prediction.get("created_at")
            )

            prediction["prediction_display"] = get_prediction_display(
                prediction.get("prediction")
            )

            prediction["odds_over"] = safe_float(
                prediction.get("odds_over")
            )

            prediction["profit"] = safe_float(
                prediction.get("profit")
            )

            prediction["outcome"] = (
                prediction.get("outcome") or "PENDING"
            )

    except Exception as exc:

        print(
            f"⚠️ OLD Web: ошибка статистики моделей: {exc}",
            flush=True
        )

        models = [
            {
                "model_name": "OLD CHECKLIST 10",
                "total": 0,
                "wins": 0,
                "loses": 0,
                "pending": 0,
                "accuracy": 0,
                "profit": 0,
                "roi": 0,
                "average_odds": 0
            },
            {
                "model_name": "OLD GOALS MODEL",
                "total": 0,
                "wins": 0,
                "loses": 0,
                "pending": 0,
                "accuracy": 0,
                "profit": 0,
                "roi": 0,
                "average_odds": 0
            }
        ]

        model_predictions = []


    # ========================================================
    # СТРАНИЦА
    # ========================================================

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

        models=models,

        model_predictions=model_predictions,

        updated=datetime.now().strftime(
            "%d.%m.%Y %H:%M:%S"
        ),

        chart_labels=json.dumps(
            chart_labels,
            ensure_ascii=False
        ),

        chart_data=json.dumps(
            chart_data
        ),

        status_labels={

            "WIN": "ЗАШЛО",

            "LOSE": "НЕ ЗАШЛО",

            "PENDING": "ОЖИДАНИЕ",

            "VOID": "ОТМЕНА",

        },

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
