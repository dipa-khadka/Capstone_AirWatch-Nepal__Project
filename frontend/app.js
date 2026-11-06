/* =====================================================================
   AirWatch Nepal: the browser side (what happens on the web page).
   It asks the Flask API (backend/app.py) for data, then fills the page
   and draws the charts with Chart.js.

   Parts of this file:
     1. Small helpers
     2. Colours, wording and advice texts
     3. Talking to the API
     4. Charts
     5. The pages (home, trends, history, compare, predict)
     6. Menu, live data button and start-up
   ===================================================================== */

/* ---------- 1. Small helpers ---------- */

// Short name for document.querySelector, so $('#city') finds the element with id "city".
const $ = s => document.querySelector(s);

// Date text for chart labels, for example "Nov 6", and with the year, "Nov 6, 2018".
const fd = s => new Date(s + 'T00:00:00').toLocaleDateString('en', { month: 'short', day: 'numeric' });
const fdy = s => new Date(s + 'T00:00:00').toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });

// Month text, for example "Feb 2017". The input looks like "2017-02".
const fm = s => new Date(s + '-01T00:00:00').toLocaleDateString('en', { month: 'short', year: 'numeric' });

// Adds n days to a date text like "2018-03-01" and gives the new date text.
const addDays = (s, n) => {
  const d = new Date(s + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};

// Reads a CSS variable, for example the grey text colour used on charts.
const cssv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/* ---------- 2. Colours, wording and advice texts ---------- */

// Plain names for the pollutants: [short plain name, one-line explanation, icon].
// The code (PM2.5, O3 ...) stays visible for students and researchers.
const INFO = {
  'PM2.5': ['Fine dust', 'Tiny dust particles that can reach deep into the lungs. Mostly from vehicles, burning, and factories.', '🌫️'],
  'PM10': ['Dust', 'Larger dust particles from roads, construction, and smoke.', '🏗️'],
  'O3': ['Ozone', 'A gas that forms in sunlight and can irritate the chest.', '☀️'],
  'NO2': ['Vehicle gas', 'A gas from vehicle exhaust and fuel burning.', '🚗'],
  'SO2': ['Fuel smoke gas', 'A gas from burning coal and diesel, for example in brick kilns.', '🏭'],
  'CO': ['Carbon monoxide', 'A gas from incomplete burning, such as vehicles and wood fires.', '🔥']
};

// The six health levels: [background colour, text colour]. They match the colours in style.css.
const COLORS = {
  'Good': ['#00b050', '#000'],
  'Moderate': ['#ffff00', '#000'],
  'Unhealthy for Sensitive Groups': ['#ff9900', '#000'],
  'Unhealthy': ['#ff0000', '#fff'],
  'Very Unhealthy': ['#7030a0', '#fff'],
  'Hazardous': ['#7e0023', '#fff']
};
const col = l => COLORS[l] || ['#888', '#fff'];   // grey if the level is unknown

// A small picture for each level, shown in the banner.
const ICON = { 'Good': '😊', 'Moderate': '🙂', 'Unhealthy for Sensitive Groups': '😷', 'Unhealthy': '⚠️', 'Very Unhealthy': '🚨', 'Hazardous': '☠️' };

// The AQI ranges as [from, to, level]. Used for the coloured chart background, the legend,
// the point colours and the marker on the colour bar.
const BANDS = [[0, 50, 'Good'], [50, 100, 'Moderate'], [100, 150, 'Unhealthy for Sensitive Groups'],
  [150, 200, 'Unhealthy'], [200, 300, 'Very Unhealthy'], [300, 500, 'Hazardous']];

// Gives the level name for an AQI number, for example lab(120) is "Unhealthy for Sensitive Groups".
const lab = a => { for (const [, hi, l] of BANDS) if (a <= hi) return l; return 'Hazardous'; };

// Simple advice for each level: [icon, title, text]. This is extra help for normal users.
// The official health message of each level still comes from the database (HEALTH_CATEGORY table).
const TIPS = {
  'Good': [['🏃', 'Exercise outside', 'Safe for everyone'], ['🪟', 'Windows', 'Open them to let fresh air in'], ['😷', 'Face mask', 'Not needed'], ['👶', 'Children and older people', 'Normal outdoor play is fine']],
  'Moderate': [['🏃', 'Exercise outside', 'Fine for most. Very sensitive people can go easy'], ['🪟', 'Windows', 'Fine to open'], ['😷', 'Face mask', 'Not needed'], ['👶', 'Children and older people', 'Fine, watch for coughing']],
  'Unhealthy for Sensitive Groups': [['🏃', 'Exercise outside', 'Keep it light and short'], ['🪟', 'Windows', 'Open only for a short time'], ['😷', 'Face mask', 'People with breathing problems should wear one'], ['👶', 'Children and older people', 'Keep outdoor time short']],
  'Unhealthy': [['🏃', 'Exercise outside', 'Do it indoors today'], ['🪟', 'Windows', 'Keep them closed'], ['😷', 'Face mask', 'Wear an N95 or KN95 outside'], ['👶', 'Children and older people', 'Better to stay indoors']],
  'Very Unhealthy': [['🏃', 'Exercise outside', 'Avoid it'], ['🪟', 'Windows', 'Keep them closed'], ['😷', 'Face mask', 'Wear an N95 or KN95 outside'], ['👶', 'Children and older people', 'Stay indoors']],
  'Hazardous': [['🏃', 'Exercise outside', 'Do not exercise outside'], ['🪟', 'Windows', 'Closed, seal the gaps if you can'], ['😷', 'Face mask', 'N95 or KN95 at all times outside'], ['👶', 'Children and older people', 'Stay indoors and avoid going out']]
};

// A coloured pill with the level name, for example "Unhealthy" in red.
const tagHtml = l => { const [bg, fg] = col(l); return `<span class="tag" style="background:${bg};color:${fg}">${l}</span>`; };

// The legend under a chart: one coloured square and name for each level.
const legendHtml = () => BANDS.map(([lo, hi, l]) =>
  `<span><i style="background:${col(l)[0]}"></i>${l} <small>${hi === 500 ? '301+' : (lo === 0 ? 0 : lo + 1) + '-' + hi}</small></span>`).join('');

// Plain wording for the data source name that comes from the database.
const srcName = s => s === 'Sample data' ? 'Sample data (not real readings)' : s === 'aqicn.org' ? 'aqicn.org (Nepal Department of Environment)' : s;

/* ---------- 3. Talking to the API ---------- */

// Asks the backend for data, for example api('current?city=Pokhara').
// If the backend answers with an error, the error text is thrown so the page can show it.
async function api(path) {
  const r = await fetch('/api/' + path);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ('Request failed (' + r.status + ')'));
  return j;
}

// Shows (or hides, when the text is empty) the red error box at the top of the page.
function showErr(m) {
  const e = $('#err');
  e.hidden = !m;
  e.textContent = m || '';
  if (m) e.scrollIntoView({ block: 'nearest' });
}

// Fills the bottom line (source and last update) and the "old data" notice.
// `list` holds the readings that were used on the page (more than one on the Compare page).
function setFoot(d, list = [d]) {
  const old = list.filter(x => x.stale), n = $('#stale');
  n.hidden = !old.length;
  n.textContent = old.length ? `No recent data for ${old.map(x => x.city).join(', ')}. Showing the last available reading${old.length > 1 ? 's' : ''} (${old.map(x => x.time.slice(0, 10)).join(', ')}).` : '';
  $('#foot').textContent = 'Data source: ' + srcName(d.source) + '  |  Last updated: ' + d.time;
}

/* ---------- 4. Charts ---------- */

const charts = {};   // the charts that are on screen, so an old chart can be removed before a new one is drawn

// Draws a chart in the canvas with the given id.
function mk(id, cfg) {
  if (typeof Chart === 'undefined') {   // the Chart.js file did not load, for example no internet
    $('#' + id).parentNode.insertAdjacentHTML('afterbegin', '<p class="note">The chart library could not load.</p>');
    return;
  }
  if (charts[id]) charts[id].destroy();
  Chart.defaults.color = cssv('--muted');
  Chart.defaults.borderColor = cssv('--line');
  charts[id] = new Chart($('#' + id), cfg);
}

// Options shared by all charts: fit the box, animate softly, round bar corners.
const base = { responsive: true, maintainAspectRatio: false, animation: { duration: 900, easing: 'easeOutQuart' }, elements: { bar: { borderRadius: 8, borderSkipped: false } } };

// A Chart.js plugin that paints the six health colours as a light background on a chart.
const bands = {
  id: 'bands',
  beforeDatasetsDraw(ch) {
    const { ctx, chartArea: a, scales: { y } } = ch;
    ctx.save();
    ctx.beginPath(); ctx.rect(a.left, a.top, a.width, a.height); ctx.clip();   // paint only inside the chart
    ctx.globalAlpha = .16;                                                       // light, so the line stays readable
    BANDS.forEach(([lo, hi, l]) => {
      if (lo >= y.max || hi <= y.min) return;                                   // this level is outside the visible range
      const top = y.getPixelForValue(Math.min(hi, y.max)), bottom = y.getPixelForValue(Math.max(lo, y.min));
      ctx.fillStyle = col(l)[0];
      ctx.fillRect(a.left, top, a.width, bottom - top);
    });
    ctx.restore();
  }
};

// Pollutant names for chart labels, for example ['Fine dust', 'Dust', ...].
const names = o => Object.keys(o).map(k => INFO[k][0]);

/* ---------- 5. The pages ---------- */

/* ----- HOME: the air right now (UC-02, UC-06) ----- */
async function home() {
  const city = $('#city').value, enc = encodeURIComponent(city);
  const d = await api('current?city=' + enc);
  const [bg, fg] = col(d.label);
  const p = Object.fromEntries(Object.entries(d.pollutants).filter(([k, v]) => v !== null));   // keep only the pollutants we have

  // Coloured health message at the top
  const b = $('#banner');
  b.style.display = ''; b.style.background = `linear-gradient(120deg,${bg},${bg}d9)`; b.style.color = fg;
  b.innerHTML = `<span class="bi">${ICON[d.label] || ''}</span><div><strong>${d.label} (AQI ${d.aqi})</strong><br>${d.message}</div>`;

  // The AQI circle: the number counts up and the coloured arc grows to match the value
  countUp($('#aqinum'), d.aqi);
  $('#aqicard').style.borderTopColor = bg;
  const arc = $('#arc');
  arc.style.stroke = bg;
  arc.style.strokeDasharray = `${Math.min(d.aqi, 300) / 300 * 326.7} 327`;   // 326.7 is the full circle length
  const tg = $('#aqicat'); tg.textContent = d.label; tg.style.background = bg; tg.style.color = fg;

  // Marker on the colour bar: find the level, then how far inside the level the AQI is
  const i = BANDS.findIndex(([, hi]) => d.aqi <= hi), band = BANDS[i < 0 ? 5 : i];
  const inside = Math.min(1, (d.aqi - band[0]) / (band[1] - band[0]));
  $('#marker').style.left = ((i < 0 ? 5 : i) + inside) / 6 * 100 + '%';

  // Facts list. The "compared with" line uses the daily averages of the last days (it is skipped if there is no data).
  let change = 'Not enough data yet';
  try {
    const t = await api('trend?city=' + enc + '&days=7'), ds = t.days;
    if (ds.length >= 2) {
      const last = ds[ds.length - 1], prev = ds[ds.length - 2], diff = last.aqi - prev.aqi;
      change = diff === 0 ? `Same as ${fd(prev.date)}` : `${Math.abs(diff)} ${diff > 0 ? 'higher (worse)' : 'lower (better)'} than ${fd(prev.date)}`;
    }
  } catch (e) { /* the facts list simply keeps the default text */ }
  $('#facts').innerHTML = [['City', city], ['Last updated', d.time], ['Data from', srcName(d.source)], ['Daily average', change]]
    .map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');

  // "What you can do" advice for this level
  $('#dos').innerHTML = '<small>What you can do today</small>' + (TIPS[d.label] || []).map(([icon, title, text]) =>
    `<div class="do"><span class="di">${icon}</span><div><strong>${title}</strong><span class="tx">${text}</span></div></div>`).join('');

  // One box per pollutant with its plain name, value and explanation
  $('#chips').innerHTML = Object.entries(p).map(([k, v]) =>
    `<div class="pt"><div><b>${INFO[k][2]} ${INFO[k][0]}</b> <small>(${k})</small></div><span class="pv">${v}</span><p>${INFO[k][1]}</p></div>`).join('');

  // Bar chart of the pollutants
  mk('c_home', { type: 'bar', data: { labels: names(p), datasets: [{ data: Object.values(p), backgroundColor: '#2e75b6' }] }, options: { ...base, plugins: { legend: { display: false } } } });
  setFoot(d);
  tiles();   // the "Air across Nepal" tiles below
}

// "Air across Nepal": one tile per city with its latest AQI. A click opens that city.
async function tiles() {
  try {
    const list = await api('overview');
    $('#tiles').innerHTML = list.map(x => {
      const [bg] = col(x.label);
      return `<button class="tile${x.stale ? ' old' : ''}" data-city="${x.city}" style="border-left-color:${bg}">` +
        `<span class="tn">${x.city}</span><span class="ta">${x.aqi}</span>${tagHtml(x.label)}` +
        `<small>${x.stale ? 'Last seen ' + x.time.slice(0, 10) : 'Updated ' + x.time.slice(5, 16)}</small></button>`;
    }).join('');
    document.querySelectorAll('.tile').forEach(t => t.addEventListener('click', () => { $('#city').value = t.dataset.city; run(); window.scrollTo({ top: 0, behavior: 'smooth' }); }));
  } catch (e) { $('#tiles').innerHTML = ''; }
}

// Makes a number count up from 0 to `to` in under a second.
function countUp(el, to) {
  const t0 = performance.now();
  (function step(now) {
    const k = Math.min(1, (now - t0) / 800);
    el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3)));   // ease-out: fast first, slow at the end
    if (k < 1) requestAnimationFrame(step);
  })(t0);
}

/* ----- HISTORY: all stored data, month by month ----- */
let lastHist = [];   // the months on screen, kept so the CSV button can download them
async function history() {
  const d = await api('history?city=' + encodeURIComponent($('#city').value));

  // Fill the year menu and keep the year the user had chosen, if it still exists
  const sel = $('#hyear'), prev = sel.value;
  sel.innerHTML = '<option value="all">All years</option>' + d.years.map(y => `<option>${y.year}</option>`).join('');
  sel.value = [...sel.options].some(o => o.value === prev) ? prev : 'all';

  // Keep only the chosen year (or everything)
  const yr = sel.value;
  const months = d.months.filter(m => yr === 'all' || m.month.startsWith(yr));
  const years = d.years.filter(y => yr === 'all' || String(y.year) === yr);
  lastHist = months.filter(m => m.avg !== null);   // months that really have data

  // One card per year
  $('#hcards').innerHTML = years.map(y => `<div class="card" style="border-top-color:${col(y.label)[0]}"><small>${y.year} average</small><b>${y.avg}</b>${tagHtml(y.label)}<small>${y.days} day${y.days === 1 ? '' : 's'} of data</small>${y.worst_month ? `<small>Worst month: ${fm(y.worst_month)} (AQI ${y.worst_avg})</small>` : ''}</div>`).join('');

  // Table of the months that have data
  $('#htable').innerHTML = lastHist.map(m => `<tr><td>${fm(m.month)}</td><td>${m.avg}</td><td>${m.max}</td><td>${m.days}</td><td>${tagHtml(m.label)}</td></tr>`).join('');

  // Bar chart: one bar per month, coloured by level. Bars with less than 10 days of data are faded ('66' makes the colour see-through).
  const faded = m => m.days < 10;
  mk('c_hist', {
    type: 'bar',
    data: { labels: months.map(m => fm(m.month)), datasets: [{ label: 'Monthly average AQI', data: months.map(m => m.avg), backgroundColor: months.map(m => m.avg === null ? 'transparent' : col(m.label)[0] + (faded(m) ? '66' : '')), borderRadius: 3 }] },
    options: {
      ...base,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => { const m = months[c.dataIndex]; return m.avg === null ? 'No data' : `Average AQI ${m.avg} (${m.label}), ${m.days} day${m.days === 1 ? '' : 's'} of data`; } } } },
      scales: { x: { ticks: { maxTicksLimit: 12, autoSkip: true } } }
    }
  });
  $('#stale').hidden = true;
  $('#foot').textContent = 'Data sources: ' + d.sources.join(', ') + '  |  Data from ' + fm(d.from) + ' to ' + fm(d.to);
}

// Downloads the months on screen as a CSV file (opens in Excel).
function downloadCsv() {
  if (!lastHist.length) return;
  const rows = ['month,average_aqi,highest_aqi,days_of_data,level', ...lastHist.map(m => `${m.month},${m.avg},${m.max},${m.days},${m.label}`)];
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv' }));
  a.download = 'airwatch_' + $('#city').value.toLowerCase() + '_monthly.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ----- TRENDS: daily averages over a date range (UC-03) ----- */
async function trends() {
  const city = encodeURIComponent($('#city').value), r = $('#range').value;
  $('#custom').hidden = r !== 'custom';   // the two date boxes only show for "Custom range"

  // Build the API address: either "last N days" or a start and end date
  let url = 'trend?city=' + city;
  if (r === 'custom') {
    if (!$('#dfrom').value || !$('#dto').value) {   // first time: start with the last 30 days of this city
      const c = await api('current?city=' + city), end = c.time.slice(0, 10);
      $('#dto').value = end;
      $('#dfrom').value = addDays(end, -29);
    }
    url += '&start=' + $('#dfrom').value + '&end=' + $('#dto').value;
  } else url += '&days=' + r;
  const d = await api(url), s = d.stats;

  // Three boxes: average, highest, lowest
  $('#tstats').innerHTML = `<div class="card"><small>Average AQI</small><b>${s.average}</b><small>of the whole period</small></div>` +
    `<div class="card"><small>Highest AQI</small><b>${s.highest.aqi}</b><small>${fd(s.highest.date)}</small></div>` +
    `<div class="card"><small>Lowest AQI</small><b>${s.lowest.aqi}</b><small>${fd(s.lowest.date)}</small></div>`;

  // Put every day on the axis, so days without data show as a gap in the line
  const first = d.days[0].date, last = d.days[d.days.length - 1].date, byDay = Object.fromEntries(d.days.map(x => [x.date, x.aqi])), dates = [];
  for (let x = first; x <= last; x = addDays(x, 1)) dates.push(x);
  const vals = dates.map(x => byDay[x] ?? null), label = dates.length > 90 ? fdy : fd;

  mk('c_trend', {
    type: 'line', plugins: [bands],
    data: {
      labels: dates.map(label),
      datasets: [
        // The daily line. Each point has the colour of its health level.
        { label: 'Daily average AQI', data: vals, borderColor: '#2e75b6', backgroundColor: 'rgba(46,117,182,.15)', pointBackgroundColor: vals.map(v => v === null ? '#2e75b6' : col(lab(v))[0]), pointBorderColor: '#2e75b6', pointRadius: dates.length > 90 ? 2 : 4, tension: .3, spanGaps: false },
        // A dashed flat line at the average of the period
        { label: 'Average for this period (' + s.average + ')', data: dates.map(() => s.average), borderColor: '#666', borderDash: [6, 5], borderWidth: 1.5, pointRadius: 0, fill: false }
      ]
    },
    options: { ...base, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'AQI' } }, x: { ticks: { maxTicksLimit: 12, autoSkip: true } } } }
  });
  setFoot(await api('current?city=' + city));
}

/* ----- COMPARE: two or three cities side by side (UC-04) ----- */
async function compare() {
  const a = $('#ca').value, b = $('#cb').value, c = $('#cc').value;   // city C is optional (empty when "None")
  const d = await api('compare?a=' + encodeURIComponent(a) + '&b=' + encodeURIComponent(b) + (c ? '&c=' + encodeURIComponent(c) : ''));
  const list = [d.a, d.b, d.c].filter(Boolean), colors = ['#2e75b6', '#e08a1e', '#2e9e6b'];

  // One card per city with its AQI and level
  $('#cardC').hidden = !d.c;
  [['#cardA', d.a], ['#cardB', d.b], ['#cardC', d.c]].forEach(([id, x]) => {
    if (!x) return;
    const e = $(id);
    e.style.borderTopColor = col(x.label)[0];
    e.innerHTML = `<small>${x.city}</small><b>${x.aqi}</b>${tagHtml(x.label)}<small>Updated ${x.time}</small>`;
  });

  // Bar chart: for each pollutant, one bar per city
  mk('c_cmp', { type: 'bar', data: { labels: names(d.a.pollutants), datasets: list.map((x, i) => ({ label: x.city, data: Object.values(x.pollutants), backgroundColor: colors[i] })) }, options: base });
  setFoot(d.a, list);
}

/* ----- PREDICTION: the next two days (UC-05) ----- */
async function predict() {
  const city = $('#city').value, d = await api('predict?city=' + encodeURIComponent(city));
  const h = d.history, n = h.length, y = h.map(x => x.aqi), tm = d.tomorrow, da = d.day_after;

  // Three boxes: today (real), tomorrow (estimate, diamond), day after (estimate, square)
  [['#pt', d.today.aqi, d.today.label, 'Today (actual)'], ['#pm', tm.aqi, tm.label, 'Tomorrow ◆ (estimate)'], ['#pd', da.aqi, da.label, 'Day after ■ (estimate)']].forEach(([id, v, l, t]) => {
    const e = $(id);
    e.style.borderTopColor = col(l)[0];
    e.innerHTML = `<small>${t}</small><b>${v}</b>${tagHtml(l)}`;
  });

  // Chart data: the real days, then two empty slots for tomorrow and the day after
  const labels = [...h.map(x => fd(x.date)), fd(tm.date), fd(da.date)];
  const A = [...y, null, null];                                  // real values (the solid line)
  const T = Array(n + 2).fill(null), D = Array(n + 2).fill(null);
  T[n] = tm.aqi;                                                 // tomorrow: one point
  D[n + 1] = da.aqi;                                             // day after: one point

  // Plugin that draws the vertical TODAY line and the two labels next to the estimate points
  const marks = {
    id: 'marks',
    afterDatasetsDraw(ch) {
      const { ctx, chartArea: ca, scales: { x } } = ch, tx = x.getPixelForValue(n - 1);
      ctx.save();
      ctx.strokeStyle = '#888'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(tx, ca.top); ctx.lineTo(tx, ca.bottom); ctx.stroke();
      ctx.font = 'bold 11px system-ui'; ctx.textAlign = 'center'; ctx.fillStyle = cssv('--muted'); ctx.fillText('TODAY', tx, ca.top - 6);
      ctx.fillStyle = cssv('--text');
      [[1, n, 'Tomorrow', tm], [2, n + 1, 'Day after', da]].forEach(([di, i, nm, e]) => {
        const pt = ch.getDatasetMeta(di).data[i], tp = ch.getDatasetMeta(1).data[n];
        ctx.textAlign = i === n + 1 ? 'right' : 'center';
        // If the two estimate points are close, put the "Day after" label below its point so the texts do not overlap
        const close = i === n + 1 && Math.abs(pt.y - tp.y) < 26;
        ctx.fillText(`${nm}, ${fd(e.date)}, AQI ${e.aqi}`, pt.x + (i === n + 1 ? 14 : 0), close ? pt.y + 26 : pt.y - 16);
      });
      ctx.restore();
    }
  };
  mk('c_pred', {
    type: 'line', plugins: [marks],
    data: {
      labels,
      datasets: [
        { label: 'Actual (last ' + n + ' days)', data: A, borderColor: '#2e75b6', backgroundColor: '#2e75b6', pointStyle: 'circle', pointRadius: 4, tension: .2 },
        { label: 'Tomorrow (estimate)', data: T, showLine: false, pointStyle: 'rectRot', pointRadius: 9, backgroundColor: col(tm.label)[0], borderColor: '#333', borderWidth: 2 },
        { label: 'Day after (estimate)', data: D, showLine: false, pointStyle: 'rect', pointRadius: 8, backgroundColor: col(da.label)[0], borderColor: '#333', borderWidth: 2 }
      ]
    },
    options: { ...base, layout: { padding: { top: 24, right: 24 } }, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true } } } }
  });
  setFoot(await api('current?city=' + encodeURIComponent(city)));
}

/* ---------- 6. Menu, live data button and start-up ---------- */

let page = 'home';                                              // the page that is open now
const pages = { home, trends, history, compare, predict };     // page name -> function that fills it

// Empties a page when it could not load, so old numbers and charts do not stay on screen next to an error.
function clearPage(p) {
  const boxes = { home: ['#chips', '#aqinum', '#aqicat', '#facts', '#dos', '#tiles'], trends: ['#tstats'], history: ['#hcards', '#htable'], compare: ['#cardA', '#cardB', '#cardC'], predict: ['#pt', '#pm', '#pd'] };
  (boxes[p] || []).forEach(s => { const e = $(s); e.innerHTML = ''; e.style.background = ''; e.style.borderColor = ''; });
  if (p === 'home') { $('#banner').style.display = 'none'; $('#arc').style.strokeDasharray = '0 327'; $('#aqicard').style.borderTopColor = ''; }
  $('#stale').hidden = true;
  const cid = { home: 'c_home', trends: 'c_trend', history: 'c_hist', compare: 'c_cmp', predict: 'c_pred' }[p];
  if (charts[cid]) { charts[cid].destroy(); delete charts[cid]; }
}

// Loads the open page. If something changes while it is loading (for example the user picks another city
// quickly), it loads once more when the first load ends, so the screen always matches the last choice.
let running = false, again = false;
async function run() {
  if (running) { again = true; return; }
  running = true;
  do {
    again = false;
    showErr('');
    try { await pages[page](); } catch (e) { clearPage(page); showErr(e.message); }
  } while (again);
  running = false;
}

// Opens a page: shows its section, highlights its menu button, then loads its data.
function show(p) {
  page = p; $('#livelog').hidden = true;
  document.querySelectorAll('main section').forEach(s => s.hidden = s.id !== p);
  document.querySelectorAll('nav button').forEach(b => b.setAttribute('aria-current', b.dataset.p === p ? 'page' : 'false'));
  $('#citylabel').hidden = (p === 'compare');   // the Compare page has its own city menus
  const sec = $('#' + p); sec.classList.remove('in'); void sec.offsetWidth; sec.classList.add('in');   // restart the slide-in animation
  run();
}

// "Update live data" button: asks the backend to fetch new readings now (FR-01), then refreshes the page.
async function live() {
  const btn = $('#live'), log = $('#livelog');
  btn.disabled = true; btn.textContent = 'Updating...'; log.hidden = true;
  try {
    const r = await fetch('/api/refresh', { method: 'POST' }), j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || ('Request failed (' + r.status + ')'));
    // Cities with data first. Cities with no live station within 25 km are grouped into one line.
    const ok = j.results.filter(x => x.ok), bad = j.results.filter(x => !x.ok);
    const far = bad.filter(x => /no live station/.test(x.error)), other = bad.filter(x => !far.includes(x));
    const lines = [...ok.map(x => `${x.city}: AQI ${x.aqi} at ${x.time} (${x.station})`), ...other.map(x => `${x.city}: ${x.error}`)];
    if (far.length) lines.push(`No live station within 25 km for: ${far.map(x => x.city).join(', ')}. Their latest saved reading stays on screen.`);
    log.className = 'notice';
    log.textContent = `Live data fetched. ${j.saved} new reading${j.saved === 1 ? '' : 's'} saved.\n` + lines.join('\n');
    log.hidden = false;
    await loadCities();   // new cities may have data now
    await run();
  } catch (e) { log.className = 'notice bad'; log.textContent = e.message; log.hidden = false; }
  finally { btn.disabled = false; btn.textContent = '⟳ Update live data'; }
}

// Fills the city menus with the cities that have data. Keeps the user's choices when possible.
async function loadCities() {
  const cities = await api('cities'), opts = cities.map(c => `<option>${c.name}</option>`).join('');
  const keep = ['#city', '#ca', '#cb', '#cc'].map(id => $(id).value), has = n => cities.some(c => c.name === n);
  ['#city', '#ca', '#cb'].forEach(id => $(id).innerHTML = opts);
  $('#cc').innerHTML = '<option value="">None</option>' + opts;
  // Defaults: Kathmandu first, Pokhara as the second city on the Compare page
  const at = n => cities.findIndex(c => c.name === n), k = at('Kathmandu'), po = at('Pokhara');
  if (k >= 0) { $('#city').selectedIndex = k; $('#ca').selectedIndex = k; }
  if (po >= 0) $('#cb').selectedIndex = po; else { const o = cities.findIndex(c => c.name !== 'Kathmandu'); if (o >= 0) $('#cb').selectedIndex = o; }
  ['#city', '#ca', '#cb', '#cc'].forEach((id, i) => { if (keep[i] && has(keep[i])) $(id).value = keep[i]; });
}

// Runs once when the page opens: load cities, connect buttons and menus, open Home.
async function init() {
  try { await loadCities(); } catch (e) { showErr(e.message); }
  // Any change in a menu reloads the open page
  ['#city', '#range', '#ca', '#cb', '#cc', '#hyear', '#dfrom', '#dto'].forEach(id => $(id).addEventListener('change', run));
  $('#live').addEventListener('click', live);
  $('#hcsv').addEventListener('click', downloadCsv);
  $('#tlegend').innerHTML = $('#hlegend').innerHTML = legendHtml();
  // Every 5 minutes the Home page reloads by itself, so an open dashboard stays fresh
  setInterval(() => { if (page === 'home' && !document.hidden) run(); }, 300000);
  document.querySelectorAll('nav button').forEach(b => b.addEventListener('click', () => show(b.dataset.p)));
  show('home');
}
init();