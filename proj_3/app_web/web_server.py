import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from robot_engine import save_config

VALID_MODES = ("uchiha", "senju", "kurama", "byakugan")
VALID_MOODS = ("auto", "normal", "battle", "happy", "sleepy", "surprised", "love")
VALID_VARIANTS = (
    "auto", "sharingan", "mangekyo_itachi", "mangekyo_sasuke",
    "mangekyo_obito", "rinnegan", "combo",
)

HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Naruto Robot Studio â€” Luckfox</title>
<style>
  :root {
    --bg: #07090e;
    --surface: rgba(17, 21, 31, 0.85);
    --surface-2: rgba(26, 32, 46, 0.74);
    --border: rgba(255, 255, 255, 0.08);
    --text: #f3f5fa;
    --muted: #8b95ab;
    --accent: #ef4444;
    --accent-glow: rgba(239, 68, 68, 0.28);
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0;
    min-height: 100vh;
    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background:
      radial-gradient(680px circle at 50% -10%, var(--accent-glow), transparent 65%),
      radial-gradient(480px circle at 90% 100%, rgba(99, 102, 241, 0.12), transparent 60%),
      var(--bg);
    color: var(--text);
    display: flex;
    justify-content: center;
    padding: 18px 14px 36px;
    transition: background 0.35s ease;
  }
  .shell {
    width: 100%;
    max-width: 460px;
    background: var(--surface);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid var(--border);
    border-radius: 26px;
    padding: 20px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.62), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  .brand { display: flex; align-items: center; gap: 10px; }
  .brand-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--accent); box-shadow: 0 0 12px var(--accent);
    transition: 0.3s;
  }
  .brand h1 { margin: 0; font-size: 16px; font-weight: 700; letter-spacing: 0.2px; }
  .brand span { display: block; font-size: 11px; color: var(--muted); font-weight: 500; }
  .pill {
    font-size: 11px; font-weight: 600; padding: 5px 10px; border-radius: 999px;
    background: rgba(16, 185, 129, 0.12); color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.25);
    display: inline-flex; align-items: center; gap: 6px;
  }
  .pill::before {
    content: ""; width: 6px; height: 6px; border-radius: 50%;
    background: #34d399; box-shadow: 0 0 8px #34d399;
  }

  /* Robot Visor Live Preview */
  .visor-wrap {
    position: relative;
    background: linear-gradient(145deg, #161a26, #0a0c12);
    border-radius: 22px; padding: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.8), 0 10px 28px rgba(0, 0, 0, 0.45);
    margin-bottom: 16px;
  }
  .visor-screen {
    position: relative; width: 100%; aspect-ratio: 4 / 3;
    background: #000; border-radius: 14px; overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.06);
    touch-action: none; cursor: crosshair;
  }
  .visor-screen::after {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, transparent 38%, transparent 100%);
    pointer-events: none;
  }
  #preview { width: 100%; height: 100%; display: block; }
  .visor-hint {
    text-align: center; font-size: 11px; color: var(--muted);
    margin-top: 7px; display: flex; justify-content: space-between; align-items: center; padding: 0 4px;
  }
  .link-btn {
    background: none; border: none; color: var(--accent);
    font-size: 11px; font-weight: 600; cursor: pointer; padding: 2px 6px;
  }

  .section-label {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1px; color: var(--muted); margin: 14px 0 9px 2px;
  }

  /* 4 Clan Cards */
  .clan-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
  .clan-btn {
    padding: 12px; border-radius: 15px;
    border: 1px solid var(--border); background: var(--surface-2);
    color: var(--text); cursor: pointer; text-align: left;
    transition: all 0.2s ease; display: flex; flex-direction: column; gap: 3px;
  }
  .clan-btn:hover { border-color: rgba(255, 255, 255, 0.2); transform: translateY(-1px); }
  .clan-btn .title { font-size: 13.5px; font-weight: 700; display: flex; justify-content: space-between; align-items: center; }
  .clan-btn .sub { font-size: 11px; color: var(--muted); }
  .clan-btn.active {
    border-color: var(--accent);
    background: linear-gradient(145deg, var(--accent-glow), rgba(20, 24, 34, 0.6));
    box-shadow: 0 0 22px var(--accent-glow);
  }
  .dot-tag { width: 8px; height: 8px; border-radius: 50%; }

  /* Variant Chips */
  .chip-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    padding: 7px 11px; border-radius: 10px;
    border: 1px solid var(--border); background: rgba(12, 15, 22, 0.72);
    color: var(--muted); font-size: 11.5px; font-weight: 600;
    cursor: pointer; transition: all 0.18s ease;
  }
  .chip:hover { color: var(--text); border-color: rgba(255,255,255,0.18); }
  .chip.active { background: var(--accent-glow); border-color: var(--accent); color: #fff; }

  /* Mood Grid (7 moods -> responsive 4 cols) */
  .mood-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; }
  .mood-btn {
    padding: 9px 4px; border-radius: 13px;
    border: 1px solid var(--border); background: var(--surface-2);
    color: var(--muted); cursor: pointer;
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    font-size: 11px; font-weight: 600; transition: all 0.18s ease;
  }
  .mood-btn .ico { font-size: 15px; line-height: 1; font-family: ui-monospace, monospace; color: var(--text); }
  .mood-btn:hover { border-color: rgba(255,255,255,0.2); color: var(--text); }
  .mood-btn.active { border-color: var(--accent); background: var(--accent-glow); color: #fff; }

  /* Action Row */
  .action-row { display: grid; grid-template-columns: 1fr 1.35fr; gap: 9px; margin-top: 14px; }
  .action-btn {
    padding: 11px 10px; border-radius: 13px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: linear-gradient(135deg, rgba(255,255,255,0.09), rgba(255,255,255,0.03));
    color: var(--text); font-size: 12.5px; font-weight: 600; cursor: pointer;
    transition: all 0.18s ease;
  }
  .action-btn.primary {
    border-color: var(--accent);
    background: linear-gradient(135deg, var(--accent-glow), rgba(255,255,255,0.04));
    color: #fff;
  }
  .action-btn:active { transform: scale(0.98); }

  /* Settings Card */
  .settings-card {
    margin-top: 14px; padding: 14px; border-radius: 16px;
    background: rgba(11, 14, 22, 0.65); border: 1px solid var(--border);
    display: flex; flex-direction: column; gap: 12px;
  }
  .row { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
  .row-label { font-size: 12.5px; font-weight: 600; }
  .row-sub { font-size: 11px; color: var(--muted); display: block; }

  /* Toggle Switch */
  .switch { position: relative; width: 42px; height: 24px; flex-shrink: 0; }
  .switch input { opacity: 0; width: 0; height: 0; }
  .slider-sw {
    position: absolute; inset: 0; background: #262d3d; border-radius: 999px;
    cursor: pointer; transition: 0.25s;
  }
  .slider-sw::before {
    content: ""; position: absolute; width: 18px; height: 18px; left: 3px; top: 3px;
    border-radius: 50%; background: #fff; transition: 0.25s;
  }
  .switch input:checked + .slider-sw { background: var(--accent); }
  .switch input:checked + .slider-sw::before { transform: translateX(18px); }

  /* Brightness & Speed */
  .mini-seg { display: flex; gap: 5px; }
  .mini-btn {
    padding: 5px 10px; border-radius: 8px; border: 1px solid var(--border);
    background: var(--surface-2); color: var(--muted); font-size: 11.5px; font-weight: 600; cursor: pointer;
  }
  .mini-btn.active { border-color: var(--accent); background: var(--accent-glow); color: #fff; }
  input[type="range"] { width: 120px; accent-color: var(--accent); cursor: pointer; }

  .hidden { display: none !important; }
</style>
</head>
<body>
  <div class="shell">
    <div class="header">
      <div class="brand">
        <div class="brand-dot"></div>
        <div>
          <h1>Naruto Robot Studio</h1>
          <span>Luckfox ST7789 Â· Auto-Save Config</span>
        </div>
      </div>
      <div class="pill" id="conn-pill">Online</div>
    </div>

    <div class="visor-wrap">
      <div class="visor-screen" id="visor-pad">
        <canvas id="preview" width="320" height="240"></canvas>
      </div>
      <div class="visor-hint">
        <span id="gaze-status">Vuá»‘t trÃªn mÃ n hÃ¬nh Ä‘á»ƒ Ä‘iá»u hÆ°á»›ng máº¯t nhÃ¬n</span>
        <button class="link-btn" onclick="resetGaze()">Tá»± Ä‘á»™ng nhÃ¬n</button>
      </div>
    </div>

    <div class="section-label">Nháº«n Thuáº­t (4 Cháº¿ Äá»™ Máº¯t)</div>
    <div class="clan-grid">
      <button class="clan-btn" data-mode="uchiha" onclick="updateState({mode:'uchiha'})">
        <span class="title">Uchiha <span class="dot-tag" style="background:#ef4444;box-shadow:0 0 8px #ef4444"></span></span>
        <span class="sub">Sharingan Â· MangekyÅ Â· Rinne</span>
      </button>
      <button class="clan-btn" data-mode="senju" onclick="updateState({mode:'senju'})">
        <span class="title">Senju <span class="dot-tag" style="background:#f59e0b;box-shadow:0 0 8px #f59e0b"></span></span>
        <span class="sub">TiÃªn NhÃ¢n Thuáº­t (Sage)</span>
      </button>
      <button class="clan-btn" data-mode="kurama" onclick="updateState({mode:'kurama'})">
        <span class="title">Kurama <span class="dot-tag" style="background:#ff5722;box-shadow:0 0 8px #ff5722"></span></span>
        <span class="sub">Cá»­u VÄ© Â· RÃ¢u CÃ¡o Neon</span>
      </button>
      <button class="clan-btn" data-mode="byakugan" onclick="updateState({mode:'byakugan'})">
        <span class="title">Byakugan <span class="dot-tag" style="background:#c4cff8;box-shadow:0 0 8px #c4cff8"></span></span>
        <span class="sub">Báº¡ch NhÃ£n Â· GÃ¢n Chakra</span>
      </button>
    </div>

    <div id="uchiha-variants">
      <div class="section-label">Biáº¿n Thá»ƒ Máº¯t Uchiha</div>
      <div class="chip-wrap">
        <button class="chip" data-var="auto" onclick="updateState({variant:'auto'})">Tá»± Ä‘á»™ng</button>
        <button class="chip" data-var="sharingan" onclick="updateState({variant:'sharingan'})">Sharingan</button>
        <button class="chip" data-var="mangekyo_itachi" onclick="updateState({variant:'mangekyo_itachi'})">Itachi MS</button>
        <button class="chip" data-var="mangekyo_sasuke" onclick="updateState({variant:'mangekyo_sasuke'})">Sasuke MS</button>
        <button class="chip" data-var="mangekyo_obito" onclick="updateState({variant:'mangekyo_obito'})">Obito MS</button>
        <button class="chip" data-var="rinnegan" onclick="updateState({variant:'rinnegan'})">Rinnegan</button>
        <button class="chip" data-var="combo" onclick="updateState({variant:'combo'})">Combo</button>
      </div>
    </div>

    <div class="section-label">Biá»ƒu Cáº£m Robot Emoji</div>
    <div class="mood-grid">
      <button class="mood-btn" data-mood="auto" onclick="updateState({mood:'auto'})"><span class="ico">âœ¦</span><span>Auto</span></button>
      <button class="mood-btn" data-mood="normal" onclick="updateState({mood:'normal'})"><span class="ico">â—‰â—‰</span><span>TÄ©nh</span></button>
      <button class="mood-btn" data-mood="battle" onclick="updateState({mood:'battle'})"><span class="ico">\ /</span><span>Chiáº¿n</span></button>
      <button class="mood-btn" data-mood="happy" onclick="updateState({mood:'happy'})"><span class="ico">^ ^</span><span>Vui</span></button>
      <button class="mood-btn" data-mood="surprised" onclick="updateState({mood:'surprised'})"><span class="ico">O O</span><span>Ngáº¡c</span></button>
      <button class="mood-btn" data-mood="love" onclick="updateState({mood:'love'})"><span class="ico">â™¥ â™¥</span><span>YÃªu</span></button>
      <button class="mood-btn" data-mood="sleepy" onclick="updateState({mood:'sleepy'})"><span class="ico">- -</span><span>Ngá»§</span></button>
    </div>

    <div class="action-row">
      <button class="action-btn" onclick="triggerBlink()">Chá»›p Máº¯t</button>
      <button class="action-btn primary" onclick="triggerPowerUp()">âš¡ KÃ­ch Hoáº¡t Nháº«n Thuáº­t</button>
    </div>

    <div class="settings-card">
      <div class="row">
        <div><span class="row-label">Äá»“ng Há»“ HUD (Giá» / NgÃ y)</span><span class="row-sub">Hiá»ƒn thá»‹ gá»n á»Ÿ gÃ³c trÃªn mÃ n hÃ¬nh</span></div>
        <label class="switch"><input type="checkbox" id="sw-hud" onchange="updateState({hud: this.checked ? 1 : 0})"><span class="slider-sw"></span></label>
      </div>
      <div class="row">
        <div><span class="row-label">Cháº¿ Äá»™ Ban ÄÃªm (22h â€“ 6h)</span><span class="row-sub">Tá»± giáº£m sÃ¡ng & chuyá»ƒn tráº¡ng thÃ¡i ngá»§</span></div>
        <label class="switch"><input type="checkbox" id="sw-night" onchange="updateState({night_mode: this.checked ? 1 : 0})"><span class="slider-sw"></span></label>
      </div>
      <div class="row">
        <span class="row-label">Äá»™ SÃ¡ng</span>
        <div class="mini-seg">
          <button class="mini-btn" data-br="40" onclick="updateState({brightness:40})">40%</button>
          <button class="mini-btn" data-br="70" onclick="updateState({brightness:70})">70%</button>
          <button class="mini-btn" data-br="100" onclick="updateState({brightness:100})">100%</button>
        </div>
      </div>
      <div class="row">
        <span class="row-label">Tá»‘c Äá»™ Xoay (<span id="spd-val">3</span>x)</span>
        <input type="range" id="rng-speed" min="1" max="5" step="1" value="3" oninput="document.getElementById('spd-val').textContent=this.value" onchange="updateState({speed: this.value})">
      </div>
    </div>
  </div>

<script>
  let curState = { mode: 'uchiha', mood: 'auto', variant: 'auto', hud: true, speed: 3, brightness: 100, night_mode: false, gaze_manual: false, gaze_x: 0, gaze_y: 0 };
  let blinkPhase = 0;
  let powerupPhase = 0;
  let lastGazeSend = 0;

  async function updateState(patch) {
    const params = new URLSearchParams(patch);
    try {
      const res = await fetch('/api/state?' + params.toString());
      curState = await res.json();
      document.getElementById('conn-pill').textContent = 'Online';
      renderUI();
    } catch (e) {
      document.getElementById('conn-pill').textContent = 'Offline';
    }
  }

  function triggerBlink() { blinkPhase = 1.0; fetch('/api/state?blink=1').catch(() => {}); }
  function triggerPowerUp() { powerupPhase = 1.0; fetch('/api/state?powerup=1').catch(() => {}); }
  function resetGaze() { updateState({ gaze_manual: 0, gaze_x: 0, gaze_y: 0 }); }

  function renderUI() {
    const accents = {
      uchiha: curState.variant === 'rinnegan' ? ['#a855f7', 'rgba(168,85,247,0.28)'] : ['#ef4444', 'rgba(239,68,68,0.28)'],
      senju: ['#f59e0b', 'rgba(245,158,11,0.26)'],
      kurama: ['#ff5722', 'rgba(255,87,34,0.28)'],
      byakugan: ['#94a8f8', 'rgba(148,168,248,0.26)'],
    };
    const [ac, gl] = accents[curState.mode] || accents.uchiha;
    document.documentElement.style.setProperty('--accent', ac);
    document.documentElement.style.setProperty('--accent-glow', gl);

    document.querySelectorAll('.clan-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === curState.mode));
    document.getElementById('uchiha-variants').className = curState.mode === 'uchiha' ? '' : 'hidden';
    document.querySelectorAll('.chip').forEach(b => b.classList.toggle('active', b.dataset.var === curState.variant));
    document.querySelectorAll('.mood-btn').forEach(b => b.classList.toggle('active', b.dataset.mood === curState.mood));
    document.querySelectorAll('.mini-btn').forEach(b => b.classList.toggle('active', Number(b.dataset.br) === Number(curState.brightness)));

    document.getElementById('sw-hud').checked = !!curState.hud;
    document.getElementById('sw-night').checked = !!curState.night_mode;
    document.getElementById('rng-speed').value = curState.speed || 3;
    document.getElementById('spd-val').textContent = curState.speed || 3;
    document.getElementById('gaze-status').textContent = curState.gaze_manual
      ? `HÆ°á»›ng nhÃ¬n thá»§ cÃ´ng (${curState.gaze_x}, ${curState.gaze_y})`
      : 'Vuá»‘t trÃªn mÃ n hÃ¬nh Ä‘á»ƒ Ä‘iá»u hÆ°á»›ng máº¯t nhÃ¬n';
  }

  // --- Touch / Mouse Gaze Joystick tren khung Preview ---
  const pad = document.getElementById('visor-pad');
  let dragging = false;
  function handlePointer(clientX, clientY) {
    const r = pad.getBoundingClientRect();
    const nx = Math.max(-1, Math.min(1, ((clientX - r.left) / r.width) * 2 - 1));
    const ny = Math.max(-1, Math.min(1, ((clientY - r.top) / r.height) * 2 - 1));
    const gx = Math.round(nx * 12);
    const gy = Math.round(ny * 10);
    curState.gaze_manual = true;
    curState.gaze_x = gx;
    curState.gaze_y = gy;
    const now = performance.now();
    if (now - lastGazeSend > 75) {
      lastGazeSend = now;
      fetch(`/api/state?gaze_manual=1&gaze_x=${gx}&gaze_y=${gy}`).catch(() => {});
      document.getElementById('gaze-status').textContent = `HÆ°á»›ng nhÃ¬n thá»§ cÃ´ng (${gx}, ${gy})`;
    }
  }
  pad.addEventListener('pointerdown', e => { dragging = true; pad.setPointerCapture(e.pointerId); handlePointer(e.clientX, e.clientY); });
  pad.addEventListener('pointermove', e => { if (dragging) handlePointer(e.clientX, e.clientY); });
  pad.addEventListener('pointerup', () => { dragging = false; });

  // --- Live Canvas Preview ---
  const canvas = document.getElementById('preview');
  const ctx = canvas.getContext('2d');

  function roundRectPath(x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawHeartCanvas(cx, cy, sz, col) {
    ctx.fillStyle = col;
    const r = sz * 0.34, ox = sz * 0.3, ty = cy - sz * 0.14;
    ctx.beginPath(); ctx.arc(cx - ox, ty, r, 0, Math.PI * 2); ctx.arc(cx + ox, ty, r, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(cx - ox - r + 1, ty + r * 0.25); ctx.lineTo(cx + ox + r - 1, ty + r * 0.25); ctx.lineTo(cx, cy + sz * 0.62); ctx.closePath(); ctx.fill();
  }

  function drawSharinganBase(cx, cy, rot, kind, scale) {
    ctx.fillStyle = '#160306'; ctx.fillRect(cx - 80, cy - 80, 160, 160);
    const R = 39 * scale;
    const g = ctx.createRadialGradient(cx, cy, 6, cx, cy, R + 4);
    g.addColorStop(0, '#ff353d'); g.addColorStop(0.8, '#d8101a'); g.addColorStop(1, '#58050a');
    ctx.fillStyle = kind === 'mangekyo_sasuke' ? '#09090b' : g;
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();
    if (kind === 'mangekyo_sasuke') {
      ctx.strokeStyle = '#e6141e'; ctx.lineWidth = 3; ctx.stroke();
      for (let i = 0; i < 3; i++) {
        ctx.save(); ctx.translate(cx, cy); ctx.rotate(rot + (i * Math.PI) / 3);
        ctx.fillStyle = '#e6141e'; ctx.beginPath(); ctx.ellipse(0, 0, 32 * scale, 9 * scale, 0, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#09090b'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-26 * scale, 0); ctx.lineTo(26 * scale, 0); ctx.stroke();
        ctx.restore();
      }
      ctx.fillStyle = '#09090b'; ctx.beginPath(); ctx.arc(cx, cy, 4 * scale, 0, Math.PI * 2); ctx.fill();
    } else if (kind === 'mangekyo_itachi') {
      ctx.fillStyle = '#09090b';
      for (let i = 0; i < 3; i++) {
        for (let s = 0; s < 14; s++) {
          const t = s / 13, a = rot + (i * Math.PI * 2) / 3 + t * 1.25;
          ctx.beginPath(); ctx.arc(cx + (10 + t * 26) * scale * Math.cos(a), cy + (10 + t * 26) * scale * Math.sin(a), Math.max(2, 8 * (1 - t * 0.72) * scale), 0, Math.PI * 2); ctx.fill();
        }
      }
      ctx.beginPath(); ctx.arc(cx, cy, 10 * scale, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#ff4038'; ctx.beginPath(); ctx.arc(cx, cy, 4 * scale, 0, Math.PI * 2); ctx.fill();
    } else if (kind === 'mangekyo_obito') {
      ctx.strokeStyle = '#09090b'; ctx.lineWidth = 5 * scale;
      ctx.beginPath(); ctx.arc(cx, cy, 15 * scale, 0, Math.PI * 2); ctx.stroke();
      for (let i = 0; i < 3; i++) {
        const a0 = rot + (i * Math.PI * 2) / 3, a1 = a0 + 0.28, a2 = a0 + 0.9;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(cx + 15 * scale * Math.cos(a0), cy + 15 * scale * Math.sin(a0));
        ctx.lineTo(cx + 34 * scale * Math.cos(a1), cy + 34 * scale * Math.sin(a1));
        ctx.lineTo(cx + 30 * scale * Math.cos(a2), cy + 30 * scale * Math.sin(a2));
        ctx.stroke();
      }
    } else {
      ctx.strokeStyle = '#09090b'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(cx, cy, 22 * scale, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = '#09090b'; ctx.beginPath(); ctx.arc(cx, cy, 8 * scale, 0, Math.PI * 2); ctx.fill();
      for (let i = 0; i < 3; i++) {
        const a = rot + (i * Math.PI * 2) / 3;
        ctx.beginPath(); ctx.arc(cx + 22 * scale * Math.cos(a), cy + 22 * scale * Math.sin(a), 5 * scale, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx - 14, cy - 15, 5.5, 0, Math.PI * 2); ctx.fill();
  }

  function drawRinnegan(cx, cy, scale) {
    const g = ctx.createRadialGradient(cx, cy, 6, cx, cy, 56 * scale);
    g.addColorStop(0, '#dbc4fa'); g.addColorStop(0.6, '#a984e0'); g.addColorStop(1, '#26143d');
    ctx.fillStyle = g; ctx.fillRect(cx - 80, cy - 80, 160, 160);
    ctx.strokeStyle = '#1e1030'; ctx.lineWidth = 2;
    [11, 20, 29, 38, 47].forEach(r => { ctx.beginPath(); ctx.arc(cx, cy, r * scale, 0, Math.PI * 2); ctx.stroke(); });
    ctx.fillStyle = '#09090b'; ctx.beginPath(); ctx.arc(cx, cy, 4 * scale, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx - 14, cy - 15, 5.5, 0, Math.PI * 2); ctx.fill();
  }

  function drawSage(cx, cy, scale) {
    ctx.fillStyle = '#1a1002'; ctx.fillRect(cx - 80, cy - 80, 160, 160);
    const g = ctx.createRadialGradient(cx, cy, 6, cx, cy, 42 * scale);
    g.addColorStop(0, '#ffe45e'); g.addColorStop(0.75, '#f5a614'); g.addColorStop(1, '#6e3c04');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, 40 * scale, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#09090b'; roundRectPath(cx - 24 * scale, cy - 6 * scale, 48 * scale, 12 * scale, 6 * scale); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx - 14, cy - 15, 5.5, 0, Math.PI * 2); ctx.fill();
  }

  function drawKurama(cx, cy, scale, thin) {
    ctx.fillStyle = '#1e0602'; ctx.fillRect(cx - 80, cy - 80, 160, 160);
    const g = ctx.createRadialGradient(cx, cy, 6, cx, cy, 44 * scale);
    g.addColorStop(0, '#ff8c1a'); g.addColorStop(0.65, '#ff3b0e'); g.addColorStop(1, '#7a1204');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, 40 * scale, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#09090b';
    ctx.beginPath(); ctx.ellipse(cx, cy, (thin ? 4.5 : 8) * scale, 32 * scale, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx - 14, cy - 15, 5.5, 0, Math.PI * 2); ctx.fill();
  }

  function drawByakugan(cx, cy, scale) {
    ctx.fillStyle = '#161824'; ctx.fillRect(cx - 80, cy - 80, 160, 160);
    const g = ctx.createRadialGradient(cx, cy, 6, cx, cy, 52 * scale);
    g.addColorStop(0, '#f5f8ff'); g.addColorStop(0.7, '#d8e0fa'); g.addColorStop(1, '#8c99c8');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, 48 * scale, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = '#8791bc'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(cx, cy, 34 * scale, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, 15 * scale, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx - 14, cy - 15, 5.5, 0, Math.PI * 2); ctx.fill();
  }

  function drawPreview(t) {
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 320, 240);
    const mode = curState.mode;
    const effMood = curState.mood === 'auto' ? 'normal' : curState.mood;
    const effVar = curState.variant === 'auto' ? (effMood === 'battle' ? 'mangekyo_itachi' : 'combo') : curState.variant;
    const rot = t * 0.0007 * (curState.speed || 3);

    let gx = curState.gaze_manual ? curState.gaze_x : ((effMood === 'normal' || effMood === 'sleepy') ? Math.sin(t * 0.0012) * 8 : 0);
    let gy = curState.gaze_manual ? curState.gaze_y : ((effMood === 'normal') ? Math.sin(t * 0.0008) * 4 : 0);
    if (powerupPhase > 0) {
      powerupPhase = Math.max(0, powerupPhase - 0.04);
      gx += (Math.random() - 0.5) * 10; gy += (Math.random() - 0.5) * 6;
    }
    if (blinkPhase > 0) blinkPhase = Math.max(0, blinkPhase - 0.09);
    const openScale = blinkPhase > 0 ? Math.max(0.08, Math.abs(blinkPhase - 0.5) * 2) : 1.0;

    // Clock HUD
    if (curState.hud) {
      const d = new Date();
      const ts = String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
      const ds = String(d.getDate()).padStart(2,'0') + '/' + String(d.getMonth()+1).padStart(2,'0');
      ctx.font = 'bold 14px ui-monospace, monospace';
      ctx.fillStyle = '#b8c4dc'; ctx.fillText(ts, 12, 22);
      ctx.fillStyle = '#6c7790'; ctx.fillText(ds, 258, 22);
    }

    // Mode top/side accents
    const pulse = 0.55 + 0.45 * Math.sin(t * 0.005);
    if (mode === 'senju') {
      ctx.strokeStyle = `rgba(235,52,46,${pulse})`; ctx.fillStyle = `rgba(235,52,46,${pulse})`; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(160, 23, 12, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.arc(160, 23, 4.5, 0, Math.PI * 2); ctx.fill();
      ctx.fillRect(4, 96, 12, 6); ctx.fillRect(304, 96, 12, 6);
    } else if (mode === 'kurama') {
      ctx.fillStyle = `rgba(255,110,25,${pulse})`;
      [174, 186, 198].forEach((y, i) => { ctx.fillRect(4, y, 18 - i * 2, 4); ctx.fillRect(316 - (18 - i * 2), y, 18 - i * 2, 4); });
    } else if (mode === 'byakugan' && effMood === 'battle') {
      ctx.fillStyle = '#a5b4e2';
      ctx.fillRect(5, 86, 12, 3); ctx.fillRect(9, 89, 3, 14); ctx.fillRect(4, 102, 13, 3);
      ctx.fillRect(303, 86, 12, 3); ctx.fillRect(308, 89, 3, 14); ctx.fillRect(303, 102, 13, 3);
    } else if (mode === 'uchiha') {
      ctx.fillStyle = effVar === 'rinnegan' ? '#a855f7' : '#ef4444';
      roundRectPath(136, 18, 48, 4, 2); ctx.fill();
    }

    const scale = effMood === 'surprised' ? 0.7 : 1.0;
    const eyes = [{ x: 24, right: false }, { x: 172, right: true }];
    eyes.forEach(e => {
      const cx = e.x + 62, cy = 48 + 58;
      const isRinn = mode === 'uchiha' && (effVar === 'rinnegan' || (effVar === 'combo' && e.right));
      const rim = mode === 'senju' ? '#eba518' : (mode === 'kurama' ? '#ff6a18' : (mode === 'byakugan' ? '#bcc8f0' : (isRinn ? '#a880e8' : '#c81c26')));

      if (effMood === 'happy') {
        ctx.strokeStyle = rim; ctx.lineWidth = 11; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.arc(cx, 126, 36, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke();
        ctx.strokeStyle = '#fff5f5'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.arc(cx, 126, 36, Math.PI * 1.2, Math.PI * 1.8); ctx.stroke();
        return;
      }
      if (effMood === 'love') {
        const beat = 70 + 8 * Math.sin(t * 0.01);
        drawHeartCanvas(cx, cy, beat, rim);
        ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx - 15, cy - 12, 5, 0, Math.PI * 2); ctx.fill();
        return;
      }

      const h = 116 * openScale, y = 48 + (116 - h) / 2;
      const rad = effMood === 'surprised' ? 46 : 34;
      ctx.save();
      roundRectPath(e.x, y, 124, h, Math.min(rad, h / 2));
      ctx.clip();

      if (mode === 'senju') drawSage(cx + gx, cy + gy, scale);
      else if (mode === 'kurama') drawKurama(cx + gx, cy + gy, scale, effMood === 'battle' || effMood === 'surprised');
      else if (mode === 'byakugan') drawByakugan(cx + gx, cy + gy, scale);
      else if (isRinn) drawRinnegan(cx + gx, cy + gy, scale);
      else drawSharinganBase(cx + gx, cy + gy, e.right ? -rot : rot, effVar === 'combo' ? 'sharingan' : effVar, scale);

      if (effMood === 'battle' || powerupPhase > 0) {
        ctx.fillStyle = '#000'; ctx.beginPath();
        if (!e.right) { ctx.moveTo(e.x, 48); ctx.lineTo(e.x + 124, 48); ctx.lineTo(e.x + 124, 94); }
        else          { ctx.moveTo(e.x, 48); ctx.lineTo(e.x + 124, 48); ctx.lineTo(e.x, 94); }
        ctx.closePath(); ctx.fill();
      } else if (effMood === 'sleepy') {
        ctx.fillStyle = '#000'; ctx.fillRect(e.x, 48, 124, 44);
      }
      ctx.restore();

      ctx.strokeStyle = rim; ctx.lineWidth = 2.2;
      roundRectPath(e.x, y, 124, h, Math.min(rad, h / 2)); ctx.stroke();
    });

    // Mouth
    const mCol = effMood === 'normal' || effMood === 'sleepy' ? '#eef2f8'
      : (mode === 'senju' ? '#fac62d' : (mode === 'kurama' ? '#ff7323' : (mode === 'byakugan' ? '#d2dcfc' : (effVar === 'rinnegan' ? '#c6a2f5' : '#f54650'))));
    ctx.strokeStyle = mCol; ctx.fillStyle = mCol; ctx.lineWidth = 4.5; ctx.lineCap = 'round';
    if (effMood === 'normal') { ctx.beginPath(); ctx.arc(160, 192, 20, Math.PI * 0.22, Math.PI * 0.78); ctx.stroke(); }
    else if (effMood === 'happy' || effMood === 'love') { ctx.beginPath(); ctx.arc(160, 190, 22, Math.PI * 0.12, Math.PI * 0.88); ctx.stroke(); }
    else if (effMood === 'battle') { roundRectPath(140, 201, 40, 6, 3); ctx.fill(); }
    else if (effMood === 'sleepy') { ctx.beginPath(); ctx.arc(160, 204, 7, 0, Math.PI * 2); ctx.stroke(); }
    else if (effMood === 'surprised') { ctx.beginPath(); ctx.arc(160, 205, 11, 0, Math.PI * 2); ctx.stroke(); }

    // Brightness overlay preview
    const br = (curState.brightness || 100) / 100;
    if (br < 0.99) {
      ctx.fillStyle = `rgba(0,0,0,${1 - br})`;
      ctx.fillRect(0, 0, 320, 240);
    }

    requestAnimationFrame(drawPreview);
  }

  fetch('/api/state').then(r => r.json()).then(d => { curState = d; renderUI(); }).catch(() => {});
  requestAnimationFrame(drawPreview);
</script>
</body>
</html>
"""


def start_web_server(state, port=8080):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send_json(self, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ("/api/state", "/api/mode"):
                qs = parse_qs(parsed.query)
                changed_cfg = False

                mode = qs.get("mode", qs.get("set", [None]))[0]
                if mode in VALID_MODES:
                    state["mode"] = mode
                    changed_cfg = True
                    print(f"[Web] Nhan thuat -> {mode.upper()}")

                mood = qs.get("mood", [None])[0]
                if mood in VALID_MOODS:
                    state["mood"] = mood
                    changed_cfg = True
                    print(f"[Web] Bieu cam -> {mood.upper()}")

                variant = qs.get("variant", [None])[0]
                if variant in VALID_VARIANTS:
                    state["variant"] = variant
                    changed_cfg = True
                    print(f"[Web] Bien the -> {variant.upper()}")

                if "hud" in qs:
                    state["hud"] = qs["hud"][0] in ("1", "true", "True")
                    changed_cfg = True

                if "night_mode" in qs:
                    state["night_mode"] = qs["night_mode"][0] in ("1", "true", "True")
                    changed_cfg = True

                if "brightness" in qs:
                    try:
                        state["brightness"] = max(30, min(100, int(qs["brightness"][0])))
                        changed_cfg = True
                    except ValueError:
                        pass

                if "speed" in qs:
                    try:
                        state["speed"] = max(1, min(5, int(qs["speed"][0])))
                        changed_cfg = True
                    except ValueError:
                        pass

                if "gaze_manual" in qs:
                    state["gaze_manual"] = qs["gaze_manual"][0] in ("1", "true", "True")
                if "gaze_x" in qs:
                    try:
                        state["gaze_x"] = max(-12, min(12, int(qs["gaze_x"][0])))
                    except ValueError:
                        pass
                if "gaze_y" in qs:
                    try:
                        state["gaze_y"] = max(-10, min(10, int(qs["gaze_y"][0])))
                    except ValueError:
                        pass

                if qs.get("blink", ["0"])[0] == "1":
                    state["blink"] = True
                if qs.get("powerup", ["0"])[0] == "1":
                    state["powerup"] = True

                if changed_cfg:
                    save_config(state)

                self._send_json({
                    "mode": state["mode"],
                    "mood": state["mood"],
                    "variant": state["variant"],
                    "hud": state["hud"],
                    "speed": state["speed"],
                    "brightness": state["brightness"],
                    "night_mode": state["night_mode"],
                    "gaze_manual": state["gaze_manual"],
                    "gaze_x": state["gaze_x"],
                    "gaze_y": state["gaze_y"],
                })
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(HTML_PAGE.encode("utf-8"))

    server = HTTPServer(("0.0.0.0", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server
