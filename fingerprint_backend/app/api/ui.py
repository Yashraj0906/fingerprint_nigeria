from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fingerprint SDK — Live Demo</title>


<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;height:100vh;overflow:hidden}

header{background:#161b22;border-bottom:1px solid #30363d;padding:10px 18px;display:flex;align-items:center;gap:12px;height:46px}
header h1{font-size:14px;font-weight:700;flex:1}
.hdr-txn{font-size:10px;color:#484f58;font-family:monospace}
.badge{font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;background:#1a7a3c;color:#fff;flex-shrink:0}
.badge.on{animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

.layout{display:grid;grid-template-columns:1fr 460px;height:calc(100vh - 46px)}

/* Camera */
.cam-panel{position:relative;background:#000;overflow:hidden}
#video{width:100%;height:100%;object-fit:cover;display:block}
#overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
#scratchCanvas{display:none}

/* Scan guide frame */
.scan-guide{position:absolute;top:50%;left:50%;transform:translate(-50%,-55%);
  width:360px;height:260px;pointer-events:none;z-index:5}
.sg-corner{position:absolute;width:24px;height:24px;border-color:#ffffff88;border-style:solid;border-width:0}
.sg-tl{top:0;left:0;border-top-width:3px;border-left-width:3px;border-top-left-radius:5px}
.sg-tr{top:0;right:0;border-top-width:3px;border-right-width:3px;border-top-right-radius:5px}
.sg-bl{bottom:0;left:0;border-bottom-width:3px;border-left-width:3px;border-bottom-left-radius:5px}
.sg-br{bottom:0;right:0;border-bottom-width:3px;border-right-width:3px;border-bottom-right-radius:5px}
.scan-guide.ok .sg-corner{border-color:#2ecc71}
.scan-guide.warn .sg-corner{border-color:#f59e0b}
.scan-guide.err .sg-corner{border-color:#ef4444}

/* Guidance bar */
.guidance{position:absolute;bottom:0;left:0;right:0;z-index:20;padding:11px 16px;
  display:flex;align-items:center;gap:9px;border-top:2px solid transparent;transition:all .3s}
.guidance.ok{background:rgba(26,122,60,.93);border-color:#2ecc71}
.guidance.warn{background:rgba(30,24,5,.93);border-color:#f59e0b}
.guidance.err{background:rgba(35,10,10,.93);border-color:#ef4444}
.g-icon{font-size:16px;flex-shrink:0}
.g-text{font-size:13px;font-weight:700}
.guidance.ok .g-text{color:#d4f5e2}
.guidance.warn .g-text{color:#fde68a}
.guidance.err .g-text{color:#fca5a5}

.live-wrap{position:absolute;top:12px;left:12px;z-index:10;display:flex;align-items:center;
  gap:7px;background:rgba(13,17,23,.86);padding:4px 11px;border-radius:20px;font-size:11px;font-weight:700}
.live-dot{width:8px;height:8px;background:#ef4444;border-radius:50%;animation:blink 1s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.15}}

.q-hud{position:absolute;top:12px;right:12px;z-index:10;background:rgba(13,17,23,.88);
  border:1px solid #30363d;border-radius:10px;padding:9px 13px;min-width:108px;text-align:center}
.q-label{font-size:9px;font-weight:700;color:#8b949e;letter-spacing:.8px;text-transform:uppercase;margin-bottom:2px}
.q-big{font-size:26px;font-weight:800;line-height:1}
.q-big.good{color:#2ecc71}.q-big.ok{color:#f59e0b}.q-big.bad{color:#ef4444}
.q-bar{height:3px;background:#21262d;border-radius:2px;margin-top:5px;overflow:hidden}
.q-fill{height:100%;border-radius:2px;transition:width .4s,background .4s}

/* Right panel */
.ctrl{background:#161b22;border-left:1px solid #30363d;display:flex;flex-direction:column;overflow:hidden}
.tabs{display:flex;border-bottom:1px solid #30363d;flex-shrink:0}
.tab{flex:1;padding:11px 4px;text-align:center;font-size:11px;font-weight:700;color:#8b949e;
  cursor:pointer;border-bottom:2px solid transparent;transition:all .2s}
.tab.active{color:#2ecc71;border-bottom-color:#2ecc71}
.pane{display:none;padding:14px;overflow-y:auto;flex:1;flex-direction:column;gap:10px}
.pane.active{display:flex}

label{display:block;font-size:10px;font-weight:700;color:#8b949e;letter-spacing:.8px;text-transform:uppercase;margin-bottom:4px}
select,input[type=text]{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:7px;
  color:#e6edf3;padding:8px 10px;font-size:12px;outline:none;margin-bottom:2px}
select:focus,input:focus{border-color:#2ecc71}

.btn{width:100%;padding:9px;border:none;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;transition:all .2s;margin-bottom:2px}
.btn-go{background:#1a7a3c;color:#fff}.btn-go:hover{background:#1f9649}
.btn-go:disabled{background:#21262d;color:#484f58;cursor:not-allowed}
.btn-stop{background:#da3633;color:#fff}.btn-stop:hover{background:#f85149}
.btn-sec{background:#21262d;color:#c9d1d9;border:1px solid #30363d}.btn-sec:hover{background:#30363d}
.btn-sm{font-size:10px;padding:5px 8px;width:auto;border-radius:6px}

/* Finger tiles */
.fgrid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.ftile{background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:9px;transition:all .3s;position:relative}
.ftile.detecting{border-color:#58a6ff;background:#0a1520}
.ftile.holding{border-color:#f59e0b;background:#1a1200}
.ftile.captured{border-color:#2ecc71;background:#0a1a0d}
.ftile.bad{border-color:#ef4444;background:#1a0a0a}

.ft-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.ft-name{font-size:10px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.6px}
.ft-badge{font-size:9px;font-weight:700;padding:2px 6px;border-radius:9px}
.ft-badge.ok{background:#1a7a3c22;color:#2ecc71;border:1px solid #1a7a3c55}
.ft-badge.hold{background:#1a120022;color:#f59e0b;border:1px solid #f59e0b55}
.ft-badge.bad{background:#da363322;color:#f85149;border:1px solid #da363355}
.ft-badge.wait{background:#21262d;color:#484f58;border:1px solid #30363d}
.ft-badge.det{background:#0d1f3022;color:#58a6ff;border:1px solid #1f6feb55}

/* Thumbnail */
.ft-thumb{width:100%;height:60px;border-radius:6px;object-fit:cover;margin-bottom:5px;
  border:1px solid #30363d;display:none;cursor:pointer}
.ft-thumb.show{display:block}
.ft-placeholder{width:100%;height:60px;background:#161b22;border-radius:6px;margin-bottom:5px;
  border:1px dashed #30363d;display:flex;align-items:center;justify-content:center;font-size:20px;color:#30363d}

/* Score row */
.ft-score-row{display:flex;align-items:baseline;gap:5px;margin-bottom:4px}
.ft-score-big{font-size:22px;font-weight:800;line-height:1}
.ft-score-big.good{color:#2ecc71}.ft-score-big.ok{color:#f59e0b}.ft-score-big.bad{color:#ef4444}.ft-score-big.none{color:#484f58}
.ft-score-label{font-size:9px;color:#8b949e}

.ft-bar{height:3px;background:#21262d;border-radius:2px;overflow:hidden;margin-bottom:5px}
.ft-fill{height:100%;border-radius:2px;transition:width .4s,background .4s}

/* Metric chips */
.chips{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px}
.chip{background:#161b22;border:1px solid #21262d;border-radius:5px;padding:3px 6px;display:flex;flex-direction:column;align-items:center;min-width:42px}
.chip-lbl{font-size:8px;color:#8b949e;font-weight:700;text-transform:uppercase}
.chip-val{font-size:11px;font-weight:800}
.chip-val.good{color:#2ecc71}.chip-val.ok{color:#f59e0b}.chip-val.bad{color:#ef4444}.chip-val.none{color:#484f58}

/* Liveness */
.lv-row{display:flex;align-items:center;gap:5px}
.lv-pill{font-size:9px;font-weight:700;padding:2px 7px;border-radius:9px}
.lv-pill.pass{background:#1a7a3c22;color:#2ecc71;border:1px solid #1a7a3c55}
.lv-pill.fail{background:#da363322;color:#f85149;border:1px solid #da363355}
.lv-conf{font-size:9px;color:#8b949e}

/* Banner */
.ok-banner{background:#0d1a0d;border:1px solid #2ecc71;border-radius:9px;padding:12px;text-align:center}
.ok-banner h2{color:#2ecc71;font-size:14px;margin-bottom:4px}
.ok-banner p{color:#8b949e;font-size:11px}

/* Log */
.log{background:#0d1117;border:1px solid #30363d;border-radius:7px;padding:7px 9px;
  font-family:monospace;font-size:10px;color:#8b949e;max-height:100px;overflow-y:auto;line-height:1.8}
.log .ok{color:#2ecc71}.log .err{color:#f85149}.log .info{color:#58a6ff}

.card{background:#0d1117;border:1px solid #30363d;border-radius:9px;padding:11px}
.card h3{font-size:9px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.8px;margin-bottom:7px}
.mrow{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}
.mlbl{font-size:11px;color:#8b949e}
.mval{font-size:11px;font-weight:700}
.pill{display:inline-block;padding:2px 8px;border-radius:15px;font-size:10px;font-weight:700}
.pill-g{background:#1a7a3c22;color:#2ecc71;border:1px solid #1a7a3c55}
.pill-r{background:#da363322;color:#f85149;border:1px solid #da363355}

.legend{display:flex;gap:10px;font-size:9px;color:#8b949e;font-weight:700}
.leg{display:flex;align-items:center;gap:4px}
.leg-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}

hr.div{border:none;border-top:1px solid #21262d}

/* Audit table */
.atbl{width:100%;font-size:10px;border-collapse:collapse}
.atbl th{color:#8b949e;font-weight:700;text-transform:uppercase;letter-spacing:.4px;
  padding:5px 6px;border-bottom:1px solid #21262d;text-align:left;white-space:nowrap}
.atbl td{padding:5px 6px;border-bottom:1px solid #21262d;color:#c9d1d9}
.atbl tr:hover td{background:#161b22}
.ep{padding:2px 6px;border-radius:7px;font-size:9px;font-weight:700}
.ep-C{background:#1f2d3d;color:#58a6ff}
.ep-E{background:#0d1f15;color:#2ecc71}
.ep-V{background:#1f1000;color:#f59e0b}
.ep-X{background:#1f0d0d;color:#f85149}
</style>
</head>
<body>

<header>
  <h1>Fingerprint SDK — Live Capture</h1>
  <span class="hdr-txn" id="hdrTxn">No session</span>
  <span class="badge" id="liveBadge">LIVE</span>
</header>

<div class="layout">
  <!-- Camera panel -->
  <div class="cam-panel" id="camPanel">
    <video id="video" autoplay playsinline muted></video>
    <canvas id="overlay"></canvas>
    <canvas id="scratchCanvas"></canvas>
    <!-- Static scan guide frame -->
    <div class="scan-guide" id="scanGuide">
      <div class="sg-corner sg-tl"></div><div class="sg-corner sg-tr"></div>
      <div class="sg-corner sg-bl"></div><div class="sg-corner sg-br"></div>
    </div>

    <div class="live-wrap">
      <div class="live-dot"></div>
      <span id="liveLabel">READY</span>
    </div>

    <div class="q-hud">
      <div class="q-label">Avg Quality</div>
      <div class="q-big bad" id="avgQ">—</div>
      <div class="q-bar"><div class="q-fill" id="avgQBar" style="width:0%"></div></div>
    </div>

    <div class="guidance warn" id="guidance">
      <span class="g-icon" id="gIcon">✋</span>
      <span class="g-text" id="gText">Point your hand flat at the camera</span>
    </div>
  </div>

  <!-- Right panel -->
  <div class="ctrl">
    <div class="tabs">
      <div class="tab active" onclick="switchTab('capture')">Capture</div>
      <div class="tab" onclick="switchTab('enroll')">Enroll</div>
      <div class="tab" onclick="switchTab('verify')">Verify</div>
      <div class="tab" onclick="switchTab('audit')">Audit</div>
    </div>

    <!-- Capture pane -->
    <div class="pane active" id="pane-capture">
      <div>
        <label>Hand</label>
        <select id="handSel" onchange="resetCapture()">
          <option value="RIGHT_FOUR">Right Hand (4 Fingers)</option>
          <option value="LEFT_FOUR">Left Hand (4 Fingers)</option>
          <option value="RIGHT_THUMB">Right Thumb</option>
          <option value="LEFT_THUMB">Left Thumb</option>
          <option value="SINGLE_FINGER">Single Finger</option>
          <option value="CUSTOM_SEQUENCE">Custom Sequence</option>
          <option value="PARTIAL_CAPTURE">Partial Capture</option>
        </select>
      </div>

      <div class="legend">
        <div class="leg"><div class="leg-dot" style="background:#2ecc71"></div>≥70 Accept</div>
        <div class="leg"><div class="leg-dot" style="background:#f59e0b"></div>40–69 Retry</div>
        <div class="leg"><div class="leg-dot" style="background:#ef4444"></div>&lt;40 Reject</div>
        <div class="leg"><div class="leg-dot" style="background:#2ecc71"></div>≥60 Auto-capture</div>
      </div>

      <button class="btn btn-go"   id="startBtn" onclick="startCapture()">▶ Start Live Detection</button>
      <button class="btn btn-stop" id="stopBtn"  onclick="stopCapture()"  style="display:none">■ Stop</button>
      <button class="btn btn-sec"  onclick="resetCapture()">↺ Reset</button>

      <hr class="div">
      <div class="fgrid" id="fgrid"></div>

      <div id="okBanner" class="ok-banner" style="display:none">
        <h2>✓ Captured!</h2>
        <p id="okMsg"></p>
      </div>

      <div id="actionBtns" style="display:none">
        <button class="btn btn-go"  onclick="sendToBackend()">Send to Backend for Template</button>
        <button class="btn btn-sec" onclick="downloadAll()">⬇ Download All Crops</button>
      </div>
    </div>

    <!-- Enroll pane -->
    <div class="pane" id="pane-enroll">
      <div><label>User ID</label><input type="text" id="enrollUid" placeholder="e.g. user_001"></div>
      <div><label>Hand</label>
        <select id="enrollHand">
          <option value="RIGHT">Right Hand</option>
          <option value="LEFT">Left Hand</option>
        </select>
      </div>
      <button class="btn btn-go" onclick="captureForEnroll()">Capture 4 Fingers</button>
      <button class="btn btn-go" id="enrollBtn" onclick="submitEnroll()" disabled>Submit Enrollment</button>
      <hr class="div">
      <div class="log" id="enrollLog">Ready...<br></div>
    </div>

    <!-- Verify pane -->
    <div class="pane" id="pane-verify">
      <div><label>User ID</label><input type="text" id="verifyUid" placeholder="e.g. user_001"></div>
      <div><label>Finger</label>
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
      </div>
      <button class="btn btn-go" onclick="captureAndVerify()">Capture & Verify</button>
      <hr class="div">
      <div id="vResult" style="display:none">
        <div class="card" id="vCard">
          <h3>Match Result</h3>
          <div class="mrow"><span class="mlbl">Decision</span><span id="vMatch" class="pill">—</span></div>
          <div class="mrow"><span class="mlbl">Confidence</span><span id="vConf" class="mval" style="color:#8b949e">—</span></div>
          <div class="q-bar" style="margin-top:5px"><div class="q-fill" id="vBar" style="width:0%"></div></div>
          <div style="margin-top:7px;font-size:11px;color:#8b949e" id="vMsg"></div>
        </div>
      </div>
      <div class="log" id="verifyLog">Ready...<br></div>
    </div>

    <!-- Audit pane -->
    <div class="pane" id="pane-audit">
      <button class="btn btn-sec" onclick="loadAudit()">⟳ Refresh</button>
      <div style="overflow-x:auto">
        <table class="atbl">
          <thead><tr><th>Time</th><th>Event</th><th>OK</th><th>User</th><th>Q</th></tr></thead>
          <tbody id="auditBody"><tr><td colspan="5" style="color:#484f58;text-align:center;padding:12px">Click Refresh</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────
const BASE         = window.location.origin;
const CAPTURE_QUAL = 60;
const HOLD_FRAMES  = 2;
const BBOX_PAD     = 15;

let FINGER_DEFS = [];
const FINGER_DEFS_4 = [
  { key:'INDEX',  ids:[5,6,7,8]    },
  { key:'MIDDLE', ids:[9,10,11,12] },
  { key:'RING',   ids:[13,14,15,16]},
  { key:'LITTLE', ids:[17,18,19,20]},
];
const FINGER_DEFS_THUMB = [
  { key:'THUMB', ids:[1,2,3,4] },
];
const FINGER_DEFS_SINGLE = [
  { key:'INDEX', ids:[5,6,7,8] },
];
const FINGER_DEFS_CUSTOM = [
  { key:'INDEX', ids:[5,6,7,8] },
  { key:'LITTLE', ids:[17,18,19,20] },
];
const FINGER_DEFS_PARTIAL = [
  { key:'INDEX', ids:[5,6,7,8] },
  { key:'MIDDLE', ids:[9,10,11,12] },
  { key:'LITTLE', ids:[17,18,19,20] },
];
const FINGER_LABEL = {THUMB:'Thumb',INDEX:'Index',MIDDLE:'Middle',RING:'Ring',LITTLE:'Little'};

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
let videoEl, overlayCanvas, overlayCtx, scratchCanvas, scratchCtx;
let stream        = null;
let imageCapture  = null;   // ImageCapture API for high-res stills
let running       = false;
let txnId         = null;
let streak        = {};
let capturedData  = {};
let enrollBuffer  = {};
let analyzing     = false;

// ─────────────────────────────────────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────────────────────────────────────
window.addEventListener('load', async () => {
  videoEl       = document.getElementById('video');
  overlayCanvas = document.getElementById('overlay');
  overlayCtx    = overlayCanvas.getContext('2d');
  scratchCanvas = document.getElementById('scratchCanvas');
  scratchCtx    = scratchCanvas.getContext('2d');

  await newSession();
  buildGrid('RIGHT');
  await startCamera();
});

window.addEventListener('resize', resizeCanvas);

// ─────────────────────────────────────────────────────────────────────────────
// Session
// ─────────────────────────────────────────────────────────────────────────────
async function newSession() {
  try {
    const r = await fetch(BASE + '/api/session');
    const d = await r.json();
    txnId = d.transaction_id;
    document.getElementById('hdrTxn').textContent = 'txn: ' + txnId.substring(0,8) + '…';
  } catch(e) {
    txnId = Date.now().toString();
    document.getElementById('hdrTxn').textContent = 'offline-txn';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Camera
// ─────────────────────────────────────────────────────────────────────────────
async function startCamera() {
  try {
    if (stream) stream.getTracks().forEach(t => t.stop());

    // Request highest available resolution — no facingMode constraint so the
    // browser picks the best camera (front webcam on laptops, rear on phones)
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width:     { ideal: 1920 },
        height:    { ideal: 1080 },
        frameRate: { ideal: 30 }
      }
    });

    // Apply continuous focus / exposure / white-balance if the camera supports it
    const track = stream.getVideoTracks()[0];
    if (track) {
      const caps = track.getCapabilities ? track.getCapabilities() : {};
      const adv  = {};
      if (caps.focusMode        && caps.focusMode.includes('continuous'))        adv.focusMode        = 'continuous';
      if (caps.exposureMode     && caps.exposureMode.includes('continuous'))     adv.exposureMode     = 'continuous';
      if (caps.whiteBalanceMode && caps.whiteBalanceMode.includes('continuous')) adv.whiteBalanceMode = 'continuous';
      if (Object.keys(adv).length) {
        try { await track.applyConstraints({ advanced: [adv] }); } catch(_) {}
      }
      // ImageCapture gives full-sensor-resolution stills instead of compressed video frames
      if (typeof ImageCapture !== 'undefined') {
        imageCapture = new ImageCapture(track);
      }
    }

    videoEl.srcObject = stream;
    await new Promise(r => videoEl.addEventListener('loadedmetadata', r, {once:true}));
    videoEl.play();
    resizeCanvas();

    const settings = track ? track.getSettings() : {};
    const resLabel = settings.width ? `${settings.width}×${settings.height}` : 'unknown';
    setGuide(`Camera ready (${resLabel}) — click Start Live Detection`, 'warn');
  } catch(e) {
    setGuide('Camera access denied — ' + e.message, 'err');
  }
}


function resizeCanvas() {
  const panel = document.getElementById('camPanel');
  overlayCanvas.width  = panel.clientWidth  || videoEl.clientWidth  || 640;
  overlayCanvas.height = panel.clientHeight || videoEl.clientHeight || 480;
}

// Map MediaPipe normalized coords → overlay canvas pixels (accounts for object-fit:cover)
function mpToCanvas(lm) {
  const vW = videoEl.videoWidth  || 640;
  const vH = videoEl.videoHeight || 480;
  const cW = overlayCanvas.width;
  const cH = overlayCanvas.height;
  const scale  = Math.max(cW / vW, cH / vH);
  const offX   = (cW - vW * scale) / 2;
  const offY   = (cH - vH * scale) / 2;
  return { x: lm.x * vW * scale + offX, y: lm.y * vH * scale + offY };
}

// Get bounding box in VIDEO natural pixel space
function getLandmarkBbox(lms, ids) {
  const vW = videoEl.videoWidth  || 640;
  const vH = videoEl.videoHeight || 480;
  const xs = ids.map(i => lms[i].x * vW);
  const ys = ids.map(i => lms[i].y * vH);
  const x1 = Math.max(0,  Math.min(...xs) - BBOX_PAD);
  const y1 = Math.max(0,  Math.min(...ys) - BBOX_PAD);
  const x2 = Math.min(vW, Math.max(...xs) + BBOX_PAD);
  const y2 = Math.min(vH, Math.max(...ys) + BBOX_PAD);
  return { x:x1, y:y1, w:x2-x1, h:y2-y1 };
}

// Map bbox in video space → canvas display space
function bboxToCanvas(bbox) {
  const vW = videoEl.videoWidth  || 640;
  const vH = videoEl.videoHeight || 480;
  const cW = overlayCanvas.width;
  const cH = overlayCanvas.height;
  const scale  = Math.max(cW / vW, cH / vH);
  const offX   = (cW - vW * scale) / 2;
  const offY   = (cH - vH * scale) / 2;
  return {
    x: bbox.x * scale + offX,
    y: bbox.y * scale + offY,
    w: bbox.w * scale,
    h: bbox.h * scale,
  };
}

function isFingerExtended(lms, ids) {
  return lms[ids[ids.length - 1]].y < lms[ids[0]].y - 0.04;
}

// ─────────────────────────────────────────────────────────────────────────────
// Backend-driven detection loop
// ─────────────────────────────────────────────────────────────────────────────
// Fast frame grab for the ~3fps analysis loop (video frame, moderate quality)
function grabBase64() {
  const vW = videoEl.videoWidth  || 640;
  const vH = videoEl.videoHeight || 480;
  scratchCanvas.width  = vW;
  scratchCanvas.height = vH;
  scratchCtx.drawImage(videoEl, 0, 0, vW, vH);
  return scratchCanvas.toDataURL('image/jpeg', 0.92).split(',')[1];
}

// High-res still grab for actual finger capture using ImageCapture API.
// Falls back to video frame if ImageCapture is unavailable.
async function grabHighResBase64() {
  if (imageCapture) {
    try {
      const bitmap = await imageCapture.grabFrame();
      scratchCanvas.width  = bitmap.width;
      scratchCanvas.height = bitmap.height;
      scratchCtx.drawImage(bitmap, 0, 0);
      bitmap.close();
      return scratchCanvas.toDataURL('image/jpeg', 0.96).split(',')[1];
    } catch(_) { /* fall through to video frame */ }
  }
  return grabBase64();
}

function getHandSide() {
  const v = document.getElementById('handSel').value;
  return v.startsWith('LEFT') ? 'LEFT' : 'RIGHT';
}

async function analyzeLoop() {
  if (!running) return;
  if (analyzing || videoEl.readyState < 2) { setTimeout(analyzeLoop, 100); return; }
  analyzing = true;

  const hand = getHandSide();
  const handSelVal = document.getElementById('handSel').value;
  try {
    const res  = await fetch(BASE + '/api/capture/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_base64: grabBase64(), hand, mode: handSelVal })
    });
    const data = await res.json();
    onAnalyzeResult(data);
  } catch(e) {
    setGuide('Connection error — is the server running?', 'err');
  } finally {
    analyzing = false;
    if (running) setTimeout(analyzeLoop, 150);  // ~6 fps
  }
}

function onAnalyzeResult(data) {
  overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

  if (!data.hand_detected) {
    document.getElementById('scanGuide').className = 'scan-guide err';
    setGuide(data.guidance || 'No hand detected — show palm flat toward camera', 'err');
    setAvgQ(0);
    FINGER_DEFS.forEach(f => { if (!capturedData[f.key]) updateTileNoHand(f.key); });
    return;
  }

  document.getElementById('scanGuide').className = 'scan-guide ok';

  const hand = getHandSide();
  let totalQ = 0, countQ = 0, anyGuide = data.guidance || null;

  (data.fingers || []).forEach(f => {
    const key = f.finger_id.replace(hand + '_', '');
    if (capturedData[key]) {
      // Already locked — draw green box if bbox available
      if (f.bbox_pct) drawBboxPct(f.bbox_pct, '#2ecc71', '✓ ' + key, null, true);
      return;
    }

    if (!f.detected || f.quality_score === 0) {
      streak[key] = 0;
      updateTileNoHand(key);
      return;
    }

    const q = f.quality_score;
    totalQ += q; countQ++;
    if (f.guidance && !anyGuide) anyGuide = f.guidance;

    const isLive = f.liveness === true;
    const color = (q >= CAPTURE_QUAL && isLive) ? '#2ecc71' : (q >= 40 && isLive) ? '#f59e0b' : '#ef4444';
    if (f.bbox_pct) {
      const label = (q >= CAPTURE_QUAL && isLive)
        ? (streak[key] >= 1 ? key + ' ' + '●'.repeat(streak[key]) + '○'.repeat(HOLD_FRAMES - streak[key]) : key)
        : (!isLive ? 'FAKE ' + key : key);
      drawBboxPct(f.bbox_pct, color, label, q, false);
    }

    const metrics = { score: q, blur: f.blur_score, illum: f.illum_score, liveness: f.liveness_conf ? f.liveness_conf * 100 : (f.liveness ? 80 : 20), reason: f.guidance || null };

    if (q >= CAPTURE_QUAL && isLive) {
      streak[key] = (streak[key] || 0) + 1;
      if (streak[key] >= HOLD_FRAMES) {
        // Lock — grab high-res still using ImageCapture API, then crop
        grabHighResBase64().then(() => {
          const dataURL = f.bbox_pct ? cropFromBboxPct(f.bbox_pct) : scratchCanvas.toDataURL('image/jpeg', 0.96);
          capturedData[key] = { imageDataURL: dataURL, ...metrics, timestamp: Date.now() };
          updateTileCaptured(key, metrics, dataURL);
        });
        if (f.bbox_pct) drawBboxPct(f.bbox_pct, '#2ecc71', 'CAPTURED ' + key, q, true);
        if (Object.keys(capturedData).length >= 1) {
            document.getElementById('actionBtns').style.display = 'block';
        }
        if (Object.keys(capturedData).length >= FINGER_DEFS.length) setTimeout(onAllCaptured, 100);
      } else {
        updateTileDetecting(key, metrics, 'hold');
      }
    } else if (q >= 40 && isLive) {
      streak[key] = 0;
      updateTileDetecting(key, metrics, 'det');
    } else {
      streak[key] = 0;
      updateTileDetecting(key, metrics, 'bad');
    }
  });

  if (countQ > 0) {
    setAvgQ(totalQ / countQ);
    const avg = totalQ / countQ;
    setGuide(anyGuide || (avg >= CAPTURE_QUAL ? 'Hold still — capturing!' : 'Spread fingers flat toward camera'),
             anyGuide ? 'warn' : avg >= CAPTURE_QUAL ? 'ok' : 'warn');
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// BboxPct draw helpers
// ─────────────────────────────────────────────────────────────────────────────
function bboxPctToCanvas(bp) {
  // bp: {x,y,w,h} as fractions of original video frame
  // map to overlay canvas display size (accounting for object-fit:cover)
  const vW = videoEl.videoWidth  || 640;
  const vH = videoEl.videoHeight || 480;
  const cW = overlayCanvas.width;
  const cH = overlayCanvas.height;
  const scale = Math.max(cW / vW, cH / vH);
  const offX  = (cW - vW * scale) / 2;
  const offY  = (cH - vH * scale) / 2;
  return {
    x: bp.x * vW * scale + offX,
    y: bp.y * vH * scale + offY,
    w: bp.w * vW * scale,
    h: bp.h * vH * scale,
  };
}

function drawBboxPct(bp, color, label, score, locked) {
  drawBbox(bboxPctToCanvas(bp), color, label, score, locked);
}

function cropFromBboxPct(bp) {
  const vW = scratchCanvas.width;
  const vH = scratchCanvas.height;
  const px = Math.round(bp.x * vW), py = Math.round(bp.y * vH);
  const pw = Math.round(bp.w * vW), ph = Math.round(bp.h * vH);
  const tmp = document.createElement('canvas');
  tmp.width = pw; tmp.height = ph;
  tmp.getContext('2d').drawImage(scratchCanvas, px, py, pw, ph, 0, 0, pw, ph);
  return tmp.toDataURL('image/jpeg', 0.92);
}

// ─────────────────────────────────────────────────────────────────────────────
// DEAD CODE — kept for reference, replaced by analyzeLoop
// ─────────────────────────────────────────────────────────────────────────────
function processFingers(lms, hand) {
  const vW = videoEl.videoWidth  || 640;
  const vH = videoEl.videoHeight || 480;
  scratchCanvas.width  = vW;
  scratchCanvas.height = vH;
  scratchCtx.drawImage(videoEl, 0, 0, vW, vH);

  let totalQ = 0, countQ = 0, anyGuide = null;
  const boxes = [];  // collected for overlayData

  FINGER_DEFS.forEach(({ key, ids }) => {
    if (capturedData[key]) {
      if (isFingerExtended(lms, ids)) {
        boxes.push({ dispBbox: bboxToCanvas(getLandmarkBbox(lms, ids)),
                     color:'#2ecc71', label:'✓ '+key, score:null, locked:true });
      }
      return;
    }

    if (!isFingerExtended(lms, ids)) {
      streak[key] = 0;
      updateTileNoHand(key);
      return;
    }

    const bbox    = getLandmarkBbox(lms, ids);
    const imgData = scratchCtx.getImageData(bbox.x, bbox.y, Math.max(1,bbox.w), Math.max(1,bbox.h));
    const metrics = calcQuality(imgData);
    const q       = metrics.score;
    totalQ += q; countQ++;
    if (metrics.guide && !anyGuide) anyGuide = metrics.guide;

    const dispBbox = bboxToCanvas(bbox);

    if (q >= CAPTURE_QUAL) {
      streak[key] = (streak[key] || 0) + 1;
      if (streak[key] >= HOLD_FRAMES) {
        const dataURL = cropToDataURL(bbox);
        capturedData[key] = { imageDataURL:dataURL, ...metrics, bbox, timestamp:Date.now() };
        updateTileCaptured(key, metrics, dataURL);
        boxes.push({ dispBbox, color:'#2ecc71', label:'CAPTURED '+key, score:q, locked:true });
        if (Object.keys(capturedData).length >= 4) setTimeout(onAllCaptured, 100);
      } else {
        const dots = '●'.repeat(streak[key]) + '○'.repeat(HOLD_FRAMES - streak[key]);
        boxes.push({ dispBbox, color:'#2ecc71', label:key+' '+dots, score:q, locked:false });
        updateTileDetecting(key, metrics, 'hold');
      }
    } else if (q >= 40) {
      streak[key] = 0;
      boxes.push({ dispBbox, color:'#f59e0b', label:key, score:q, locked:false });
      updateTileDetecting(key, metrics, 'det');
    } else {
      streak[key] = 0;
      boxes.push({ dispBbox, color:'#ef4444', label:key, score:q, locked:false });
      updateTileDetecting(key, metrics, 'bad');
    }
  });

  // Draw all boxes directly onto overlay canvas
  boxes.forEach(b => drawBbox(b.dispBbox, b.color, b.label, b.score, b.locked));

  if (countQ > 0) {
    const avg = totalQ / countQ;
    setAvgQ(avg);
    setGuide(anyGuide || (avg >= CAPTURE_QUAL ? 'Hold still — capturing!' :
             'Spread fingers flat and point toward camera'),
             anyGuide ? 'warn' : avg >= CAPTURE_QUAL ? 'ok' : 'warn');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Quality metrics (pure JS, matches backend logic)
// ─────────────────────────────────────────────────────────────────────────────
function calcQuality(imgData) {
  const blur  = calcBlur(imgData);
  const illum = calcIllum(imgData);
  const live  = calcLiveness(imgData);
  const score = Math.min(100, blur * 0.35 + illum * 0.35 + live * 0.30);
  const guide = qualityGuide(blur, illum, live, imgData);
  return { score, blur, illum, liveness: live, guide };
}

function calcBlur(imgData) {
  // Laplacian variance on grayscale (sampled every 2px for speed)
  const d = imgData.data, w = imgData.width, h = imgData.height;
  const gray = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++) {
    gray[i] = 0.299*d[i*4] + 0.587*d[i*4+1] + 0.114*d[i*4+2];
  }
  let sum = 0, sum2 = 0, n = 0;
  for (let y = 2; y < h-2; y += 2) {
    for (let x = 2; x < w-2; x += 2) {
      const c   = gray[y*w+x];
      const lap = Math.abs(-4*c + gray[(y-1)*w+x] + gray[(y+1)*w+x] + gray[y*w+x-1] + gray[y*w+x+1]);
      sum  += lap;
      sum2 += lap * lap;
      n++;
    }
  }
  if (n === 0) return 0;
  const mean = sum / n;
  const variance = sum2 / n - mean * mean;
  return Math.min(100, variance / 3);
}

function calcIllum(imgData) {
  // Mean brightness + contrast check, matches backend _contrast_score + brightness
  const d = imgData.data;
  const n = imgData.width * imgData.height;
  let sumB = 0, sumB2 = 0;
  for (let i = 0; i < n; i++) {
    const lum = 0.299*d[i*4] + 0.587*d[i*4+1] + 0.114*d[i*4+2];
    sumB  += lum;
    sumB2 += lum * lum;
  }
  const mean = sumB / n;
  const std  = Math.sqrt(sumB2/n - mean*mean);

  // Brightness penalty (optimal 80-180)
  let brightFactor;
  if (mean >= 80 && mean <= 180)     brightFactor = 1.0;
  else if (mean < 50 || mean > 210)  brightFactor = 0.4;
  else if (mean < 80)                brightFactor = 0.4 + 0.6*(mean-50)/30;
  else                               brightFactor = 0.4 + 0.6*(210-mean)/30;

  return Math.min(100, (std / 0.64) * brightFactor);
}

function calcLiveness(imgData) {
  // Screen-replay guard: % of pure-white (glare) pixels
  const d = imgData.data;
  const n = imgData.width * imgData.height;
  let glare = 0;
  for (let i = 0; i < n; i++) {
    if (d[i*4] > 245 && d[i*4+1] > 245 && d[i*4+2] > 245) glare++;
  }
  const ratio = glare / n;
  if (ratio > 0.15) return 30;   // likely screen replay
  return Math.max(40, 100 - ratio * 400);
}

function qualityGuide(blur, illum, live, imgData) {
  const d    = imgData.data;
  const n    = imgData.width * imgData.height;
  let sumB   = 0;
  for (let i = 0; i < n; i++) sumB += 0.299*d[i*4]+0.587*d[i*4+1]+0.114*d[i*4+2];
  const brightness = sumB / n;

  if (brightness < 55)  return 'Too dark — move to better lighting';
  if (brightness > 215) return 'Too bright — reduce glare or move away from light';
  if (blur < 40)        return 'Hold still — finger is blurry';
  if (live < 40)        return 'Glare detected — move away from screen / light';
  if (illum < 35)       return 'Low contrast — improve lighting';
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Canvas drawing helpers
// ─────────────────────────────────────────────────────────────────────────────
function drawBbox(dispBbox, color, label, score, locked) {
  const { x, y, w, h } = dispBbox;
  overlayCtx.save();

  overlayCtx.strokeStyle = color;
  overlayCtx.lineWidth   = locked ? 3 : 2;
  overlayCtx.setLineDash(locked ? [] : [6, 3]);
  roundRect(overlayCtx, x, y, w, h, 8);
  overlayCtx.stroke();
  overlayCtx.setLineDash([]);

  // Fill label background
  const lblH = 18;
  overlayCtx.fillStyle = color + 'cc';
  overlayCtx.fillRect(x, y - lblH, w, lblH);

  // Label text
  overlayCtx.fillStyle = '#fff';
  overlayCtx.font = 'bold 10px system-ui';
  overlayCtx.textAlign = 'left';
  overlayCtx.fillText(label, x + 5, y - 5);

  // Score pill top-right
  if (score != null) {
    const sq = score.toFixed(0);
    overlayCtx.textAlign = 'right';
    overlayCtx.fillText(sq, x + w - 5, y - 5);
  }

  // Corner accents for locked
  if (locked) {
    const cs = 12;
    overlayCtx.lineWidth = 3;
    overlayCtx.strokeStyle = color;
    [[x,y],[x+w,y],[x,y+h],[x+w,y+h]].forEach(([cx,cy], i) => {
      overlayCtx.beginPath();
      overlayCtx.moveTo(cx + (i%2===0?cs:-cs), cy);
      overlayCtx.lineTo(cx, cy);
      overlayCtx.lineTo(cx, cy + (i<2?cs:-cs));
      overlayCtx.stroke();
    });
  }

  overlayCtx.restore();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);  ctx.arcTo(x+w, y,   x+w, y+r,   r);
  ctx.lineTo(x + w, y+h-r);  ctx.arcTo(x+w, y+h, x+w-r,y+h, r);
  ctx.lineTo(x + r, y+h);    ctx.arcTo(x,   y+h, x,   y+h-r, r);
  ctx.lineTo(x, y + r);      ctx.arcTo(x,   y,   x+r, y,     r);
  ctx.closePath();
}

function cropToDataURL(bbox) {
  const tmp = document.createElement('canvas');
  tmp.width  = bbox.w;
  tmp.height = bbox.h;
  const tc   = tmp.getContext('2d');
  tc.drawImage(scratchCanvas, bbox.x, bbox.y, bbox.w, bbox.h, 0, 0, bbox.w, bbox.h);
  return tmp.toDataURL('image/jpeg', 0.92);
}

// ─────────────────────────────────────────────────────────────────────────────
// Tile updates
// ─────────────────────────────────────────────────────────────────────────────
function buildGrid(hand) {
  const g = document.getElementById('fgrid');
  g.innerHTML = '';
  
  if (hand === 'SINGLE_FINGER') FINGER_DEFS = FINGER_DEFS_SINGLE;
  else if (hand === 'CUSTOM_SEQUENCE') FINGER_DEFS = FINGER_DEFS_CUSTOM;
  else if (hand === 'PARTIAL_CAPTURE') FINGER_DEFS = FINGER_DEFS_PARTIAL;
  else if (hand.includes('THUMB')) FINGER_DEFS = FINGER_DEFS_THUMB;
  else FINGER_DEFS = FINGER_DEFS_4;

  g.style.gridTemplateColumns = FINGER_DEFS.length === 1 ? '1fr' : '1fr 1fr';

  FINGER_DEFS.forEach(({ key }) => {
    g.innerHTML += `
    <div class="ftile" id="tile-${key}">
      <div class="ft-top">
        <span class="ft-name">${FINGER_LABEL[key]}</span>
        <span class="ft-badge wait" id="badge-${key}">Waiting</span>
      </div>
      <div class="ft-placeholder" id="ph-${key}">👆</div>
      <img class="ft-thumb" id="thumb-${key}" alt="">
      <div class="ft-score-row">
        <span class="ft-score-big none" id="score-${key}">—</span>
        <span class="ft-score-label">/ 100</span>
      </div>
      <div class="ft-bar"><div class="ft-fill" id="bar-${key}" style="width:0%"></div></div>
      <div class="chips" id="chips-${key}">
        ${chip('BLR','—','none')}${chip('ILLUM','—','none')}${chip('LIVE','—','none')}
      </div>
      <div class="lv-row" id="lv-${key}"></div>
    </div>`;
  });
}

function chip(lbl, val, cls) {
  return `<div class="chip"><span class="chip-lbl">${lbl}</span><span class="chip-val ${cls}">${val}</span></div>`;
}

function scCls(v) { return v == null ? 'none' : v > 70 ? 'good' : v > 40 ? 'ok' : 'bad'; }
function fmt(v)   { return v != null ? v.toFixed(0) : '—'; }

function updateTileNoHand(key) {
  if (capturedData[key]) return;
  const tile = document.getElementById('tile-' + key);
  if (!tile) return;
  tile.className = 'ftile';
  document.getElementById('badge-' + key).textContent = 'No finger';
  document.getElementById('badge-' + key).className   = 'ft-badge wait';
  document.getElementById('score-' + key).textContent = '—';
  document.getElementById('score-' + key).className   = 'ft-score-big none';
  document.getElementById('bar-'   + key).style.width = '0%';
  document.getElementById('chips-' + key).innerHTML   =
    chip('BLR','—','none') + chip('ILLUM','—','none') + chip('LIVE','—','none');
  document.getElementById('lv-' + key).innerHTML = '';
}

function updateTileDetecting(key, metrics, state) {
  if (capturedData[key]) return;
  const tile  = document.getElementById('tile-' + key);
  const badge = document.getElementById('badge-' + key);
  const sc    = document.getElementById('score-' + key);
  const bar   = document.getElementById('bar-'   + key);
  if (!tile) return;

  const q = metrics.score;
  const qcol = q > 70 ? '#2ecc71' : q > 40 ? '#f59e0b' : '#ef4444';

  tile.className  = 'ftile ' + (state === 'hold' ? 'holding' : state === 'bad' ? 'bad' : 'detecting');
  sc.textContent  = q.toFixed(0);
  sc.className    = 'ft-score-big ' + scCls(q);
  bar.style.width      = Math.min(q, 100) + '%';
  bar.style.background = qcol;

  if (state === 'hold') {
    const s = streak[key] || 0;
    badge.textContent = '●'.repeat(s) + '○'.repeat(HOLD_FRAMES - s) + ' Hold!';
    badge.className   = 'ft-badge hold';
  } else if (state === 'bad') {
    badge.textContent = 'Low quality';
    badge.className   = 'ft-badge bad';
  } else {
    badge.textContent = 'Detecting…';
    badge.className   = 'ft-badge det';
  }

  document.getElementById('chips-' + key).innerHTML =
    chip('BLR',  fmt(metrics.blur),     scCls(metrics.blur))  +
    chip('ILLUM',fmt(metrics.illum),    scCls(metrics.illum)) +
    chip('LIVE', fmt(metrics.liveness), scCls(metrics.liveness));

  const live = metrics.liveness >= 50;
  const failReason = (!live && metrics.reason) ? metrics.reason : (live ? 'LIVE ✓' : 'FAKE ✗');
  const shortReason = failReason.length > 35 ? failReason.substring(0, 35) + '…' : failReason;
  document.getElementById('lv-' + key).innerHTML =
    `<span class="lv-pill ${live?'pass':'fail'}">${live ? 'LIVE ✓' : shortReason}</span>` +
    `<span class="lv-conf">${metrics.liveness.toFixed(0)}%</span>`;
}

function updateTileCaptured(key, metrics, dataURL) {
  const tile  = document.getElementById('tile-' + key);
  const badge = document.getElementById('badge-' + key);
  const sc    = document.getElementById('score-' + key);
  const bar   = document.getElementById('bar-'   + key);
  const ph    = document.getElementById('ph-'    + key);
  const thumb = document.getElementById('thumb-' + key);
  if (!tile) return;

  tile.className   = 'ftile captured';
  badge.textContent= '✓ Captured';
  badge.className  = 'ft-badge ok';
  sc.textContent   = metrics.score.toFixed(0);
  sc.className     = 'ft-score-big good';
  bar.style.width      = Math.min(metrics.score, 100) + '%';
  bar.style.background = '#2ecc71';

  // Show thumbnail
  ph.style.display    = 'none';
  thumb.src           = dataURL;
  thumb.className     = 'ft-thumb show';
  thumb.title         = 'Click to download';
  thumb.onclick       = () => downloadImg(dataURL, key + '_finger.jpg');

  document.getElementById('chips-' + key).innerHTML =
    chip('BLR',  fmt(metrics.blur),     scCls(metrics.blur))  +
    chip('ILLUM',fmt(metrics.illum),    scCls(metrics.illum)) +
    chip('LIVE', fmt(metrics.liveness), scCls(metrics.liveness));

  document.getElementById('lv-' + key).innerHTML =
    `<span class="lv-pill pass">LIVE ✓</span>` +
    `<span class="lv-conf">${metrics.liveness.toFixed(0)}%</span>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Capture control
// ─────────────────────────────────────────────────────────────────────────────
function startCapture() {
  running = true;
  document.getElementById('startBtn').style.display = 'none';
  document.getElementById('stopBtn').style.display  = 'block';
  document.getElementById('liveLabel').textContent  = 'DETECTING';
  document.getElementById('liveBadge').classList.add('on');
  setGuide('Show your fingers flat and point toward camera', 'warn');
  analyzeLoop();
}

function stopCapture() {
  running = false;
  overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  document.getElementById('startBtn').style.display = 'block';
  document.getElementById('stopBtn').style.display  = 'none';
  document.getElementById('liveLabel').textContent  = 'PAUSED';
  document.getElementById('liveBadge').classList.remove('on');
}

function resetCapture() {
  stopCapture();
  streak       = {};
  capturedData = {};
  buildGrid(document.getElementById('handSel').value);
  document.getElementById('okBanner').style.display    = 'none';
  document.getElementById('actionBtns').style.display  = 'none';
  setGuide('Ready — click Start Live Detection', 'warn');
  setAvgQ(0);
  // Redraw clean canvas
  if (videoEl.srcObject) {
    overlayCtx.drawImage(videoEl, 0, 0, liveCanvas.width, liveCanvas.height);
  }
}

function mpLoop() {
  if (!running) return;
  scheduleMP();
  requestAnimationFrame(mpLoop);
}

function onAllCaptured() {
  stopCapture();
  const cnt  = Object.keys(capturedData).length;
  if (cnt === 0) return;
  const avgQ = Object.values(capturedData).reduce((s,r) => s + r.score, 0) / cnt;
  document.getElementById('okBanner').style.display   = 'block';
  document.getElementById('actionBtns').style.display = 'block';
  
  document.getElementById('okMsg').textContent =
    cnt + ' finger' + (cnt > 1 ? 's' : '') + ' captured · Avg quality ' + avgQ.toFixed(1) + '/100';
    
  document.getElementById('okBanner').querySelector('h2').textContent = '✓ Capture Complete!';
  setGuide(cnt + ' fingers captured! Use actions below.', 'ok');
}

// ─────────────────────────────────────────────────────────────────────────────
// HUD helpers
// ─────────────────────────────────────────────────────────────────────────────
function setAvgQ(score) {
  const v = document.getElementById('avgQ');
  const f = document.getElementById('avgQBar');
  v.textContent     = score > 0 ? score.toFixed(0) : '—';
  v.className       = 'q-big ' + (score>70?'good':score>40?'ok':'bad');
  f.style.width      = score + '%';
  f.style.background = score>70?'#2ecc71':score>40?'#f59e0b':'#ef4444';
}

function setGuide(msg, type) {
  const icons = { ok:'✅', warn:'⚠️', err:'❌' };
  const el = document.getElementById('guidance');
  el.className = 'guidance ' + (type||'warn');
  document.getElementById('gIcon').textContent = icons[type]||'⚠️';
  document.getElementById('gText').textContent = msg;
}

// ─────────────────────────────────────────────────────────────────────────────
// Actions: send to backend, download
// ─────────────────────────────────────────────────────────────────────────────
async function sendToBackend() {
  const hand = document.getElementById('handSel').value;
  // Grab current full frame and send to /api/capture/multi for template encoding
  if (!Object.keys(capturedData).length) return;

  // Use high-res still from ImageCapture for best template quality
  const b64 = await grabHighResBase64();
  try {
    const res  = await fetch(BASE + '/api/capture/multi', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ transaction_id: txnId, image_base64: b64, hand })
    });
    const data = await res.json();
    alert('Backend processed ' + (data.results||[]).filter(r=>r.status==='success').length +
          '/4 fingers. Switch to Enroll tab to save.');
    // Cache templates for enroll + swap thumbnails for enhanced backend crops
    enrollBuffer = {};
    const hand = document.getElementById('handSel').value;
    (data.results||[]).forEach(r => {
      if (r.status === 'success' && r.template) {
        enrollBuffer[r.finger_id] = { finger_id:r.finger_id, template:r.template,
                                      quality_score:r.quality_score };
      }
      // Replace raw webcam thumbnail with CLAHE-enhanced crop from backend
      if (r.enhanced_image_b64) {
        const key   = r.finger_id.replace(hand + '_', '');
        const thumb = document.getElementById('thumb-' + key);
        if (thumb) {
          thumb.src       = 'data:image/jpeg;base64,' + r.enhanced_image_b64;
          thumb.className = 'ft-thumb show';
          thumb.title     = 'Enhanced — click to download';
          thumb.onclick   = () => downloadImg(thumb.src, key.toLowerCase() + '_enhanced.jpg');
        }
      }
    });
  } catch(e) { alert('Error: ' + e.message); }
}

function downloadImg(dataURL, filename) {
  const a = document.createElement('a');
  a.href     = dataURL;
  a.download = filename;
  a.click();
}

function downloadAll() {
  FINGER_DEFS.forEach(({ key }) => {
    if (capturedData[key]) {
      setTimeout(() => downloadImg(capturedData[key].imageDataURL, key.toLowerCase() + '_finger.jpg'),
                 FINGER_DEFS.findIndex(f=>f.key===key) * 200);
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Tabs
// ─────────────────────────────────────────────────────────────────────────────
function switchTab(name) {
  ['capture','enroll','verify','audit'].forEach((n, i) => {
    document.querySelectorAll('.tab')[i].classList.toggle('active', n===name);
    document.getElementById('pane-'+n).classList.toggle('active', n===name);
  });
  if (name === 'audit') loadAudit();
}

// ─────────────────────────────────────────────────────────────────────────────
// Enroll
// ─────────────────────────────────────────────────────────────────────────────
async function captureForEnroll() {
  const hand = document.getElementById('enrollHand').value;
  log('enrollLog', 'Capturing ' + hand + '…', 'info');
  // Use current scratch canvas frame
  const b64 = scratchCanvas.toDataURL('image/jpeg', 0.92).split(',')[1] ||
              captureFromVideo();
  try {
    const res  = await fetch(BASE + '/api/capture/multi', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ transaction_id: txnId, image_base64: b64, hand })
    });
    const data = await res.json();
    enrollBuffer = {};
    const ok = [];
    (data.results||[]).forEach(r => {
      if (r.status==='success' && r.template) {
        enrollBuffer[r.finger_id] = { finger_id:r.finger_id, template:r.template,
                                      quality_score:r.quality_score };
        ok.push(r.finger_id.replace(hand+'_',''));
        log('enrollLog', r.finger_id + ' Q=' + r.quality_score.toFixed(1) +
            ' blur=' + (r.blur_score!=null?r.blur_score.toFixed(0):'?') +
            ' illum=' + (r.contrast_score!=null?r.contrast_score.toFixed(0):'?'), 'ok');
      } else {
        log('enrollLog', r.finger_id + ' ✗ ' + (r.error_code||'?') +
            (r.guidance_message ? ' — '+r.guidance_message : ''), 'err');
      }
    });
    if (ok.length) {
      document.getElementById('enrollBtn').disabled = false;
      log('enrollLog', 'Ready: ' + ok.join(', '), 'ok');
    } else {
      log('enrollLog', data.guidance || 'No fingers captured', 'err');
    }
  } catch(e) { log('enrollLog', 'Error: ' + e.message, 'err'); }
}

async function submitEnroll() {
  const uid     = document.getElementById('enrollUid').value.trim();
  const fingers = Object.values(enrollBuffer);
  if (!uid)           { log('enrollLog','Enter a User ID','err'); return; }
  if (!fingers.length){ log('enrollLog','Capture fingers first','err'); return; }
  log('enrollLog', 'Enrolling ' + uid + ' (' + fingers.length + ')…', 'info');
  try {
    const res = await fetch(BASE+'/api/enroll', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ user_id:uid, transaction_id:txnId, fingers })
    });
    const d = await res.json();
    log('enrollLog', 'Enrolled! ID: ' + d.enrollment_id, 'ok');
    log('enrollLog', d.fingers_enrolled.join(', '), 'ok');
    enrollBuffer = {};
    document.getElementById('enrollBtn').disabled = true;
  } catch(e) { log('enrollLog','Error: '+e.message,'err'); }
}

// ─────────────────────────────────────────────────────────────────────────────
// Verify
// ─────────────────────────────────────────────────────────────────────────────
function captureFromVideo() {
  const tmp = document.createElement('canvas');
  tmp.width  = videoEl.videoWidth  || 640;
  tmp.height = videoEl.videoHeight || 480;
  tmp.getContext('2d').drawImage(videoEl, 0, 0);
  return tmp.toDataURL('image/jpeg', 0.88).split(',')[1];
}

async function captureAndVerify() {
  const uid = document.getElementById('verifyUid').value.trim();
  const fid = document.getElementById('verifyFinger').value;
  if (!uid) { log('verifyLog','Enter a User ID','err'); return; }
  log('verifyLog', 'Verifying ' + fid + ' for ' + uid + '…', 'info');
  setGuide('Capturing for verification…','warn');
  const b64 = captureFromVideo();
  try {
    const res = await fetch(BASE+'/api/verify', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ user_id:uid, transaction_id:txnId,
                             fingers:[{finger_id:fid, image_base64:b64}] })
    });
    const d     = await res.json();
    const match = d.match;
    const conf  = (d.confidence||0)*100;

    document.getElementById('vResult').style.display='block';
    document.getElementById('vMatch').textContent = match?'MATCHED ✓':'NO MATCH';
    document.getElementById('vMatch').className   = 'pill '+(match?'pill-g':'pill-r');
    document.getElementById('vConf').textContent  = conf.toFixed(1)+'%';
    document.getElementById('vBar').style.width      = conf+'%';
    document.getElementById('vBar').style.background = match?'#2ecc71':'#ef4444';
    document.getElementById('vMsg').textContent   = d.message||'';
    document.getElementById('vCard').style.borderColor = match?'#2ecc71':'#da3633';
    setGuide(match?'Identity verified!':'No match found', match?'ok':'err');
    log('verifyLog',(match?'MATCH':'NO MATCH')+' conf='+conf.toFixed(1)+'%',match?'ok':'err');
  } catch(e) {
    log('verifyLog','Error: '+e.message,'err');
    setGuide('Verification error','err');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Audit
// ─────────────────────────────────────────────────────────────────────────────
async function loadAudit() {
  try {
    const rows = await (await fetch(BASE+'/api/audit/logs?limit=30')).json();
    const body = document.getElementById('auditBody');
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="5" style="color:#484f58;text-align:center;padding:10px">No logs yet</td></tr>';
      return;
    }
    body.innerHTML = rows.map(l => {
      const t   = new Date(l.created_at).toLocaleTimeString('en',{hour12:false});
      const e   = l.event_type||'?';
      const cls = 'ep ep-'+(e[0]||'C');
      const qs  = l.quality_score!=null ? l.quality_score.toFixed(0) : '—';
      const st  = l.status==='success'
        ? '<span style="color:#2ecc71">✓</span>'
        : '<span style="color:#f85149">✗</span>';
      return `<tr>
        <td>${t}</td>
        <td><span class="${cls}">${e}</span></td>
        <td>${st}</td>
        <td>${l.user_id||'—'}</td>
        <td>${qs}</td>
      </tr>`;
    }).join('');
  } catch(e) {
    document.getElementById('auditBody').innerHTML =
      '<tr><td colspan="5" style="color:#f85149;text-align:center">Failed to load</td></tr>';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Log util
// ─────────────────────────────────────────────────────────────────────────────
function log(id, msg, type) {
  const el = document.getElementById(id);
  const s  = document.createElement('span');
  s.className   = type||'info';
  s.textContent = new Date().toLocaleTimeString('en',{hour12:false})+'  '+msg+'\\n';
  el.appendChild(s);
  el.scrollTop  = el.scrollHeight;
}
</script>
</body>
</html>"""
