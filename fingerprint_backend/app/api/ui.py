from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fingerprint SDK Tester</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; }

header { background: #161b22; border-bottom: 1px solid #30363d; padding: 14px 20px; display: flex; align-items: center; gap: 12px; }
header h1 { font-size: 17px; font-weight: 700; }
.badge { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
.badge-live { background: #1a7a3c; color: #fff; }
.badge-live.on { animation: pulse 1.4s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

.layout { display: grid; grid-template-columns: 1fr 400px; height: calc(100vh - 51px); }

/* ── Camera ── */
.cam-panel { position: relative; background: #000; overflow: hidden; }
#video { width: 100%; height: 100%; object-fit: cover; display: block; }
canvas { display: none; }

.cam-overlay { position: absolute; inset: 0; pointer-events: none; display: flex; align-items: center; justify-content: center; }
.scan-frame { width: 340px; height: 260px; border-radius: 14px; border: 2px solid #30363d; position: relative; transition: all 0.3s; }
.scan-frame.ready   { border-color: #2ecc71; box-shadow: 0 0 30px rgba(46,204,113,0.35); }
.scan-frame.warn    { border-color: #f59e0b; box-shadow: 0 0 20px rgba(245,158,11,0.3); }
.scan-frame.error   { border-color: #ef4444; box-shadow: 0 0 20px rgba(239,68,68,0.3); }

.corner { position: absolute; width: 20px; height: 20px; border-color: inherit; border-style: solid; border-width: 0; }
.corner.tl { top:-2px; left:-2px;  border-top-width:3px; border-left-width:3px;  border-top-left-radius:5px; }
.corner.tr { top:-2px; right:-2px; border-top-width:3px; border-right-width:3px; border-top-right-radius:5px; }
.corner.bl { bottom:-2px; left:-2px;  border-bottom-width:3px; border-left-width:3px;  border-bottom-left-radius:5px; }
.corner.br { bottom:-2px; right:-2px; border-bottom-width:3px; border-right-width:3px; border-bottom-right-radius:5px; }

/* Guidance bar — full-width at bottom of camera, always on top */
.guidance-box { position: absolute; bottom: 0; left: 0; right: 0; z-index: 20;
  padding: 13px 20px; display: flex; align-items: center; gap: 10px;
  transition: background 0.3s, border-color 0.3s; border-top: 2px solid transparent; }
.guidance-box.ok   { background: rgba(26,122,60,0.92); border-color: #2ecc71; }
.guidance-box.warn { background: rgba(30,24,5,0.92);   border-color: #f59e0b; }
.guidance-box.err  { background: rgba(35,10,10,0.92);  border-color: #ef4444; }
.guidance-icon { font-size: 18px; flex-shrink: 0; }
.guidance-text { font-size: 14px; font-weight: 700; line-height: 1.3; }
.guidance-box.ok   .guidance-text { color: #d4f5e2; }
.guidance-box.warn .guidance-text { color: #fde68a; }
.guidance-box.err  .guidance-text { color: #fca5a5; }

.live-dot-wrap { position: absolute; top: 16px; left: 16px; z-index: 10; display: flex; align-items: center;
  gap: 8px; background: rgba(13,17,23,0.85); padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; }
.live-dot { width: 8px; height: 8px; background: #ef4444; border-radius: 50%; animation: blink 1s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.15} }

.quality-hud { position: absolute; top: 16px; right: 16px; z-index: 10; background: rgba(13,17,23,0.88);
  border: 1px solid #30363d; border-radius: 10px; padding: 10px 14px; min-width: 120px; }
.hud-label { font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 4px; }
.hud-score { font-size: 26px; font-weight: 800; line-height: 1; }
.hud-score.good { color: #2ecc71; } .hud-score.ok { color: #f59e0b; } .hud-score.bad { color: #ef4444; }
.hud-bar { height: 4px; background: #21262d; border-radius: 2px; margin-top: 6px; overflow: hidden; }
.hud-fill { height: 100%; border-radius: 2px; transition: width 0.4s, background 0.4s; }

/* ── Control panel ── */
.ctrl-panel { background: #161b22; border-left: 1px solid #30363d; display: flex; flex-direction: column; overflow-y: auto; }
.tabs { display: flex; border-bottom: 1px solid #30363d; flex-shrink: 0; }
.tab { flex: 1; padding: 13px 8px; text-align: center; font-size: 12px; font-weight: 700; color: #8b949e; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tab.active { color: #2ecc71; border-bottom-color: #2ecc71; }
.tab-content { display: none; padding: 18px; }
.tab-content.active { display: block; }

label { display: block; font-size: 11px; font-weight: 700; color: #8b949e; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 6px; }
select, input[type="text"] { width: 100%; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; color: #e6edf3; padding: 9px 12px; font-size: 13px; outline: none; margin-bottom: 14px; }
select:focus, input:focus { border-color: #2ecc71; }

.btn { width: 100%; padding: 11px; border: none; border-radius: 9px; font-size: 13px; font-weight: 700; cursor: pointer; margin-bottom: 8px; transition: all 0.2s; }
.btn-primary  { background: #1a7a3c; color: #fff; }
.btn-primary:hover  { background: #1f9649; }
.btn-primary:disabled { background: #21262d; color: #484f58; cursor: not-allowed; }
.btn-secondary { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; }
.btn-secondary:hover { background: #30363d; }
.btn-stop { background: #da3633; color: #fff; }
.btn-stop:hover { background: #f85149; }

/* 4-finger tile grid */
.finger-tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px; }
.ftile { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 10px 12px; transition: all 0.3s; }
.ftile.success { border-color: #2ecc71; background: #1a7a3c18; }
.ftile.failed  { border-color: #ef4444; background: #da363318; }
.ftile.active  { border-color: #58a6ff; background: #1f2d3d; }
.ft-name  { font-size: 11px; font-weight: 700; color: #8b949e; text-transform: uppercase; letter-spacing: 0.6px; }
.ft-score { font-size: 22px; font-weight: 800; line-height: 1.1; margin: 4px 0 2px; }
.ft-score.good { color: #2ecc71; } .ft-score.ok { color: #f59e0b; } .ft-score.bad { color: #ef4444; } .ft-score.none { color: #484f58; }
.ft-bar  { height: 3px; background: #21262d; border-radius: 2px; overflow: hidden; margin-bottom: 5px; }
.ft-fill { height: 100%; border-radius: 2px; transition: width 0.4s, background 0.4s; }
.ft-status { font-size: 11px; font-weight: 700; }
.ft-status.ok  { color: #2ecc71; } .ft-status.err { color: #f85149; } .ft-status.wait { color: #484f58; }

.success-banner { background: #1a7a3c22; border: 1px solid #1a7a3c; border-radius: 10px; padding: 14px; text-align: center; margin-bottom: 14px; }
.success-banner h2 { color: #2ecc71; font-size: 16px; margin-bottom: 4px; }
.success-banner p  { color: #8b949e; font-size: 12px; }

.result-card { background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 12px; margin-bottom: 10px; }
.result-card h3 { font-size: 10px; font-weight: 700; color: #8b949e; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; }
.metric-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.metric-label { font-size: 12px; color: #8b949e; }
.metric-value { font-size: 12px; font-weight: 700; }
.pill { display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 700; }
.pill-green  { background: #1a7a3c22; color: #2ecc71; border: 1px solid #1a7a3c44; }
.pill-red    { background: #da363322; color: #f85149; border: 1px solid #da363344; }
.pill-yellow { background: #f59e0b22; color: #f59e0b; border: 1px solid #f59e0b44; }
.pill-gray   { background: #21262d;   color: #8b949e; border: 1px solid #30363d; }

.divider { border: none; border-top: 1px solid #21262d; margin: 14px 0; }
.log { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 10px; font-family: monospace; font-size: 11px; color: #8b949e; max-height: 130px; overflow-y: auto; line-height: 1.7; }
.log .ok   { color: #2ecc71; } .log .err { color: #f85149; } .log .info { color: #58a6ff; }

@media (max-width: 768px) { .layout { grid-template-columns: 1fr; grid-template-rows: 55vh 1fr; } }
</style>
</head>
<body>

<header>
  <h1>Fingerprint SDK — 4-Finger Capture</h1>
  <span class="badge badge-live" id="liveBadge">LIVE</span>
</header>

<div class="layout">
  <!-- Camera side -->
  <div class="cam-panel">
    <video id="video" autoplay playsinline muted></video>
    <canvas id="canvas"></canvas>

    <div class="cam-overlay">
      <div class="scan-frame" id="scanFrame">
        <div class="corner tl"></div><div class="corner tr"></div>
        <div class="corner bl"></div><div class="corner br"></div>
      </div>
    </div>

    <div class="live-dot-wrap">
      <div class="live-dot" id="liveDot"></div>
      <span id="liveLabel">READY</span>
    </div>

    <div class="quality-hud">
      <div class="hud-label">Avg Quality</div>
      <div class="hud-score bad" id="hudScore">—</div>
      <div class="hud-bar"><div class="hud-fill" id="hudFill" style="width:0%;background:#ef4444"></div></div>
    </div>

    <div class="guidance-box err" id="guidanceBox">
      <span class="guidance-icon" id="guidanceIcon">✋</span>
      <span class="guidance-text" id="guidanceText">Point your hand at the camera</span>
    </div>
  </div>

  <!-- Control panel -->
  <div class="ctrl-panel">
    <div class="tabs">
      <div class="tab active" onclick="switchTab('capture')">Capture</div>
      <div class="tab" onclick="switchTab('enroll')">Enroll</div>
      <div class="tab" onclick="switchTab('verify')">Verify</div>
    </div>

    <!-- TAB: Capture -->
    <div class="tab-content active" id="tab-capture">

      <label>Hand</label>
      <select id="handSelect">
        <option value="RIGHT">Right Hand</option>
        <option value="LEFT">Left Hand</option>
      </select>

      <button class="btn btn-primary" id="startBtn"  onclick="startLive()">Start Live Analysis</button>
      <button class="btn btn-stop"    id="stopBtn"   onclick="stopLive()" style="display:none">Stop</button>
      <button class="btn btn-secondary" onclick="startCamera()">Restart Camera</button>

      <hr class="divider">

      <!-- 4 finger tiles -->
      <div class="finger-tiles" id="fingerTiles"></div>

      <!-- Success banner (shown when all 4 done) -->
      <div id="successBanner" class="success-banner" style="display:none">
        <h2>All 4 fingers captured!</h2>
        <p id="successMsg"></p>
      </div>
    </div>

    <!-- TAB: Enroll -->
    <div class="tab-content" id="tab-enroll">
      <label>User ID</label>
      <input type="text" id="enrollUserId" placeholder="e.g. user_001">

      <label>Hand</label>
      <select id="enrollHand">
        <option value="RIGHT">Right Hand</option>
        <option value="LEFT">Left Hand</option>
      </select>

      <button class="btn btn-primary" onclick="captureForEnroll()">Capture 4 Fingers</button>
      <button class="btn btn-primary" id="enrollSubmitBtn" onclick="submitEnroll()" disabled>Submit Enrollment</button>

      <hr class="divider">
      <div class="log" id="enrollLog">Ready...<br></div>
    </div>

    <!-- TAB: Verify -->
    <div class="tab-content" id="tab-verify">
      <label>User ID</label>
      <input type="text" id="verifyUserId" placeholder="e.g. user_001">

      <label>Finger</label>
      <select id="verifyFinger">
        <option value="RIGHT_INDEX">Right Index</option>
        <option value="RIGHT_MIDDLE">Right Middle</option>
        <option value="RIGHT_RING">Right Ring</option>
        <option value="RIGHT_LITTLE">Right Little</option>
        <option value="LEFT_INDEX">Left Index</option>
        <option value="LEFT_MIDDLE">Left Middle</option>
        <option value="LEFT_RING">Left Ring</option>
        <option value="LEFT_LITTLE">Left Little</option>
      </select>

      <button class="btn btn-primary" onclick="captureAndVerify()">Capture & Verify</button>

      <hr class="divider">
      <div id="verifyResult" style="display:none">
        <div class="result-card" id="verifyCard">
          <h3>Match Result</h3>
          <div class="metric-row">
            <span class="metric-label">Match</span>
            <span id="v-match" class="pill pill-gray">—</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">Confidence</span>
            <span id="v-conf" class="metric-value" style="color:#8b949e">—</span>
          </div>
          <div style="margin-top:8px"><div class="hud-bar"><div class="hud-fill" id="v-bar" style="width:0%"></div></div></div>
          <div style="margin-top:8px;font-size:12px;color:#8b949e" id="v-msg"></div>
        </div>
      </div>
      <div class="log" id="verifyLog">Ready...<br></div>
    </div>
  </div>
</div>

<script>
const BASE = window.location.origin;
let stream        = null;
let liveInterval  = null;
let isAnalyzing   = false;
let capturedAll   = {};   // finger_id → {template, quality_score}
let streak        = {};   // finger key → consecutive success count
const HOLD_FRAMES = 3;    // need 3 good frames in a row (~4 seconds at 1.3s interval)

const FINGER_KEYS = ['INDEX','MIDDLE','RING','LITTLE'];
const FINGER_LABEL = { INDEX:'Index', MIDDLE:'Middle', RING:'Ring', LITTLE:'Little' };

// ── Camera ────────────────────────────────────────────────────────────────────
async function startCamera() {
  try {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }
    });
    document.getElementById('video').srcObject = stream;
    setFrame('default');
    setGuidance('Point your hand at the camera', 'warn');
  } catch(e) {
    setFrame('error');
    setGuidance('Camera access denied', 'err');
  }
}

function captureFrame() {
  const v = document.getElementById('video');
  const c = document.getElementById('canvas');
  c.width  = v.videoWidth  || 640;
  c.height = v.videoHeight || 480;
  c.getContext('2d').drawImage(v, 0, 0);
  return c.toDataURL('image/jpeg', 0.88).split(',')[1];
}

// ── 4-finger live loop ────────────────────────────────────────────────────────
function startLive() {
  capturedAll = {};
  streak      = {};
  buildTiles(document.getElementById('handSelect').value);
  resetTiles();
  document.getElementById('successBanner').style.display = 'none';
  document.getElementById('startBtn').style.display = 'none';
  document.getElementById('stopBtn').style.display  = 'block';
  document.getElementById('liveLabel').textContent  = 'ANALYZING';
  document.getElementById('liveBadge').classList.add('on');
  liveInterval = setInterval(runAnalysis, 1300);
  runAnalysis();
}

function stopLive() {
  clearInterval(liveInterval);
  liveInterval = null;
  document.getElementById('startBtn').style.display = 'block';
  document.getElementById('stopBtn').style.display  = 'none';
  document.getElementById('liveLabel').textContent  = 'PAUSED';
  document.getElementById('liveBadge').classList.remove('on');
}

async function runAnalysis() {
  if (isAnalyzing) return;
  isAnalyzing = true;

  const hand = document.getElementById('handSelect').value;
  const b64  = captureFrame();

  try {
    const res  = await fetch(BASE + '/api/capture/multi', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transaction_id: Date.now().toString(),
                             image_base64: b64, hand })
    });
    const data = await res.json();

    // Guidance banner
    if (data.guidance) {
      setGuidance(data.guidance, 'warn');
    } else if (data.overall_status === 'success') {
      setGuidance('Hold steady — capturing!', 'ok');
    } else {
      setGuidance('Keep fingers flat and spread', 'warn');
    }

    // Update each tile with streak logic
    let totalQ = 0, countQ = 0;
    const results = data.results || [];
    results.forEach(r => {
      const key = r.finger_id.replace(hand + '_', '');
      if (r.quality_score > 0) { totalQ += r.quality_score; countQ++; }

      // Already locked in — keep tile green, skip streak logic
      if (capturedAll[r.finger_id]) return;

      if (r.status === 'success' && r.template) {
        streak[key] = (streak[key] || 0) + 1;
        if (streak[key] >= HOLD_FRAMES) {
          // Lock in this finger
          capturedAll[r.finger_id] = { finger_id: r.finger_id, template: r.template, quality_score: r.quality_score };
          lockTile(key, r.quality_score);
        } else {
          // Show hold progress
          updateTileHolding(key, r.quality_score, streak[key]);
        }
      } else {
        streak[key] = 0;
        updateTile(key, r);
      }
    });

    // Update HUD avg quality
    if (countQ > 0) updateHUD(totalQ / countQ);

    // Frame border
    if (data.overall_status === 'success') {
      setFrame('ready');
    } else if (data.overall_status === 'partial') {
      setFrame('warn');
    } else {
      setFrame('error');
    }

    // Auto-stop when all 4 captured
    const capturedCount = Object.keys(capturedAll).length;
    if (capturedCount >= 4) {
      stopLive();
      showAllCaptured();
    }

  } catch(e) {
    setGuidance('Connection error — check server', 'err');
    setFrame('error');
  } finally {
    isAnalyzing = false;
  }
}

// ── Tile management ───────────────────────────────────────────────────────────
function buildTiles(hand) {
  const grid = document.getElementById('fingerTiles');
  grid.innerHTML = '';
  FINGER_KEYS.forEach(key => {
    const fid = hand + '_' + key;
    grid.innerHTML += `
      <div class="ftile" id="tile-${key}">
        <div class="ft-name">${FINGER_LABEL[key]}</div>
        <div class="ft-score none" id="ts-${key}">—</div>
        <div class="ft-bar"><div class="ft-fill" id="tb-${key}" style="width:0%"></div></div>
        <div class="ft-status wait" id="tst-${key}">Waiting...</div>
      </div>`;
  });
}

function resetTiles() {
  FINGER_KEYS.forEach(key => {
    const tile = document.getElementById('tile-' + key);
    if (tile) { tile.className = 'ftile active'; }
    const sc = document.getElementById('ts-' + key);
    if (sc) { sc.textContent = '—'; sc.className = 'ft-score none'; }
    const fill = document.getElementById('tb-' + key);
    if (fill) { fill.style.width = '0%'; }
    const st = document.getElementById('tst-' + key);
    if (st) { st.textContent = 'Analyzing...'; st.className = 'ft-status wait'; }
  });
}

function updateTile(key, r) {
  const tile = document.getElementById('tile-' + key);
  const sc   = document.getElementById('ts-' + key);
  const fill = document.getElementById('tb-' + key);
  const st   = document.getElementById('tst-' + key);
  if (!tile) return;

  const q     = r.quality_score || 0;
  const color = q > 70 ? '#2ecc71' : q > 40 ? '#f59e0b' : '#ef4444';
  const cls   = q > 70 ? 'good' : q > 40 ? 'ok' : 'bad';

  sc.textContent = q > 0 ? q.toFixed(0) : '—';
  sc.className   = 'ft-score ' + (q > 0 ? cls : 'none');
  fill.style.width      = Math.min(q, 100) + '%';
  fill.style.background = color;

  if (r.status === 'success') {
    tile.className  = 'ftile success';
    st.textContent  = '✓ Captured';
    st.className    = 'ft-status ok';
  } else if (r.error_code === 'FINGER_NOT_DETECTED' || r.error_code === 'NO_HAND_DETECTED') {
    tile.className  = 'ftile';
    st.textContent  = 'Not visible';
    st.className    = 'ft-status wait';
    sc.textContent  = '—';
    sc.className    = 'ft-score none';
  } else {
    tile.className  = 'ftile failed';
    st.textContent  = r.error_code || 'Failed';
    st.className    = 'ft-status err';
  }
}

function showAllCaptured() {
  const count = Object.keys(capturedAll).length;
  const avgQ  = Object.values(capturedAll).reduce((s,r) => s + r.quality_score, 0) / count;
  document.getElementById('successBanner').style.display = 'block';
  document.getElementById('successMsg').textContent =
    `${count} fingers captured. Avg quality: ${avgQ.toFixed(1)}/100. Go to Enroll tab.`;
  setFrame('ready');
  setGuidance('All fingers captured!', 'ok');
}

// ── HUD + Frame ───────────────────────────────────────────────────────────────
function updateHUD(score) {
  const el   = document.getElementById('hudScore');
  const fill = document.getElementById('hudFill');
  el.textContent = score.toFixed(0);
  el.className   = 'hud-score ' + (score > 70 ? 'good' : score > 40 ? 'ok' : 'bad');
  fill.style.width      = score + '%';
  fill.style.background = score > 70 ? '#2ecc71' : score > 40 ? '#f59e0b' : '#ef4444';
}

function setFrame(state) {
  const cls = { default:'', ready:' ready', warn:' warn', error:' error' };
  document.getElementById('scanFrame').className = 'scan-frame' + (cls[state] || '');
}

function setGuidance(msg, type) {
  const icons = { ok: '✅', warn: '⚠️', err: '❌' };
  document.getElementById('guidanceBox').className   = 'guidance-box ' + (type || 'warn');
  document.getElementById('guidanceIcon').textContent = icons[type] || '⚠️';
  document.getElementById('guidanceText').textContent = msg;
}

function lockTile(key, score) {
  const tile = document.getElementById('tile-' + key);
  const st   = document.getElementById('tst-' + key);
  const sc   = document.getElementById('ts-' + key);
  const fill = document.getElementById('tb-' + key);
  if (!tile) return;
  tile.className  = 'ftile success';
  sc.textContent  = score.toFixed(0);
  sc.className    = 'ft-score good';
  fill.style.width = Math.min(score, 100) + '%';
  fill.style.background = '#2ecc71';
  st.textContent  = '✓ Captured';
  st.className    = 'ft-status ok';
}

function updateTileHolding(key, score, count) {
  const tile = document.getElementById('tile-' + key);
  const st   = document.getElementById('tst-' + key);
  const sc   = document.getElementById('ts-' + key);
  const fill = document.getElementById('tb-' + key);
  if (!tile) return;
  const dots = '●'.repeat(count) + '○'.repeat(HOLD_FRAMES - count);
  tile.className  = 'ftile active';
  sc.textContent  = score.toFixed(0);
  sc.className    = 'ft-score ' + (score > 70 ? 'good' : 'ok');
  fill.style.width = Math.min(score, 100) + '%';
  fill.style.background = '#58a6ff';
  st.textContent  = 'Hold still ' + dots;
  st.className    = 'ft-status wait';
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(name) {
  ['capture','enroll','verify'].forEach((n, i) => {
    document.querySelectorAll('.tab')[i].classList.toggle('active', n === name);
    document.getElementById('tab-' + n).classList.toggle('active', n === name);
  });
}

// ── Enroll ────────────────────────────────────────────────────────────────────
async function captureForEnroll() {
  const hand = document.getElementById('enrollHand').value;
  logMsg('enrollLog', 'Capturing ' + hand + ' hand...', 'info');

  const b64 = captureFrame();
  try {
    const res  = await fetch(BASE + '/api/capture/multi', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transaction_id: Date.now().toString(),
                             image_base64: b64, hand })
    });
    const data = await res.json();
    const ok   = [];
    capturedAll = {};

    (data.results || []).forEach(r => {
      if (r.status === 'success' && r.template) {
        capturedAll[r.finger_id] = { finger_id: r.finger_id, template: r.template, quality_score: r.quality_score };
        ok.push(r.finger_id.replace(hand + '_', ''));
        logMsg('enrollLog', r.finger_id + ' Q=' + r.quality_score.toFixed(1), 'ok');
      } else {
        logMsg('enrollLog', r.finger_id + ' FAIL: ' + (r.error_code || '?'), 'err');
      }
    });

    if (ok.length > 0) {
      document.getElementById('enrollSubmitBtn').disabled = false;
      logMsg('enrollLog', 'Ready to enroll: ' + ok.join(', '), 'ok');
    } else {
      logMsg('enrollLog', 'No fingers captured — ' + (data.guidance || 'try again'), 'err');
    }
  } catch(e) { logMsg('enrollLog', 'Error: ' + e.message, 'err'); }
}

async function submitEnroll() {
  const uid     = document.getElementById('enrollUserId').value.trim();
  const fingers = Object.values(capturedAll);
  if (!uid)            { logMsg('enrollLog', 'Enter a User ID', 'err'); return; }
  if (!fingers.length) { logMsg('enrollLog', 'Capture fingers first', 'err'); return; }

  logMsg('enrollLog', 'Enrolling ' + uid + ' (' + fingers.length + ' fingers)...', 'info');
  try {
    const res  = await fetch(BASE + '/api/enroll', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: uid, transaction_id: Date.now().toString(), fingers })
    });
    const data = await res.json();
    logMsg('enrollLog', 'Enrolled! ID: ' + data.enrollment_id, 'ok');
    logMsg('enrollLog', 'Fingers: ' + data.fingers_enrolled.join(', '), 'ok');
    capturedAll = {};
    document.getElementById('enrollSubmitBtn').disabled = true;
  } catch(e) { logMsg('enrollLog', 'Error: ' + e.message, 'err'); }
}

// ── Verify ────────────────────────────────────────────────────────────────────
async function captureAndVerify() {
  const uid = document.getElementById('verifyUserId').value.trim();
  const fid = document.getElementById('verifyFinger').value;
  if (!uid) { logMsg('verifyLog', 'Enter a User ID', 'err'); return; }

  logMsg('verifyLog', 'Verifying ' + fid + ' for ' + uid, 'info');
  setGuidance('Capturing for verification...', 'warn');
  const b64 = captureFrame();

  try {
    const res  = await fetch(BASE + '/api/verify', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: uid, transaction_id: Date.now().toString(),
                             fingers: [{ finger_id: fid, image_base64: b64 }] })
    });
    const data  = await res.json();
    const match = data.match;
    const conf  = (data.confidence || 0) * 100;

    document.getElementById('verifyResult').style.display = 'block';
    document.getElementById('v-match').textContent  = match ? 'MATCHED ✓' : 'NO MATCH';
    document.getElementById('v-match').className    = 'pill ' + (match ? 'pill-green' : 'pill-red');
    document.getElementById('v-conf').textContent   = conf.toFixed(1) + '%';
    document.getElementById('v-bar').style.width    = conf + '%';
    document.getElementById('v-bar').style.background = match ? '#2ecc71' : '#ef4444';
    document.getElementById('v-msg').textContent    = data.message || '';
    document.getElementById('verifyCard').style.borderColor = match ? '#2ecc71' : '#da3633';

    setFrame(match ? 'ready' : 'error');
    setGuidance(match ? 'Identity verified!' : 'No match found', match ? 'ok' : 'err');
    logMsg('verifyLog', (match ? 'MATCH' : 'NO MATCH') + '  ' + conf.toFixed(1) + '%', match ? 'ok' : 'err');
  } catch(e) {
    logMsg('verifyLog', 'Error: ' + e.message, 'err');
    setGuidance('Verification error', 'err');
  }
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function logMsg(logId, msg, type) {
  const log = document.getElementById(logId);
  const s   = document.createElement('span');
  s.className   = type || 'info';
  s.textContent = new Date().toLocaleTimeString('en',{hour12:false}) + '  ' + msg + '\\n';
  log.appendChild(s);
  log.scrollTop = log.scrollHeight;
}

// Build initial tiles and start camera
buildTiles('RIGHT');
startCamera();
</script>
</body>
</html>"""
