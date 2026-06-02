/* ============================================================
   КАПИБАРА-КЛИКЕР: ЭТАЖ 9000  ·  game.js  ·  v0.4.0
   «КАРМАННЫЙ ЭТАЖ» — iPhone-first переписка.
   ------------------------------------------------------------
   Что нового против v0.3.0:
   · Один экран без скролла страницы: HUD сверху, геймплей в центре,
     магазин снизу. Все «панели» (скины, рекорд, ачивки, статы,
     настройки, помощь) уехали в ВЫДВИЖНУЮ ШТОРКУ — свайп вниз.
   · Баланс: тап = (плоская мощь + % от КК/сек), поэтому тапать
     полезно всю игру. У каждого работника майлстоун-множители ×2
     (10/25/50/100/...). Престиж — понятные «кринж-очки».
   · Золотая капибара (вместо чит-гэга): пролетает по экрану, тап —
     жирный бонус. Это «стимуляция между эвентами».
   · DJ-ноты замедлены (по фидбеку), окно попадания шире, есть линия.
   · Лидерборд-генерёнка убрана: только твой личный рекорд.
   · Звук / Вибро / Анимации — тумблеры в настройках.
   Сейв: localStorage, ключ "DEVIN_MEGA_CAPYBARA_v1" (старые сейвы живут).
   ============================================================ */

'use strict';

const VERSION = '0.4.0';
const VERSION_NAME = 'КАРМАННЫЙ ЭТАЖ';

/* ---------- утилиты ---------- */
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const rand = (a, b) => Math.random() * (b - a) + a;
const randInt = (a, b) => Math.floor(rand(a, b + 1));
const pick = (a) => a[Math.floor(Math.random() * a.length)];
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const fmt = (n) => {
  if (n < 0) return '-' + fmt(-n);
  if (n === 0) return '0';
  if (n < 1) return n.toFixed(2);
  if (n < 1000) return (n < 10 ? n.toFixed(1) : String(Math.floor(n)));
  const u = ['', 'к', 'М', 'Б', 'Т', 'кв', 'кн', 'скб', 'крнж'];
  let i = 0;
  while (n >= 1000 && i < u.length - 1) { n /= 1000; i++; }
  return n.toFixed(n < 10 ? 2 : n < 100 ? 1 : 0) + u[i];
};

/* ---------- баланс (всё, что крутим — тут) ---------- */
const BAL = {
  COST_GROWTH: 1.15,                                  // удорожание работника за штуку
  MILESTONES: [10, 25, 50, 100, 150, 200, 300, 400],  // ×2 за каждый порог владения
  TAP_PCT_BASE: 0.01,                                 // тап = +1% от КК/сек (растёт апгрейдами)
  COMBO_CAP: 50, COMBO_STEP: 0.04,                    // комбо до ×3 при 50
  CRIT_BASE: 0.05, CRIT_PER_COMBO: 0.004, CRIT_CAP: 0.25, CRIT_MULT: 7,
  COMBO_DECAY: 2400,                                  // мс паузы → комбо сброс
  OFFLINE_RATE: 0.55, OFFLINE_MAX_H: 8,               // оффлайн 55%, до 8 часов
  GOLDEN_MIN: 45, GOLDEN_MAX: 95,                     // золотая капибара раз в 45–95 с
  EVENT_MIN: 30, EVENT_MAX: 70,                       // эвент раз в 30–70 с
  PRESTIGE_UNLOCK: 1e6, PRESTIGE_PER_POINT: 0.10,     // престиж: +10% за очко
};

/* ---------- состояние ---------- */
const SAVE_KEY = 'DEVIN_MEGA_CAPYBARA_v1';
const NAME_KEY = 'DEVIN_MEGA_CAPYBARA_NAME';
const BEST_KEY = 'DEVIN_MEGA_CAPYBARA_BEST';

const DEFAULT_STATE = () => ({
  coins: 0, totalCoins: 0,
  clicks: 0, events: 0, standups: 0,
  clickPower: 1, tapPercent: BAL.TAP_PCT_BASE,
  multiplier: 1,
  prestige: 0, prestigePoints: 0, prestigeMult: 1,
  combo: 0,
  workers: {}, upgrades: {}, achievements: {},
  // настройки
  muted: false, haptics: true, motion: true,
  // скины
  skin: { body: 0, hat: 0, face: 0 }, savedSkins: [], lockedSkin: false,
  // бафы золотой капибары
  buffs: { tapMult: 1, tapUntil: 0, cpsMult: 1, cpsUntil: 0 },
  lastSeen: Date.now(), version: VERSION,
});

let S = loadState();

function loadState() {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return DEFAULT_STATE();
    const obj = JSON.parse(raw);
    const s = { ...DEFAULT_STATE(), ...obj };
    if (!s.buffs) s.buffs = DEFAULT_STATE().buffs;
    if (typeof s.tapPercent !== 'number') s.tapPercent = BAL.TAP_PCT_BASE;
    // престиж никогда не уменьшаем (старые сейвы)
    s.prestigeMult = Math.max(s.prestigeMult || 1, 1 + BAL.PRESTIGE_PER_POINT * (s.prestigePoints || 0));
    return s;
  } catch (e) { return DEFAULT_STATE(); }
}
function saveState() {
  try { S.lastSeen = Date.now(); localStorage.setItem(SAVE_KEY, JSON.stringify(S)); } catch (e) {}
  // личный рекорд
  try {
    const best = +localStorage.getItem(BEST_KEY) || 0;
    if (S.totalCoins > best) localStorage.setItem(BEST_KEY, String(Math.floor(S.totalCoins)));
  } catch (e) {}
}

/* ============================================================
   СКИНЫ (как в v0.3.0: 5×4×4 = 80 комбо)
   ============================================================ */
const SKIN_BODY = [
  { id: 'std',    name: 'обычка',   body: '#a87b4a', head: '#b88955', dark: '#5e3d1c', leg: '#8a6238' },
  { id: 'white',  name: 'альбинос', body: '#f0e7d6', head: '#fff5e1', dark: '#5e3d1c', leg: '#d4c8b0' },
  { id: 'black',  name: 'нуарь',    body: '#3a2c2a', head: '#4a3a35', dark: '#000',    leg: '#251c1a' },
  { id: 'pink',   name: 'розовая',  body: '#ff8acc', head: '#ffabd8', dark: '#a31a78', leg: '#e072b0' },
  { id: 'rainbow',name: 'РАДУГА',   body: 'url(#capyRainbow)', head: 'url(#capyRainbow)', dark: '#1a0040', leg: 'url(#capyRainbow)' },
];
const SKIN_HAT = [
  { id: 'none',  name: 'без шапки' },
  { id: 'cap',   name: 'кепка',    svg: '<path d="M125 32 Q155 12 192 28 L195 38 L125 42 Z" fill="#ff4ec8" stroke="#000" stroke-width="3"/><rect x="155" y="38" width="34" height="4" fill="#fff34a" stroke="#000" stroke-width="2"/>' },
  { id: 'crown', name: 'корона',   svg: '<path d="M130 30 L138 12 L150 26 L162 8 L175 26 L188 12 L195 30 L188 40 L130 40 Z" fill="#fff34a" stroke="#000" stroke-width="3"/><circle cx="150" cy="22" r="3" fill="#ff4ec8" stroke="#000"/><circle cx="170" cy="22" r="3" fill="#34f7f7" stroke="#000"/>' },
  { id: 'space', name: 'космошлем',svg: '<ellipse cx="160" cy="32" rx="38" ry="22" fill="#34f7f7" fill-opacity="0.45" stroke="#000" stroke-width="3"/><ellipse cx="148" cy="28" rx="6" ry="4" fill="#fff" opacity="0.7"/>' },
];
const SKIN_FACE = [
  { id: 'none',    name: 'без аксов' },
  { id: 'specs',   name: 'очки',    svg: '<circle cx="170" cy="62" r="9" fill="none" stroke="#000" stroke-width="3"/><circle cx="190" cy="62" r="9" fill="none" stroke="#000" stroke-width="3"/><line x1="178" y1="62" x2="182" y2="62" stroke="#000" stroke-width="3"/>' },
  { id: 'mustache',name: 'усы',     svg: '<path d="M180 92 Q186 96 192 92 M180 92 Q174 96 168 92" fill="none" stroke="#1a1a1a" stroke-width="3" stroke-linecap="round"/>' },
  { id: 'chain',   name: 'цепь',    svg: '<path d="M120 110 Q160 130 195 108" fill="none" stroke="#fff34a" stroke-width="5"/><circle cx="160" cy="124" r="6" fill="#fff34a" stroke="#000" stroke-width="2"/><text x="160" y="128" font-size="9" font-weight="900" text-anchor="middle" fill="#000">$</text>' },
];

function skinDesc() {
  return {
    b: SKIN_BODY[S.skin.body % SKIN_BODY.length],
    h: SKIN_HAT[S.skin.hat % SKIN_HAT.length],
    f: SKIN_FACE[S.skin.face % SKIN_FACE.length],
  };
}
function skinName() { const { b, h, f } = skinDesc(); return `${b.name} / ${h.name} / ${f.name}`; }
function skinKey(s) { return `${s.body}-${s.hat}-${s.face}`; }

let capySvg;
function renderCapybara() {
  if (!capySvg) return;
  const { b, h, f } = skinDesc();
  capySvg.innerHTML = `
    <defs><linearGradient id="capyRainbow" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#ff4ec8"/><stop offset="33%" stop-color="#fff34a"/>
      <stop offset="66%" stop-color="#34f7f7"/><stop offset="100%" stop-color="#5dff8c"/>
    </linearGradient></defs>
    <ellipse cx="100" cy="100" rx="70" ry="42" fill="${b.body}" stroke="${b.dark}" stroke-width="3"/>
    <ellipse cx="55"  cy="135" rx="13" ry="18" fill="${b.leg}" stroke="${b.dark}" stroke-width="3"/>
    <ellipse cx="145" cy="135" rx="13" ry="18" fill="${b.leg}" stroke="${b.dark}" stroke-width="3"/>
    <ellipse cx="155" cy="70" rx="38" ry="32" fill="${b.head}" stroke="${b.dark}" stroke-width="3"/>
    <ellipse cx="135" cy="42" rx="8" ry="10" fill="${b.leg}" stroke="${b.dark}" stroke-width="2"/>
    <ellipse cx="170" cy="40" rx="8" ry="10" fill="${b.leg}" stroke="${b.dark}" stroke-width="2"/>
    <circle cx="170" cy="62" r="5" fill="#1a1a1a"/><circle cx="171" cy="60" r="1.5" fill="#fff"/>
    <ellipse cx="190" cy="78" rx="5" ry="3" fill="#3a2412"/>
    <path d="M178 88 Q188 92 195 86" fill="none" stroke="#3a2412" stroke-width="2" stroke-linecap="round"/>
    <rect x="183" y="86" width="3" height="6" fill="#fff" stroke="#3a2412" stroke-width="0.5"/>
    <rect x="187" y="86" width="3" height="6" fill="#fff" stroke="#3a2412" stroke-width="0.5"/>
    ${f.svg || ''}${h.svg || ''}`;
}
function randomizeSkin() {
  S.skin = { body: randInt(0, SKIN_BODY.length - 1), hat: randInt(0, SKIN_HAT.length - 1), face: randInt(0, SKIN_FACE.length - 1) };
  renderCapybara(); updateSkinPanel();
}
function saveCurrentSkin() {
  const cur = { ...S.skin, name: skinName() };
  if (S.savedSkins.some(s => skinKey(s) === skinKey(cur))) { speak('уже в галерее'); return; }
  S.savedSkins.push(cur); saveState(); updateSkinPanel(); sfxAch(); haptic(20); speak('💾 скин сохранён!');
}
function pickSavedSkin(i) {
  const s = S.savedSkins[i]; if (!s) return;
  S.skin = { body: s.body, hat: s.hat, face: s.face }; S.lockedSkin = true;
  renderCapybara(); updateSkinPanel(); speak('🎨 играем на нём');
}
function deleteSavedSkin(i) { S.savedSkins.splice(i, 1); saveState(); updateSkinPanel(); }
function unlockSkin() { S.lockedSkin = false; updateSkinPanel(); speak('🔓 снова рандом'); }

function updateSkinPanel() {
  const cur = $('#skin-current'); if (cur) cur.textContent = skinName();
  const st = $('#skin-status'); if (st) st.textContent = S.lockedSkin ? '🔒 закреплён' : '🎲 авто';
  const gal = $('#skin-gallery'); if (!gal) return;
  if (!S.savedSkins.length) { gal.innerHTML = '<li class="skin-empty">Пусто. Тапни «💾 Сохранить» — оставишь любимый скин.</li>'; return; }
  gal.innerHTML = '';
  S.savedSkins.forEach((s, i) => {
    const li = document.createElement('li'); li.className = 'skin-saved';
    li.innerHTML = `<span class="skin-saved__dot" style="background:${SKIN_BODY[s.body % SKIN_BODY.length].body}"></span>
      <span class="skin-saved__name">${s.name}</span>
      <button data-i="${i}" class="use">▶</button><button data-i="${i}" class="del">🗑</button>`;
    gal.appendChild(li);
  });
  gal.querySelectorAll('.use').forEach(b => b.onclick = () => pickSavedSkin(+b.dataset.i));
  gal.querySelectorAll('.del').forEach(b => b.onclick = () => deleteSavedSkin(+b.dataset.i));
}

/* ============================================================
   ЭКОНОМИКА
   ============================================================ */
const WORKERS = [
  { id: 'junior', name: 'Капибара-джун',  icon: '🦫',  base: 10,    cps: 0.2,  desc: 'Стажёр. Кликает медленно, плачет часто.' },
  { id: 'coffee', name: 'Кофеварка-3000', icon: '☕',  base: 60,    cps: 1,    desc: 'Льёт кофе. Иногда — на ноут.' },
  { id: 'mid',    name: 'Капибара-мидл',  icon: '🦫',  base: 1100,  cps: 8,    desc: 'Знает фреймворки. Не до конца.' },
  { id: 'qa',     name: 'Капибара-QA',    icon: '🐞',  base: 12000, cps: 47,   desc: 'Всё ломает. Но в хорошем смысле.' },
  { id: 'senior', name: 'Капибара-синьор',icon: '🧑‍💻', base: 130000,cps: 260,  desc: 'Архитектура головного мозга.' },
  { id: 'lead',   name: 'Капибара-тимлид',icon: '👔',  base: 1.4e6, cps: 1400,  desc: 'Орёт раз в 10 секунд. Эффективно.' },
  { id: 'devops', name: 'DevOps на 3-м энергетике', icon: '🛰️', base: 2e7, cps: 7800, desc: 'Не спит. Не моргает. Деплоит.' },
  { id: 'sigma',  name: 'Капибара-сигма', icon: '🕶️',  base: 3.3e8, cps: 44000, desc: 'Слушает phonk. В офисе. На колонке.' },
  { id: 'cto',    name: 'Капибара-CTO',   icon: '👑',  base: 5.1e9, cps: 260000,desc: 'На стендапе раз в квартал.' },
  { id: 'singularity', name: 'Сингулярность', icon: '🌌', base: 7.5e10, cps: 1.6e6, desc: 'Кликает в 4 измерениях.' },
];

const CLICK_UPGRADES = [
  { id: 'paw',    name: 'Когтистая лапка',  icon: '✋', cost: 100,    flat: 2,   desc: '+2 к мощи тапа.' },
  { id: 'hammer', name: 'Молот тимлида',    icon: '🔨', cost: 1500,   flat: 12,  desc: '+12 к мощи тапа.' },
  { id: 'mitt',   name: 'Боевые митенки',   icon: '🧤', cost: 15000,  pct: 0.01, desc: 'Тап = +1% от КК/сек.' },
  { id: 'laser',  name: 'Лазерный взгляд',  icon: '👁️', cost: 120000, flat: 90,  desc: '+90 к мощи тапа.' },
  { id: 'thanos', name: 'Перчатка Бесконечности', icon: '🪐', cost: 2.5e6, pct: 0.03, desc: 'Тап = ещё +3% от КК/сек.' },
  { id: 'cosmic', name: 'Космическая лапа', icon: '🌠', cost: 1.5e8, pct: 0.06, desc: 'Тап = ещё +6% от КК/сек.' },
];

const ULTRA_UPGRADES = [
  { id: 'doshik',   name: 'Корпоративный доширак', icon: '🍜', cost: 10000,  mult: 2, desc: '×2 ко всему доходу. Навсегда.' },
  { id: 'kombucha', name: 'Чайный гриб тимбилдинг',icon: '🫖', cost: 300000, mult: 2, desc: '×2 ко всему доходу.' },
  { id: 'lofi',     name: 'Lo-Fi радио 24/7',      icon: '🎧', cost: 6e6,    mult: 2, desc: '×2. Капибары работают под бит.' },
  { id: 'matrix',   name: 'Подключение к Матрице', icon: '💚', cost: 1.5e8,  mult: 3, desc: '×3 ко всему доходу.' },
  { id: 'wormhole', name: 'Червоточина в офисе',   icon: '🕳️', cost: 4e9,    mult: 3, desc: '×3. Письма приходят вчера.' },
];

const owned = (id) => S.workers[id] || 0;
function workerCost(w) { return Math.ceil(w.base * Math.pow(BAL.COST_GROWTH, owned(w.id))); }
function milestoneMult(n) { let m = 1; for (const t of BAL.MILESTONES) if (n >= t) m *= 2; return m; }
function nextMilestone(n) { for (const t of BAL.MILESTONES) if (n < t) return t; return null; }
function workerCps(w) { const n = owned(w.id); return n * w.cps * milestoneMult(n); }

function tapBuffMult() { return Date.now() < S.buffs.tapUntil ? S.buffs.tapMult : 1; }
function cpsBuffMult() { return Date.now() < S.buffs.cpsUntil ? S.buffs.cpsMult : 1; }

function totalCps() {
  let c = 0; for (const w of WORKERS) c += workerCps(w);
  return c * S.multiplier * S.prestigeMult * cpsBuffMult();
}
function comboMult() { return 1 + Math.min(S.combo, BAL.COMBO_CAP) * BAL.COMBO_STEP; }
function tapValue() {
  const flat = S.clickPower * S.multiplier * S.prestigeMult;
  const fromCps = totalCps() * S.tapPercent;     // делает тап полезным всю игру
  return (flat + fromCps) * comboMult() * tapBuffMult();
}
function addCoins(v) { S.coins += v; S.totalCoins += v; }

/* ---------- достижения ---------- */
const ACHIEVEMENTS = [
  { id: 'first',     name: '🦫 Первый тап',        ok: () => S.clicks >= 1 },
  { id: 'c100',      name: '👋 100 тапов',          ok: () => S.clicks >= 100 },
  { id: 'c1000',     name: '💢 1000 тапов',         ok: () => S.clicks >= 1000 },
  { id: 'coins1k',   name: '💰 Первая тыща',        ok: () => S.totalCoins >= 1e3 },
  { id: 'coins1m',   name: '🪙 Лимон',              ok: () => S.totalCoins >= 1e6 },
  { id: 'coins1b',   name: '🤑 Миллиард',           ok: () => S.totalCoins >= 1e9 },
  { id: 'worker1',   name: '👋 Первый джун',        ok: () => owned('junior') >= 1 },
  { id: 'team10',    name: '🧑‍🤝‍🧑 Команда из 10',    ok: () => totalWorkers() >= 10 },
  { id: 'team100',   name: '🏢 100 на этаже',       ok: () => totalWorkers() >= 100 },
  { id: 'mile',      name: '✖️ Майлстоун ×2',       ok: () => WORKERS.some(w => owned(w.id) >= 10) },
  { id: 'event1',    name: '⚡ Пережил эвент',       ok: () => S.events >= 1 },
  { id: 'golden',    name: '🌟 Поймал золотую',     ok: () => S._goldenCaught },
  { id: 'combo50',   name: '🔥 Комбо 50',           ok: () => S.combo >= 50 },
  { id: 'prestige1', name: '🌌 Сжёг контору',       ok: () => S.prestige >= 1 },
  { id: 'zen',       name: '🧘 Капибара-дзен (1Т)', ok: () => S.totalCoins >= 1e12 },
];
function totalWorkers() { let n = 0; for (const w of WORKERS) n += owned(w.id); return n; }

/* ---------- лог → бегущая строка ---------- */
const LOG = [];
const TICKER_STATIC = '★ ЭТАЖ 9000 НА СВЯЗИ ★ ТАПАЙ КАПИБАРУ ★ ЛОВИ ЗОЛОТУЮ 🦫✨ ★';
function log(msg) {
  LOG.push(msg); while (LOG.length > 6) LOG.shift();
  const t = $('#ticker'); if (!t) return;
  const text = (LOG.join('  ★  ') + '  ★  ' + TICKER_STATIC);
  t.innerHTML = `<span>${escapeHtml(text)}</span>`;
}
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c])); }

/* ---------- речь капибары ---------- */
const SPEECH = ['агрх','мур','я тут работаю','+1 респект','где доширак?','тимлид опять орёт',
  'не больно','хи-хи','ставь лайк','я в тренде','я капибара','воды бы','кофе закончился 😭',
  'это фича а не баг','надо обновить зависимости','прод в порядке','ёмаё'];
const MOTIVATIONAL = ['давай-давай!','не сдавайся!','ну ты и мужик!','ТЫ ЛЕГЕНДА','жми-жми!',
  'аплодирую лапкой','я в тебя верю','красавчик','ИДЁТ КРАСАВА','мощно!','эпично!','я горжусь тобой','ты — машина'];
let speechT = null;
function speak(t) {
  const el = $('#speech'); if (!el) return;
  el.textContent = t || pick(SPEECH); el.classList.add('show');
  clearTimeout(speechT); speechT = setTimeout(() => el.classList.remove('show'), 1700);
}
let lastMotiv = 0;
function maybeMotivate() {
  const now = Date.now();
  if (S.clicks > 0 && S.clicks % 30 === 0 && now - lastMotiv > 4000) { speak(pick(MOTIVATIONAL)); lastMotiv = now; }
}

/* ---------- звук + вибро ---------- */
let actx = null;
function ac() { if (S.muted) return null; if (!actx) { try { actx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { actx = null; } } return actx; }
function beep({ f = 440, t = 0.06, type = 'square', vol = 0.08, slide = 0 } = {}) {
  const ctx = ac(); if (!ctx) return;
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type; o.frequency.setValueAtTime(f, ctx.currentTime);
  if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(40, f + slide), ctx.currentTime + t);
  g.gain.setValueAtTime(vol, ctx.currentTime);
  g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t);
  o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + t + 0.02);
}
let lastSfx = 0;
function sfxClick() { const n = Date.now(); if (n - lastSfx < 30) return; lastSfx = n; beep({ f: 380 + rand(-30, 60), t: 0.05, vol: 0.06, slide: 200 }); }
function sfxCoin() { beep({ f: 880, t: 0.08, type: 'triangle', vol: 0.07 }); setTimeout(() => beep({ f: 1320, t: 0.1, type: 'triangle', vol: 0.07 }), 60); }
function sfxBuy() { beep({ f: 600, t: 0.06, type: 'sawtooth', vol: 0.08 }); setTimeout(() => beep({ f: 900, t: 0.08, type: 'sawtooth', vol: 0.08 }), 70); }
function sfxAch() { [800, 1100, 1400, 1700].forEach((f, i) => setTimeout(() => beep({ f, t: 0.1, type: 'triangle', vol: 0.08 }), i * 80)); }
function sfxAlarm() { for (let i = 0; i < 4; i++) setTimeout(() => beep({ f: 300, t: 0.16, vol: 0.1, slide: 600 }), i * 200); }
function sfxPrestige() { [220, 330, 440, 660, 880, 1320].forEach((f, i) => setTimeout(() => beep({ f, t: 0.18, type: 'triangle', vol: 0.09 }), i * 110)); }
function haptic(ms) { if (S.haptics && navigator.vibrate) { try { navigator.vibrate(ms); } catch (e) {} } }

/* ============================================================
   ТАП
   ============================================================ */
let capyBtn, floats, comboBox, comboDecayT = null;
const clickTimes = [];
function recordClick(now) { clickTimes.push(now); while (clickTimes.length && now - clickTimes[0] > 1000) clickTimes.shift(); }

function doClick(x, y) {
  const now = Date.now();
  recordClick(now);
  S.clicks++; S.combo++; resetComboDecay();

  const crit = Math.random() < Math.min(BAL.CRIT_CAP, BAL.CRIT_BASE + Math.min(S.combo, BAL.COMBO_CAP) * BAL.CRIT_PER_COMBO);
  const value = tapValue() * (crit ? BAL.CRIT_MULT : 1);
  addCoins(value);

  spawnFloat(x, y, value, crit);
  sfxClick(); haptic(8);

  if (Math.random() < 0.04) speak();
  maybeMotivate();

  capySvg.classList.remove('pulse'); void capySvg.offsetWidth; capySvg.classList.add('pulse');
  if (!S.lockedSkin && S.clicks % 7 === 0) randomizeSkin();
  if (S.combo > 0 && S.combo % 25 === 0 && S.motion) { capySvg.classList.add('disco'); setTimeout(() => capySvg.classList.remove('disco'), 600); }

  fastUpdate();
}
function resetComboDecay() {
  if (comboDecayT) clearTimeout(comboDecayT);
  comboDecayT = setTimeout(() => { S.combo = 0; comboBox.classList.remove('on'); }, BAL.COMBO_DECAY);
}

const FLOAT_MAX = 28;
function spawnFloat(cx, cy, value, crit) {
  while (floats.childElementCount >= FLOAT_MAX) floats.firstElementChild.remove();
  const r = floats.getBoundingClientRect();
  const el = document.createElement('div');
  el.className = 'float' + (crit ? ' crit' : '');
  el.style.left = (cx - r.left + rand(-18, 18)) + 'px';
  el.style.top = (cy - r.top + rand(-8, 8)) + 'px';
  el.textContent = (crit ? 'КРИТ! +' : '+') + fmt(value);
  floats.appendChild(el);
  setTimeout(() => el.remove(), 1000);
}

/* ============================================================
   МАГАЗИН
   ============================================================ */
let shopList, curTab = 'workers';
function renderShop() {
  if (!shopList) return;
  shopList.innerHTML = '';
  if (curTab === 'workers') {
    for (const w of WORKERS) {
      const n = owned(w.id), cost = workerCost(w), can = S.coins >= cost;
      const nm = nextMilestone(n);
      const each = w.cps * milestoneMult(n) * S.multiplier * S.prestigeMult;
      const item = el('div', 'item' + (can ? '' : ' cant'));
      item.innerHTML = `
        <div class="item__icon">${w.icon}</div>
        <div class="item__body">
          <div class="item__name">${w.name} <b>×${n}</b></div>
          <div class="item__desc">${w.desc}</div>
          <div class="item__milestone">даёт ${fmt(each)} КК/сек за штуку${nm ? ` · до ×2: ${n}/${nm}` : ' · МАКС ×2 ✓'}</div>
        </div>
        <div class="item__price">${fmt(cost)}</div>`;
      item.onclick = () => buyWorker(w);
      shopList.appendChild(item);
    }
  } else if (curTab === 'clicks') {
    for (const u of CLICK_UPGRADES) {
      const has = !!S.upgrades[u.id], can = !has && S.coins >= u.cost;
      const item = el('div', 'item' + (has ? ' owned' : can ? '' : ' cant'));
      item.innerHTML = `
        <div class="item__icon">${u.icon}</div>
        <div class="item__body">
          <div class="item__name">${u.name}</div>
          <div class="item__desc">${u.desc}</div>
        </div>
        <div class="item__price">${has ? '✓' : fmt(u.cost)}</div>`;
      if (!has) item.onclick = () => buyClick(u);
      shopList.appendChild(item);
    }
  } else {
    for (const u of ULTRA_UPGRADES) {
      const has = !!S.upgrades[u.id], can = !has && S.coins >= u.cost;
      const item = el('div', 'item' + (has ? ' owned' : can ? '' : ' cant'));
      item.innerHTML = `
        <div class="item__icon">${u.icon}</div>
        <div class="item__body">
          <div class="item__name">${u.name} ${has ? '<b>АКТИВНО</b>' : ''}</div>
          <div class="item__desc">${u.desc}</div>
        </div>
        <div class="item__price">${has ? '✓' : fmt(u.cost)}</div>`;
      if (!has) item.onclick = () => buyUltra(u);
      shopList.appendChild(item);
    }
  }
}
function el(tag, cls) { const e = document.createElement(tag); e.className = cls; return e; }

function buyWorker(w) {
  const cost = workerCost(w);
  if (S.coins < cost) { speak('денег нет, держись'); return; }
  S.coins -= cost; S.workers[w.id] = owned(w.id) + 1;
  sfxBuy(); haptic(15); speak(`+${w.name.split(' ')[0]}!`);
  log(`нанят ${w.name} ×${owned(w.id)}`);
  renderShop(); updateUI();
}
function buyClick(u) {
  if (S.upgrades[u.id] || S.coins < u.cost) { if (!S.upgrades[u.id]) speak('копи дальше'); return; }
  S.coins -= u.cost; S.upgrades[u.id] = true;
  if (u.flat) S.clickPower += u.flat;
  if (u.pct) S.tapPercent += u.pct;
  sfxBuy(); haptic(15); speak(u.name + '!'); log(`куплено: ${u.name}`);
  renderShop(); updateUI();
}
function buyUltra(u) {
  if (S.upgrades[u.id] || S.coins < u.cost) { if (!S.upgrades[u.id]) speak('куда без денег'); return; }
  S.coins -= u.cost; S.upgrades[u.id] = true; S.multiplier *= u.mult;
  sfxAch(); haptic(25); speak('КРИНЖ ×' + u.mult + '!'); log(`MEGA: ${u.name}`); flashPsy();
  renderShop(); updateUI();
}

/* ============================================================
   UI
   ============================================================ */
let _c = {};
function cacheEls() {
  _c.coins = $('#stat-coins'); _c.cps = $('#stat-cps'); _c.prestige = $('#stat-prestige');
  _c.comboVal = $('#combo-val'); _c.comboFill = $('#combo-fill'); _c.buffs = $('#buffs');
}
function fastUpdate() {
  if (!_c.coins) cacheEls();
  _c.coins.textContent = fmt(S.coins);
  _c.cps.textContent = fmt(totalCps());
  if (S.combo > 0) {
    comboBox.classList.add('on');
    _c.comboVal.textContent = '×' + comboMult().toFixed(2);
    _c.comboFill.style.width = clamp(S.combo / BAL.COMBO_CAP, 0, 1) * 100 + '%';
  }
  renderBuffs();
}
function renderBuffs() {
  const now = Date.now(); let html = '';
  if (now < S.buffs.tapUntil) html += `<span class="buff">👋×${S.buffs.tapMult} ${Math.ceil((S.buffs.tapUntil - now) / 1000)}с</span>`;
  if (now < S.buffs.cpsUntil) html += `<span class="buff">🚀×${S.buffs.cpsMult} ${Math.ceil((S.buffs.cpsUntil - now) / 1000)}с</span>`;
  if (_c.buffs.innerHTML !== html) _c.buffs.innerHTML = html;
}
let _lastHeavy = 0;
function updateUI() {
  fastUpdate();
  $('#stat-prestige').textContent = S.prestige;
  // престиж-кнопка
  const gain = prestigeGain();
  const btn = $('#prestige-btn'), hint = $('#prestige-hint');
  if (S.totalCoins >= BAL.PRESTIGE_UNLOCK && gain >= 1) {
    btn.classList.remove('hidden');
    btn.textContent = `🌌 ПРЕСТИЖ +${gain} ✦`;
    hint.textContent = `множитель станет ×${(1 + BAL.PRESTIGE_PER_POINT * (S.prestigePoints + gain)).toFixed(2)}`;
  } else {
    btn.classList.add('hidden');
    hint.textContent = S.totalCoins < BAL.PRESTIGE_UNLOCK
      ? `престиж с ${fmt(BAL.PRESTIGE_UNLOCK)} КК (у тебя ${fmt(S.totalCoins)})` : '';
  }
  const now = Date.now();
  if (drawerOpen && now - _lastHeavy > 500) { _lastHeavy = now; renderDrawerStats(); }
}
function renderDrawerStats() {
  const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
  set('#stat-clicks', fmt(S.clicks)); set('#stat-events', S.events);
  set('#stat-standups', S.standups); set('#stat-total', fmt(S.totalCoins));
  set('#rec-cur', fmt(S.totalCoins));
  set('#rec-best', fmt(Math.max(+localStorage.getItem(BEST_KEY) || 0, S.totalCoins)));
  // достижения
  const ul = $('#ach-list'); if (ul) {
    let unlocked = 0; ul.innerHTML = '';
    for (const a of ACHIEVEMENTS) {
      const has = !!S.achievements[a.id]; if (has) unlocked++;
      const li = document.createElement('li'); li.className = 'ach' + (has ? '' : ' locked');
      li.textContent = has ? a.name : '🔒 ???'; ul.appendChild(li);
    }
    const cnt = $('#ach-count'); if (cnt) cnt.textContent = `${unlocked}/${ACHIEVEMENTS.length}`;
  }
}
function checkAchievements() {
  for (const a of ACHIEVEMENTS) {
    if (!S.achievements[a.id] && a.ok()) {
      S.achievements[a.id] = true; log(`🏆 ${a.name}`); sfxAch(); haptic([10, 40, 10]); flashPsy(); toast('🏆 ' + a.name);
    }
  }
}
function flashPsy() { if (!S.motion) return; const p = $('#psy'); p.classList.add('on'); setTimeout(() => p.classList.remove('on'), 1200); }

let toastT = null;
function toast(msg) {
  let t = $('#toast'); if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show'); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 2600);
}

/* ============================================================
   ПРЕСТИЖ
   ============================================================ */
function prestigeTarget() { return Math.floor(Math.sqrt(S.totalCoins / 1e6)); }
function prestigeGain() { return Math.max(0, prestigeTarget() - S.prestigePoints); }
function doPrestige() {
  const gain = prestigeGain(); if (gain < 1) return;
  if (!confirm(`Сжечь контору и обнулить прогресс?\nПолучишь +${gain} кринж-очков → множитель ×${(1 + BAL.PRESTIGE_PER_POINT * (S.prestigePoints + gain)).toFixed(2)} навсегда.`)) return;
  const keep = {
    achievements: S.achievements, muted: S.muted, haptics: S.haptics, motion: S.motion,
    skin: S.skin, savedSkins: S.savedSkins, lockedSkin: S.lockedSkin, standups: S.standups,
    prestige: S.prestige + 1, prestigePoints: S.prestigePoints + gain,
  };
  S = DEFAULT_STATE();
  Object.assign(S, keep);
  S.prestigeMult = 1 + BAL.PRESTIGE_PER_POINT * S.prestigePoints;
  sfxPrestige(); haptic([20, 60, 20]); flashPsy();
  log(`🌌 ПРЕСТИЖ! множитель ×${S.prestigeMult.toFixed(2)}`); toast(`🌌 Контора сожжена! ×${S.prestigeMult.toFixed(2)}`);
  saveState(); renderShop(); updateUI();
}

/* ============================================================
   ЗОЛОТАЯ КАПИБАРА (вместо чит-гэга)
   ============================================================ */
let goldenLayer;
function goldenLoop() {
  setTimeout(() => {
    spawnGolden(); goldenLoop();
  }, randInt(BAL.GOLDEN_MIN * 1000, BAL.GOLDEN_MAX * 1000));
}
function spawnGolden() {
  if (eventState.active || document.hidden || S.totalCoins < 200) return;
  const dur = rand(5.5, 7.5);
  const g = document.createElement('div'); g.className = 'golden'; g.textContent = '🦫';
  g.style.animationDuration = dur + 's';
  const grab = () => { if (g._done) return; g._done = true; goldenReward(); g.style.pointerEvents = 'none'; g.style.transition = 'transform .2s, opacity .2s'; g.style.transform = 'scale(1.6)'; g.style.opacity = '0'; setTimeout(() => g.remove(), 250); };
  g.addEventListener('pointerdown', (e) => { e.stopPropagation(); e.preventDefault(); grab(); });
  goldenLayer.appendChild(g);
  log('🦫✨ золотая капибара пролетает!'); speak('лови меня!');
  setTimeout(() => { if (!g._done) g.remove(); }, dur * 1000 + 60);
}
function goldenReward() {
  S._goldenCaught = true;
  const roll = Math.random(); let msg;
  if (roll < 0.45) { const c = Math.max(80, totalCps() * rand(60, 140)); addCoins(c); msg = '💰 +' + fmt(c) + ' КК'; }
  else if (roll < 0.72) { S.buffs.tapMult = 7; S.buffs.tapUntil = Date.now() + 15000; msg = '👋 ТАП ×7 на 15с!'; }
  else if (roll < 0.95) { S.buffs.cpsMult = 7; S.buffs.cpsUntil = Date.now() + 15000; msg = '🚀 КК/сек ×7 на 15с!'; }
  else { S.buffs.cpsMult = 15; S.buffs.cpsUntil = Date.now() + 12000; msg = '🌈 МЕГА ×15!'; }
  sfxCoin(); haptic([10, 30, 10]); flashPsy(); toast('🌟 ' + msg); log('🌟 ' + msg);
  fastUpdate();
}

/* ============================================================
   ЭВЕНТЫ (мини-игры)
   ============================================================ */
const eventState = { active: false, type: null };
const EVENTS = ['bug', 'dj', 'standup', 'coffee', 'cringe', 'pocket'];
function eventLoop() {
  setTimeout(() => { maybeStartEvent(); eventLoop(); }, randInt(BAL.EVENT_MIN * 1000, BAL.EVENT_MAX * 1000));
}
function maybeStartEvent() { if (eventState.active || S.totalCoins < 50 || document.hidden) return; startEvent(pick(EVENTS)); }
function startEvent(type) {
  eventState.active = true; eventState.type = type; S.events++;
  const layer = $('#event'); layer.classList.remove('hidden');
  layer.innerHTML = '<div class="event__banner" id="event-banner"></div><div class="event__area" id="event-area"></div>';
  const banner = $('#event-banner'), area = $('#event-area');
  sfxAlarm(); haptic(30);
  ({ bug: startBug, dj: startDj, standup: startStandup, coffee: startCoffee, cringe: startCringe, pocket: startPocket }[type])(banner, area);
}
function endEvent(reward, label) {
  $('#event').classList.add('hidden');
  eventState.active = false; eventState.type = null;
  if (reward > 0) { addCoins(reward); sfxCoin(); haptic(20); speak(label || 'награда!'); log(`⚡ +${fmt(reward)} КК (${label})`); }
  else { speak('эх...'); log('⚡ эвент впустую'); }
  updateUI(); renderShop();
}

function startBug(banner, area) {
  banner.textContent = '🐞 ПРОД УПАЛ! ЛОВИ ЖУКОВ!';
  let caught = 0; const dur = 9000, start = Date.now();
  const spawn = () => {
    if (!eventState.active || Date.now() - start > dur) return;
    const b = el('div', 'bug'); b.textContent = pick(['🐞', '🪲', '🐛', '🦗', '🪳']);
    b.style.left = rand(2, 82) + '%'; b.style.top = rand(6, 80) + '%';
    b.addEventListener('pointerdown', (e) => { e.stopPropagation(); if (b.classList.contains('dead')) return; b.classList.add('dead'); caught++; sfxClick(); haptic(8); setTimeout(() => b.remove(), 300); });
    area.appendChild(b); setTimeout(() => b.remove(), 2200); setTimeout(spawn, rand(330, 640));
  };
  spawn();
  setTimeout(() => { if (eventState.active) endEvent(caught * Math.max(60, totalCps() * 4), `жуков: ${caught}`); }, dur);
}

function startDj(banner, area) {
  banner.textContent = '🎧 DJ-СЕССИЯ! A S D F или тапай клавиши';
  area.innerHTML = `<div class="dj"><div class="dj__score" id="dj-score">0</div><div class="dj__lanes" id="dj-lanes">
    ${['A', 'S', 'D', 'F'].map(k => `<div class="dj__lane"><div class="dj__hitline"></div><div class="dj__key">${k}</div></div>`).join('')}
  </div></div>`;
  capySvg.classList.add('disco');
  const lanes = $$('.dj__lane'), keys = $$('.dj__key'), scoreEl = $('#dj-score');
  let score = 0, combo = 0, notes = [];
  const FALL = 2600, dur = 12000, start = Date.now(), KEY_H = 60, WINDOW = 120;
  const spawn = () => {
    if (!eventState.active || eventState.type !== 'dj' || Date.now() - start > dur - 1800) return;
    const lane = randInt(0, 3), note = el('div', 'dj__note'); note.style.top = '0px';
    lanes[lane].appendChild(note); notes.push({ el: note, lane, t: Date.now() });
    beep({ f: 240 + lane * 90, t: 0.04, vol: 0.05 });
    setTimeout(spawn, rand(620, 1000));
  };
  spawn();
  const fall = () => {
    if (!eventState.active || eventState.type !== 'dj') return;
    const h = lanes[0].clientHeight;
    notes = notes.filter(n => {
      const p = (Date.now() - n.t) / FALL, y = p * (h - KEY_H);
      n.el.style.top = y + 'px';
      const close = y >= h - KEY_H - WINDOW && y <= h - KEY_H + 10;
      n.el.classList.toggle('good', close);
      if (p > 1.05) { n.el.remove(); combo = 0; return false; }
      return true;
    });
    requestAnimationFrame(fall);
  };
  requestAnimationFrame(fall);
  const hit = (lane) => {
    if (!eventState.active || eventState.type !== 'dj') return;
    keys[lane].classList.add('hit'); setTimeout(() => keys[lane].classList.remove('hit'), 100);
    const ln = notes.filter(n => n.lane === lane); if (!ln.length) return;
    ln.sort((a, b) => parseFloat(b.el.style.top) - parseFloat(a.el.style.top));
    const near = ln[0], y = parseFloat(near.el.style.top), h = lanes[0].clientHeight;
    if (y >= h - KEY_H - WINDOW && y <= h - KEY_H + 10) {
      near.el.remove(); notes = notes.filter(n => n !== near);
      score += 100 + combo * 25; combo++;
      scoreEl.textContent = score + (combo > 1 ? ` (×${combo})` : ''); beep({ f: 660 + lane * 80, t: 0.06, type: 'triangle', vol: 0.07 }); haptic(8);
    }
  };
  const onKey = (e) => { const i = ['a', 's', 'd', 'f'].indexOf(e.key.toLowerCase()); if (i >= 0) hit(i); };
  document.addEventListener('keydown', onKey);
  keys.forEach((k, i) => k.addEventListener('pointerdown', (e) => { e.stopPropagation(); e.preventDefault(); hit(i); }));
  setTimeout(() => {
    document.removeEventListener('keydown', onKey); capySvg.classList.remove('disco');
    if (eventState.active) endEvent(score * Math.max(1, totalCps() * 0.06), `DJ-сет: ${score}`);
  }, dur);
}

function startStandup(banner, area) {
  banner.textContent = '🏃 СТЕНДАП! ТАПАЙ ЧТОБ УБЕЖАТЬ!';
  area.innerHTML = `<div class="standup">
    <div class="su-meter"><div class="su-fill" id="su-fill"></div><div class="su-text" id="su-text">убегай!</div></div>
    <button class="su-capy" id="su-capy">🦫</button>
    <div class="event__sub">тапни 20 раз за 7 секунд!</div></div>`;
  S.standups++;
  let clicks = 0; const need = 20, dur = 7000, start = Date.now();
  const fill = $('#su-fill'), text = $('#su-text'), capy = $('#su-capy');
  const tick = () => {
    if (!eventState.active || eventState.type !== 'standup') return;
    const p = clicks / need; fill.style.width = clamp(p, 0, 1) * 100 + '%';
    text.textContent = `${clicks}/${need}` + (p >= 1 ? ' — УБЕЖАЛ!' : '');
    if (p >= 1) { endEvent(totalCps() * 30 + 600, 'отбился от стендапа!'); return; }
    if ((Date.now() - start) / dur >= 1) { endEvent(0, 'попал на стендап'); return; }
    requestAnimationFrame(tick);
  };
  tick();
  capy.addEventListener('pointerdown', (e) => { e.stopPropagation(); if (!eventState.active) return; clicks++; capy.style.transform = `translateX(${rand(-40, 40) | 0}px) scale(${1 + Math.random() * 0.1})`; sfxClick(); haptic(8); });
}

function startCoffee(banner, area) {
  banner.textContent = '☕ КОФЕ-БРЕЙК! ×2 КК/сек на 8 секунд';
  area.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:10px">
    <div class="event__big">☕</div><div class="event__sub">все капибары отдыхают</div></div>`;
  const old = S.multiplier; S.multiplier *= 2;
  setTimeout(() => { S.multiplier = old; if (eventState.active) endEvent(totalCps() * 12, 'кофе допит'); }, 8000);
}

function startCringe(banner, area) {
  banner.textContent = '🌈 КРИНЖ-ВОЛНА! ВЫБЕРИ КАПИБАРУ!';
  area.innerHTML = '';
  const wrap = el('div', 'pick');
  const choices = [{ m: 0.5, l: 'облом', i: '😭' }, { m: 1, l: 'пшик', i: '🤡' }, { m: 5, l: 'ОГОНЬ', i: '🔥' }, { m: 20, l: 'СКИБИДИ', i: '🌈' }];
  const shuf = [...choices].sort(() => Math.random() - 0.5);
  shuf.forEach((c) => {
    const b = el('button', 'pick__btn'); b.textContent = '🦫';
    b.addEventListener('pointerdown', (e) => { e.stopPropagation(); if (b._done) return; b._done = true; b.textContent = c.i; flashPsy(); setTimeout(() => endEvent(Math.max(80, totalCps() * 10) * c.m, c.l), 600); });
    wrap.appendChild(b);
  });
  area.appendChild(wrap);
  setTimeout(() => { if (eventState.active && eventState.type === 'cringe') endEvent(0, 'не успел'); }, 11000);
}

function startPocket(banner, area) {
  banner.textContent = '🪙 ЧТО В КАРМАНЕ? ВЫБЕРИ!';
  area.innerHTML = '';
  const wrap = el('div', 'pick');
  ['👖', '🧥', '🎒'].forEach((icon) => {
    const b = el('button', 'pick__btn'); b.textContent = icon;
    b.addEventListener('pointerdown', (e) => { e.stopPropagation(); if (b._done) return; b._done = true; b.textContent = '🪙'; const c = Math.max(100, totalCps() * rand(20, 80)); flashPsy(); setTimeout(() => endEvent(c, 'нашёл ' + fmt(c) + ' КК'), 450); });
    wrap.appendChild(b);
  });
  area.appendChild(wrap);
  setTimeout(() => { if (eventState.active && eventState.type === 'pocket') endEvent(0, 'карман пуст'); }, 9000);
}

/* ============================================================
   СПАРКЛЫ + ГЛАВНЫЙ ЦИКЛ
   ============================================================ */
let sparkleLayer; const SPARK = ['✨', '★', '💖', '💫', '🌈', '🦫', '💸', '☕', '🍜'];
function spawnSparkle() {
  if (!S.motion) return;
  const e = el('div', 'sparkle'); e.textContent = pick(SPARK);
  e.style.left = rand(0, 100) + '%'; e.style.fontSize = rand(14, 30) + 'px';
  e.style.animationDuration = rand(4, 9) + 's';
  sparkleLayer.appendChild(e); setTimeout(() => e.remove(), 9000);
}

let lastTick = Date.now();
function tick() {
  const now = Date.now(), dt = (now - lastTick) / 1000; lastTick = now;
  if (!eventState.active) { const g = totalCps() * dt; if (g > 0) addCoins(g); }
  checkAchievements(); updateUI();
  if (Math.random() < 0.05) spawnSparkle();
  requestAnimationFrame(tick);
}

/* ============================================================
   ШТОРКА НАСТРОЕК + СВАЙП
   ============================================================ */
let drawer, sheet, drawerOpen = false;
function openDrawer() { drawerOpen = true; drawer.classList.add('open'); drawer.setAttribute('aria-hidden', 'false'); sheet.style.transform = ''; renderDrawerStats(); updateSkinPanel(); }
function closeDrawer() { drawerOpen = false; drawer.classList.remove('open'); drawer.setAttribute('aria-hidden', 'true'); sheet.style.transform = ''; }

function setupDrawer() {
  drawer = $('#drawer'); sheet = $('#drawer-sheet');
  $('#grab').addEventListener('click', openDrawer);
  $('#drawer-close').addEventListener('click', closeDrawer);
  $('#drawer-backdrop').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && drawerOpen) closeDrawer(); });

  // --- свайп вниз = открыть, свайп вверх по шторке = закрыть ---
  let mode = null, startY = 0, dy = 0, h = 0;
  const isTyping = (t) => t && /input|textarea/i.test(t.tagName || '');
  const closestSafe = (t, sel) => (t && t.closest) ? t.closest(sel) : null;
  document.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if (!drawerOpen) {
      // открыть: жест начат в верхних 62% экрана, не на магазине/шторке/инпуте
      if (closestSafe(e.target, '.shop') || closestSafe(e.target, '.drawer') || isTyping(e.target)) return;
      if (e.clientY > window.innerHeight * 0.62) return;
      mode = 'open'; startY = e.clientY; dy = 0; h = Math.min(window.innerHeight * 0.9, sheet.offsetHeight || window.innerHeight * 0.8);
    } else {
      // закрыть: тянем шторку вверх (за хват или в верхней её части)
      if (!closestSafe(e.target, '.drawer__sheet')) return;
      const r = sheet.getBoundingClientRect();
      if (e.clientY > r.top + 120) return; // тянуть можно только за верх шторки
      mode = 'close'; startY = e.clientY; dy = 0; h = sheet.offsetHeight;
    }
  }, { passive: true });

  document.addEventListener('pointermove', (e) => {
    if (!mode) return;
    dy = e.clientY - startY;
    if (mode === 'open') {
      if (dy <= 6) return;
      drawer.classList.add('open', 'dragging');
      sheet.style.transform = `translateY(${Math.min(0, -h + dy)}px)`;
      e.preventDefault();
    } else {
      if (dy >= -6) return;
      drawer.classList.add('dragging');
      sheet.style.transform = `translateY(${Math.max(-h, dy)}px)`;
      e.preventDefault();
    }
  }, { passive: false });

  const finish = () => {
    if (!mode) return;
    drawer.classList.remove('dragging');
    if (mode === 'open') { if (dy > 70) openDrawer(); else closeDrawer(); }
    else { if (dy < -70) closeDrawer(); else openDrawer(); }
    mode = null; dy = 0;
  };
  document.addEventListener('pointerup', finish);
  document.addEventListener('pointercancel', finish);
}

/* ============================================================
   НАСТРОЙКИ (тумблеры)
   ============================================================ */
function applyMotion() { document.body.classList.toggle('no-motion', !S.motion); }
function setupSettings() {
  const sound = $('#set-sound'), hap = $('#set-haptics'), mot = $('#set-motion');
  const sync = () => {
    sound.setAttribute('aria-pressed', String(!S.muted));
    hap.setAttribute('aria-pressed', String(S.haptics));
    mot.setAttribute('aria-pressed', String(S.motion));
  };
  sound.onclick = () => { S.muted = !S.muted; if (!S.muted) sfxCoin(); sync(); saveState(); };
  hap.onclick = () => { S.haptics = !S.haptics; if (S.haptics) haptic(20); sync(); saveState(); };
  mot.onclick = () => { S.motion = !S.motion; applyMotion(); sync(); saveState(); };
  sync(); applyMotion();
}

/* ---------- имя / рекорд ---------- */
function getName() { let n = localStorage.getItem(NAME_KEY); if (!n) { n = 'Капыч-' + Math.random().toString(36).slice(2, 6).toUpperCase(); localStorage.setItem(NAME_KEY, n); } return n; }
function setupRecord() {
  const inp = $('#lb-name'); inp.value = getName();
  $('#lb-save').onclick = () => { const v = inp.value.trim(); if (v.length >= 2) { localStorage.setItem(NAME_KEY, v.slice(0, 20)); toast('ник сохранён: ' + v.slice(0, 20)); } };
}

/* ---------- оффлайн-доход ---------- */
function offlineGain() {
  const dt = (Date.now() - (S.lastSeen || Date.now())) / 1000;
  if (dt > 30) {
    const g = totalCps() * Math.min(dt, BAL.OFFLINE_MAX_H * 3600) * BAL.OFFLINE_RATE;
    if (g > 1) { addCoins(g); setTimeout(() => toast(`📦 Пока тебя не было: +${fmt(g)} КК`), 800); log(`📦 оффлайн +${fmt(g)} КК`); }
  }
}

/* ---------- konami (десктоп-пасхалка) ---------- */
const konami = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
let ki = 0;
function setupKonami() {
  document.addEventListener('keydown', (e) => {
    if (e.key === konami[ki]) { if (++ki === konami.length) { ki = 0; addCoins(1e6); flashPsy(); sfxPrestige(); toast('★ KONAMI: +1М КК ★'); updateUI(); } }
    else ki = (e.key === konami[0]) ? 1 : 0;
  });
}

/* ============================================================
   СТАРТ
   ============================================================ */
function init() {
  capyBtn = $('#capy-btn'); capySvg = $('#capy-svg'); floats = $('#floats');
  comboBox = $('#combo'); goldenLayer = $('#golden-layer'); sparkleLayer = $('#sparkles'); shopList = $('#shop-list');

  renderCapybara();

  // тап по капибаре
  capyBtn.addEventListener('pointerdown', (e) => { e.preventDefault(); if (eventState.active) return; doClick(e.clientX, e.clientY); });
  capyBtn.addEventListener('contextmenu', (e) => e.preventDefault());
  capyBtn.addEventListener('dblclick', (e) => e.preventDefault());
  $('#play').addEventListener('gesturestart', (e) => e.preventDefault());
  // пробел = тап (десктоп)
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && !eventState.active && !drawerOpen && !/input|textarea/i.test((e.target.tagName || ''))) {
      e.preventDefault(); const r = capyBtn.getBoundingClientRect(); doClick(r.left + r.width / 2, r.top + r.height / 2);
    }
  });

  // табы магазина
  $$('.tab').forEach(t => t.addEventListener('click', () => {
    $$('.tab').forEach(x => x.classList.remove('tab--active')); t.classList.add('tab--active');
    curTab = t.dataset.tab; renderShop();
  }));
  $('#prestige-btn').addEventListener('click', doPrestige);

  // скины
  $('#skin-save').onclick = saveCurrentSkin;
  $('#skin-next').onclick = () => { S.lockedSkin = false; randomizeSkin(); };
  $('#skin-auto').onclick = unlockSkin;

  // сброс
  $('#btn-reset').onclick = () => { if (confirm('Точно сбросить весь прогресс? Это навсегда.')) { localStorage.removeItem(SAVE_KEY); location.reload(); } };

  $('#version').textContent = `v${VERSION} «${VERSION_NAME}»`;

  setupDrawer(); setupSettings(); setupRecord(); setupKonami();
  offlineGain();
  renderShop(); updateUI(); updateSkinPanel(); renderDrawerStats();
  log(`★ v${VERSION} «${VERSION_NAME}» загружен`); speak('привет! свайпни вниз — там настройки');
  for (let i = 0; i < 5; i++) spawnSparkle();

  setInterval(saveState, 4000);
  goldenLoop(); eventLoop(); requestAnimationFrame(tick);

  // QA / читы из URL
  const m = location.hash.match(/event=(\w+)/); if (m) setTimeout(() => startEvent(m[1]), 600);
  if (location.search.includes('cheat=1')) { addCoins(1e9); log('🤡 ?cheat=1 → +1Б КК'); updateUI(); }
}

window.addEventListener('beforeunload', saveState);
document.addEventListener('visibilitychange', () => { if (document.hidden) saveState(); });
init();
