const pad = n => String(n).padStart(2, '0');
const formatCountdown = totalSeconds => {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return `${h}:${pad(m)}:${pad(s)}`;
};
const formatStopwatch = ms => {
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const tenths = Math.floor((ms % 1000) / 100);
  return `${pad(m)}:${pad(s)}.${tenths}`;
};

document.addEventListener('DOMContentLoaded', () => {
  const moodForm = document.getElementById('moodForm');
  if (!moodForm) return;
  moodForm.addEventListener('submit', () => {
    const now = new Date();
    document.getElementById('clientTime').value =
      now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    document.getElementById('clientDate').value =
      `${now.getMonth() + 1}/${now.getDate()}/${now.getFullYear()}`;
  });
});

function switchTab(name, btn) {
  document.querySelectorAll('.timer-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.timer-tab').forEach(b => b.classList.remove('active'));
  document.getElementById(`panel-${name}`).classList.add('active');
  btn.classList.add('active');
}

function toggleFullPage(editorId, siblingId) {
  const editor = document.getElementById(editorId);
  const sibling = siblingId ? document.getElementById(siblingId) : null;
  const expanded = editor.classList.toggle('fullpage');
  if (sibling) sibling.classList.toggle('hide-list', expanded);
  const btn = editor.querySelector('.expand-btn');
  btn.textContent = expanded ? '\u2715 Close full page' : '\u26F6 Full page';
}

const countdown = { interval: null, total: 0, left: 0, running: false };
function cdPreset(seconds) {
  countdown.left = countdown.total = seconds;
  document.getElementById('cdH').value = Math.floor(seconds / 3600) || '';
  document.getElementById('cdM').value = Math.floor((seconds % 3600) / 60) || '';
  document.getElementById('cdS').value = seconds % 60 || '';
  cdDraw();
}
function cdStart() {
  if (countdown.running) return;
  if (!countdown.left) {
    const h = parseInt(document.getElementById('cdH').value) || 0;
    const m = parseInt(document.getElementById('cdM').value) || 0;
    const s = parseInt(document.getElementById('cdS').value) || 0;
    countdown.left = countdown.total = h * 3600 + m * 60 + s;
  }
  if (!countdown.left) return;
  countdown.running = true;
  countdown.interval = setInterval(() => {
    countdown.left--;
    cdDraw();
    if (countdown.left <= 0) {
      cdPause();
      countdown.left = 0;
      alert('Timer done!');
    }
  }, 1000);
}
function cdPause() {
  clearInterval(countdown.interval);
  countdown.running = false;
}
function cdReset() {
  cdPause();
  countdown.left = countdown.total;
  cdDraw();
}
function cdDraw() {
  document.getElementById('cdDisplay').textContent = formatCountdown(countdown.left);
  const pct = countdown.total ? (countdown.total - countdown.left) / countdown.total * 100 : 0;
  document.getElementById('cdProgress').style.width = `${pct}%`;
}

const stopwatch = { interval: null, ms: 0, running: false, laps: [] };
function swStart() {
  if (stopwatch.running) return;
  stopwatch.running = true;
  const startedAt = Date.now() - stopwatch.ms;
  stopwatch.interval = setInterval(() => {
    stopwatch.ms = Date.now() - startedAt;
    document.getElementById('swDisplay').textContent = formatStopwatch(stopwatch.ms);
  }, 100);
}
function swPause() {
  clearInterval(stopwatch.interval);
  stopwatch.running = false;
}
function swLap() {
  if (!stopwatch.running) return;
  stopwatch.laps.push(stopwatch.ms);
  const li = document.createElement('li');
  li.textContent = `Lap ${stopwatch.laps.length}: ${formatStopwatch(stopwatch.ms)}`;
  document.getElementById('lapList').prepend(li);
}
function swReset() {
  swPause();
  stopwatch.ms = 0;
  stopwatch.laps = [];
  document.getElementById('swDisplay').textContent = '00:00.0';
  document.getElementById('lapList').innerHTML = '';
}

const alarms = [];
setInterval(() => {
  const now = new Date();
  const current = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  alarms.forEach(a => {
    if (!a.fired && a.time === current) {
      a.fired = true;
      alert(`Alarm: ${a.label || a.time}`);
      renderAlarms();
    }
  });
}, 10000);
function addAlarm() {
  const time = document.getElementById('alarmTime').value;
  const label = document.getElementById('alarmLabel').value;
  if (!time) return;
  alarms.push({ time, label, fired: false });
  renderAlarms();
  document.getElementById('alarmTime').value = '';
  document.getElementById('alarmLabel').value = '';
}
function removeAlarm(i) {
  alarms.splice(i, 1);
  renderAlarms();
}
function renderAlarms() {
  const list = document.getElementById('alarmList');
  list.innerHTML = '';
  alarms.forEach((alarm, i) => {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:.5rem;padding:.4rem 0;border-bottom:1px solid var(--border)';
    row.innerHTML = `<span style="font-size:1.1rem">🔔</span><b>${alarm.time}</b>`;
    if (alarm.label) row.appendChild(makeSpan(alarm.label, 'var(--muted)'));
    if (alarm.fired) row.appendChild(makeSpan('(fired)', 'var(--success)'));
    const removeBtn = document.createElement('button');
    removeBtn.className = 'icon-btn';
    removeBtn.style.marginLeft = 'auto';
    removeBtn.textContent = '✕';
    removeBtn.onclick = () => removeAlarm(i);
    row.appendChild(removeBtn);

    list.appendChild(row);
  });
}
function makeSpan(text, color) {
  const span = document.createElement('span');
  span.style.color = color;
  span.textContent = text;
  return span;
}