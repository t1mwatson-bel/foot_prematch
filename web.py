# -*- coding: utf-8 -*-

import json
from datetime import datetime

from flask import Flask, render_template_string, jsonify

import database as db
import match_momentum
import model_stats


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
<title>OLD — Live Statistics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
:root {
  color-scheme: dark;
  --bg:#050b19; --panel:rgba(10,23,45,.91);
  --border:rgba(117,164,226,.34); --text:#eef5ff;
  --muted:#a6b8d4; --green:#41e6a1; --red:#ff6b81;
  --blue:#6dc5ff; --yellow:#ffd36b; --gold:#ffc65c;
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
body:before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(circle at 3% 20%,rgba(255,255,255,.18),transparent 2px),
    radial-gradient(circle at 15% 65%,rgba(255,255,255,.15),transparent 2px),
    radial-gradient(circle at 90% 25%,rgba(255,210,120,.15),transparent 3px),
    radial-gradient(circle at 97% 70%,rgba(255,255,255,.15),transparent 2px);
}
.snow{
  position:fixed;inset:-100px 0 0;pointer-events:none;z-index:5;opacity:.4;
  background-image:
    radial-gradient(2px 2px at 20px 30px,#fff 50%,transparent 100%),
    radial-gradient(2px 2px at 80px 120px,#fff 50%,transparent 100%),
    radial-gradient(3px 3px at 150px 70px,#fff 50%,transparent 100%),
    radial-gradient(2px 2px at 220px 180px,#fff 50%,transparent 100%),
    radial-gradient(2px 2px at 300px 40px,#fff 50%,transparent 100%);
  background-size:400px 240px;animation:snowfall 18s linear infinite;
}
@keyframes snowfall{from{transform:translateY(-100px)}to{transform:translateY(240px)}}
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

/* MOMENTUM */
.momentum-panel{
  border-color:rgba(91,176,255,.48);
  background:radial-gradient(ellipse at 50% 0%,rgba(38,106,173,.2),transparent 65%),
             linear-gradient(145deg,rgba(13,31,57,.97),rgba(5,15,31,.97));
}
.momentum-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.momentum-heading h2{font-size:20px;margin:0}
.momentum-controls{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
.momentum-select,.window-button{color:var(--text);background:#10243f;border:1px solid #365477;border-radius:10px;padding:11px 13px;font-size:13px;outline:none}
.momentum-select{flex:1;min-width:220px}
.window-button{cursor:pointer;transition:.2s}
.window-button:hover{border-color:var(--blue)}
.window-button.active{color:#061323;background:var(--blue);border-color:var(--blue);font-weight:900}
.momentum-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:16px}
.momentum-box{background:rgba(4,14,30,.72);border:1px solid rgba(110,160,220,.25);border-radius:13px;padding:16px;min-width:0}
.momentum-label{color:var(--muted);font-size:12px;margin-bottom:8px}
.momentum-number{font-size:clamp(22px,3vw,32px);font-weight:900;overflow-wrap:anywhere}
.home-color{color:#55c7ff}.away-color{color:#ffbd59}
.momentum-status{display:inline-block;border-radius:30px;padding:7px 13px;font-size:12px;font-weight:800;background:rgba(255,255,255,.07);border:1px solid var(--border)}
.status-rising{color:var(--green);border-color:rgba(65,230,161,.45);background:rgba(65,230,161,.09)}
.status-falling{color:var(--red);border-color:rgba(255,107,129,.45);background:rgba(255,107,129,.09)}
.status-stable{color:var(--yellow);border-color:rgba(255,211,107,.4);background:rgba(255,211,107,.08)}
.status-insufficient{color:var(--muted)}
.momentum-chart-wrap{height:300px;position:relative}
.momentum-legend{display:flex;gap:18px;flex-wrap:wrap;margin:12px 0;font-size:12px;color:var(--muted)}
.legend-home{color:#55c7ff}.legend-away{color:#ffbd59}
.momentum-note{color:var(--muted);font-size:11px;margin-top:12px;line-height:1.5}
.momentum-empty{text-align:center;padding:35px 12px;color:var(--muted);line-height:1.7}

@media(max-width:850px){
  .cards{grid-template-columns:repeat(2,minmax(0,1fr))}
  .card:last-child{grid-column:span 2}
  .panel{padding:14px}
  .momentum-grid,.models-grid{grid-template-columns:1fr}
  .momentum-chart-wrap{height:250px}
  .decor{opacity:.2}
}
@media(max-width:420px){
  .wrap{width:94%;padding-top:18px}
  .card{padding:13px}
  .momentum-controls{display:grid;grid-template-columns:1fr 1fr}
  .momentum-select{grid-column:span 2}
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
    <div class="sub">Статистика прогнозов на следующий гол до конца матча</div>
  </div>
  <div class="updated">Обновлено: {{ updated }}</div>
</header>

<section class="cards">
  <div class="card"><div class="label">Всего прогнозов</div><div class="value">{{ total }}</div></div>
  <div class="card"><div class="label">Зашло</div><div class="value green">{{ wins }}</div></div>
  <div class="card"><div class="label">Не зашло</div><div class="value red">{{ loses }}</div></div>
  <div class="card"><div class="label">Ожидают результата</div><div class="value yellow">{{ pending }}</div></div>
  <div class="card"><div class="label">Проходимость</div><div class="value blue">{{ accuracy }}%</div><div class="small">Только завершённые прогнозы</div></div>
</section>

<section class="cards">
  <div class="card" style="grid-column:span 2">
    <div class="label">Общая прибыль, условные единицы</div>
    <div class="value {{ 'green' if profit >= 0 else 'red' }}">{{ '%+.2f'|format(profit) }}</div>
  </div>
  <div class="card" style="grid-column:span 3">
    <div class="label">ROI по завершённым прогнозам</div>
    <div class="value {{ 'green' if roi >= 0 else 'red' }}">{{ '%+.2f'|format(roi) }}%</div>
    <div class="small">Расчёт по единичной ставке на каждый завершённый сигнал</div>
  </div>
</section>

<!-- OLD PREMATCH MODELS -->
<section class="panel models-section">
  <h2>🧠 OLD PREMATCH MODELS</h2>
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
  <h2>📈 Накопленная прибыль лайв-бота</h2>
  <div class="chart-wrap"><canvas id="profitChart"></canvas></div>
</section>

<!-- OLD MATCH MOMENTUM -->
<section class="panel momentum-panel">
  <div class="momentum-heading">
    <h2>⚡ OLD MATCH MOMENTUM</h2>
    <span id="momentumState" class="momentum-status status-insufficient">Ожидание данных</span>
  </div>
  <div class="small">Импульс команд · Температура матча · Изменение инициативы</div>
  <div class="momentum-controls">
    <select id="momentumMatch" class="momentum-select"><option value="">Загрузка матчей...</option></select>
    <button class="window-button active" data-window="5" type="button">5 минут</button>
    <button class="window-button" data-window="10" type="button">10 минут</button>
    <button class="window-button" data-window="15" type="button">15 минут</button>
  </div>
  <div id="momentumContent"><div class="momentum-empty">Загружаем историю Momentum...</div></div>
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

<footer>OLD · Статистика рассчитывается по данным SQLite · ❄️</footer>
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

/* OLD MATCH MOMENTUM */
let momentumChart=null,momentumHistory=[],selectedWindow=5,currentMatch=null;
const matchSelect=document.getElementById('momentumMatch');
const momentumContent=document.getElementById('momentumContent');
const momentumState=document.getElementById('momentumState');

function setMomentumState(state,label){
  momentumState.textContent=label;
  momentumState.className='momentum-status';
  if(state==='RISING')momentumState.classList.add('status-rising');
  else if(state==='FALLING')momentumState.classList.add('status-falling');
  else if(state==='STABLE')momentumState.classList.add('status-stable');
  else momentumState.classList.add('status-insufficient');
}
function calculateDelta(current,previous,key){
  const difference=Number(current[key]||0)-Number(previous[key]||0);
  return difference>0?difference:0;
}
function calculateTeamImpulse(current,previous,side){
  const n=side==='home'?'1':'2';
  const xg=calculateDelta(current,previous,'xg'+n);
  const sot=calculateDelta(current,previous,'shots_on'+n);
  const shots=calculateDelta(current,previous,'shots_all'+n);
  const corners=calculateDelta(current,previous,'corners'+n);
  const attacks=calculateDelta(current,previous,'att'+n);
  return xg*8+sot*2.5+shots*.8+corners*1.2+attacks*.08;
}
function calculateWindow(history,index,minutes){
  const current=history[index],target=Number(current.ts)-minutes*60;
  const tolerance=Math.max(150,minutes*60*.35);
  let previous=null;
  for(let i=index-1;i>=0;i--){
    const ts=Number(history[i].ts);
    if(ts<=target&&ts>=target-tolerance){previous=history[i];break;}
    if(ts<target-tolerance)break;
  }
  if(!previous)return null;
  const elapsed=Math.max(1,Number(current.ts)-Number(previous.ts));
  const home=calculateTeamImpulse(current,previous,'home');
  const away=calculateTeamImpulse(current,previous,'away');
  const factor=300/elapsed;
  return {home:home*factor,away:away*factor,temperature:(home+away)*factor,elapsed};
}
function getCurrentMomentum(){
  if(!momentumHistory.length)return null;
  return calculateWindow(momentumHistory,momentumHistory.length-1,selectedWindow);
}
function getStateFromHistory(){
  const i=momentumHistory.length-1;
  const c5=calculateWindow(momentumHistory,i,5);
  const c10=calculateWindow(momentumHistory,i,10);
  const c15=calculateWindow(momentumHistory,i,15);
  if(!c5||(!c10&&!c15))return {state:'INSUFFICIENT',label:'Недостаточно истории'};
  const baseValues=[];
  if(c10)baseValues.push(c10.temperature);
  if(c15)baseValues.push(c15.temperature);
  const baseline=baseValues.reduce((a,b)=>a+b,0)/baseValues.length;
  if(c5.temperature>=Math.max(3,baseline*1.25))return {state:'RISING',label:'Активность растёт'};
  if(c5.temperature<=baseline*.70)return {state:'FALLING',label:'Активность снижается'};
  return {state:'STABLE',label:'Активность стабильна'};
}
function escapeHtml(value){
  return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}
function renderMomentum(){
  if(!momentumHistory.length){
    momentumContent.innerHTML='<div class="momentum-empty">Пока нет истории этого матча.<br>Дождитесь накопления снимков статистики.</div>';
    setMomentumState('INSUFFICIENT','Недостаточно истории');return;
  }
  const latest=momentumHistory[momentumHistory.length-1];
  const result=getCurrentMomentum(),state=getStateFromHistory();
  const homeName=latest.team1||'Хозяева',awayName=latest.team2||'Гости';
  setMomentumState(state.state,state.label);
  if(!result){
    momentumContent.innerHTML=`<div class="momentum-empty">Собираем историю для окна ${selectedWindow} минут.<br>Нужно немного времени, чтобы накопить данные.</div>`;
    if(momentumChart){momentumChart.destroy();momentumChart=null;}return;
  }
  let leaderText='Равная активность';
  if(result.home>result.away*1.15&&result.home-result.away>=1)leaderText=homeName;
  else if(result.away>result.home*1.15&&result.away-result.home>=1)leaderText=awayName;
  momentumContent.innerHTML=`
    <div class="momentum-grid">
      <div class="momentum-box"><div class="momentum-label">Импульс хозяев</div><div class="momentum-number home-color">${result.home.toFixed(2)}</div><div class="small">${escapeHtml(homeName)}</div></div>
      <div class="momentum-box"><div class="momentum-label">Импульс гостей</div><div class="momentum-number away-color">${result.away.toFixed(2)}</div><div class="small">${escapeHtml(awayName)}</div></div>
      <div class="momentum-box"><div class="momentum-label">Температура матча</div><div class="momentum-number">${result.temperature.toFixed(2)}</div><div class="small">Инициатива: ${escapeHtml(leaderText)}</div></div>
    </div>
    <div class="momentum-legend"><span class="legend-home">● ${escapeHtml(homeName)}</span><span class="legend-away">● ${escapeHtml(awayName)}</span></div>
    <div class="momentum-chart-wrap"><canvas id="momentumChart"></canvas></div>
    <div class="momentum-note">Показатель рассчитан по приросту статистики за выбранное окно и приведён к условным пяти минутам. Это экспериментальный индекс активности, а не вероятность гола.</div>`;
  drawMomentumChart(homeName,awayName);
}
function drawMomentumChart(homeName,awayName){
  const labels=[],homeData=[],awayData=[];
  for(let i=0;i<momentumHistory.length;i++){
    const point=calculateWindow(momentumHistory,i,selectedWindow);
    if(!point)continue;
    const date=new Date(Number(momentumHistory[i].ts)*1000);
    labels.push(date.toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}));
    homeData.push(Number(point.home.toFixed(2)));
    awayData.push(Number(point.away.toFixed(2)));
  }
  const canvas=document.getElementById('momentumChart');
  if(!canvas)return;
  if(momentumChart)momentumChart.destroy();
  momentumChart=new Chart(canvas,{
    type:'line',
    data:{labels,datasets:[
      {label:homeName,data:homeData,borderColor:'#55c7ff',fill:false,tension:.28,pointRadius:0,borderWidth:2.5},
      {label:awayName,data:awayData,borderColor:'#ffbd59',fill:false,tension:.28,pointRadius:0,borderWidth:2.5}
    ]},
    options:{
      responsive:true,maintainAspectRatio:false,
      interaction:{intersect:false,mode:'index'},
      plugins:{legend:{display:false}},
      scales:{
        x:{ticks:{color:'#a6b8d4',maxTicksLimit:8},grid:{color:'rgba(100,140,190,.12)'}},
        y:{beginAtZero:true,ticks:{color:'#a6b8d4'},grid:{color:'rgba(100,140,190,.16)'}}
      }
    }
  });
}
async function loadMomentumMatches(){
  try{
    const response=await fetch('/api/momentum/matches');
    if(!response.ok)throw new Error('Ошибка получения матчей');
    const matches=await response.json(),previousValue=matchSelect.value;
    matchSelect.innerHTML='';
    if(!matches.length){
      matchSelect.innerHTML='<option value="">Пока нет матчей Momentum</option>';
      momentumContent.innerHTML='<div class="momentum-empty">Матчи появятся после накопления первых снимков.</div>';
      return;
    }
    matches.forEach(match=>{
      const option=document.createElement('option');
      option.value=match.game_id;
      option.textContent=`${match.team1} — ${match.team2} | ${match.score||'—'} | ${match.minute||0}'`;
      matchSelect.appendChild(option);
    });
    const exists=matches.some(m=>String(m.game_id)===previousValue);
    if(exists)matchSelect.value=previousValue;
    if(!matchSelect.value)matchSelect.selectedIndex=0;
    if(!currentMatch||String(currentMatch)!==String(matchSelect.value)){
      currentMatch=matchSelect.value;await loadMomentumHistory();
    }
  }catch(error){
    console.error('OLD Momentum:',error);
    matchSelect.innerHTML='<option value="">Ошибка загрузки матчей</option>';
  }
}
async function loadMomentumHistory(){
  const gameId=matchSelect.value;if(!gameId)return;
  currentMatch=gameId;
  try{
    const response=await fetch('/api/momentum/'+encodeURIComponent(gameId));
    if(!response.ok)throw new Error('Ошибка истории Momentum');
    momentumHistory=await response.json();renderMomentum();
  }catch(error){
    console.error('OLD Momentum:',error);
    momentumContent.innerHTML='<div class="momentum-empty">Не удалось загрузить историю матча.</div>';
  }
}
document.querySelectorAll('.window-button').forEach(button=>{
  button.addEventListener('click',()=>{
    selectedWindow=Number(button.dataset.window);
    document.querySelectorAll('.window-button').forEach(item=>item.classList.remove('active'));
    button.classList.add('active');renderMomentum();
  });
});
matchSelect.addEventListener('change',loadMomentumHistory);
loadMomentumMatches();
setInterval(loadMomentumHistory,45000);
setInterval(loadMomentumMatches,60000);
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
        print(f"⚠️ OLD Web: ошибка API Momentum matches: {exc}", flush=True)
        return jsonify([]), 500


# ============================================================
# API MOMENTUM — ИСТОРИЯ МАТЧА
# ============================================================

@app.route("/api/momentum/<game_id>")
def momentum_history_api(game_id):
    try:
        history = match_momentum.get_momentum_history(game_id, limit=1000)
        return jsonify(history)
    except Exception as exc:
        print(f"⚠️ OLD Web: ошибка API Momentum history: {exc}", flush=True)
        return jsonify([]), 500


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
