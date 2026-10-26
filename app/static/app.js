// Chess in the Hand of AI – browser side.
// The page keeps the list of moves; the Python server checks rules and runs the AI.

const S = {
  moves: [], legal: [], fen: "", turn: "w", last: null, check: false, king: null,
  over: false, status: "", san: [],
  player: "w", level: 3, time: 2, flipped: false, busy: false, selected: null,
  levels: [],
};
let requestId = 0;  // ignore AI answers that arrive after "New game" / "Undo"

const $ = (id) => document.getElementById(id);
const FILES = "abcdefgh";

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function applyState(st) {
  Object.assign(S, {
    fen: st.fen, legal: st.legal, turn: st.turn, last: st.last, check: st.check,
    king: st.king, over: st.game_over, status: st.status, san: st.san,
  });
}

// ---------------------------------------------------------------- board ----
function pieceAt(fen) {
  const map = {};
  const rows = fen.split(" ")[0].split("/");
  rows.forEach((row, i) => {
    let f = 0;
    for (const ch of row) {
      if (/\d/.test(ch)) f += +ch;
      else { map[FILES[f] + (8 - i)] = ch; f++; }
    }
  });
  return map;
}

function renderBoard() {
  const board = $("board");
  board.innerHTML = "";
  const pieces = pieceAt(S.fen);
  const targets = new Map();
  if (S.selected) {
    for (const m of S.legal) if (m.startsWith(S.selected)) targets.set(m.slice(2, 4), true);
  }
  const ranks = S.flipped ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
  const files = S.flipped ? [...FILES].reverse() : [...FILES];
  ranks.forEach((r, ri) => {
    files.forEach((f, fi) => {
      const sq = f + r;
      const el = document.createElement("div");
      const light = (FILES.indexOf(f) + r) % 2 === 1;
      el.className = "sq " + (light ? "l" : "d");
      el.dataset.sq = sq;
      if (S.last && (S.last.slice(0, 2) === sq || S.last.slice(2, 4) === sq)) el.classList.add("last");
      if (S.selected === sq) el.classList.add("sel");
      if (S.check && S.king === sq) el.classList.add("check");
      if (targets.has(sq)) { el.classList.add("target"); if (pieces[sq]) el.classList.add("cap"); }
      if (pieces[sq]) {
        const img = document.createElement("img");
        img.src = `/piece/${pieces[sq]}.svg`;
        img.alt = pieces[sq];
        el.appendChild(img);
      }
      if (ri === 7) el.insertAdjacentHTML("beforeend", `<span class="coord f">${f}</span>`);
      if (fi === 0) el.insertAdjacentHTML("beforeend", `<span class="coord r">${r}</span>`);
      el.addEventListener("click", () => onSquare(sq));
      board.appendChild(el);
    });
  });
}

function renderMoves() {
  const ol = $("moves");
  ol.innerHTML = "";
  for (let i = 0; i < S.san.length; i += 2) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${S.san[i]}</span><span>${S.san[i + 1] || ""}</span>`;
    ol.appendChild(li);
  }
  ol.scrollTop = ol.scrollHeight;
}

function renderStatus() {
  const st = $("status");
  st.classList.toggle("thinking", S.busy);
  if (S.over) st.textContent = S.status;
  else if (S.busy) st.textContent = "AI is thinking";
  else if (S.turn === S.player) st.textContent = S.check ? "Check! Your move" : "Your move";
  else st.textContent = "AI to move";
  $("undo").disabled = S.busy || S.moves.length === 0;
}

function render() { renderBoard(); renderMoves(); renderStatus(); }

function renderLevels() {
  const box = $("levels");
  box.innerHTML = "";
  for (const lv of S.levels) {
    const b = document.createElement("button");
    b.innerHTML = `${lv.level}<small>${lv.name}</small>`;
    b.className = lv.level === S.level ? "on" : "";
    b.addEventListener("click", () => { S.level = lv.level; renderLevels(); });
    box.appendChild(b);
  }
  const cur = S.levels.find((l) => l.level === S.level);
  if (cur) {
    const how = cur.time_limit ? `deepens until time runs out` : `fixed depth ${cur.depth} ply`;
    $("levelInfo").textContent = `${cur.label} · ${how} · evaluation: ${cur.evaluation}`;
  }
}

function showStats(s) {
  $("sMove").textContent = s.san;
  $("sScore").textContent = s.score_text + " (AI side)";
  $("sDepth").textContent = s.seldepth > s.depth ? `${s.depth} ply (selective ${s.seldepth})` : `${s.depth} ply`;
  $("sNodes").textContent = s.nodes.toLocaleString();
  $("sTime").textContent = s.time.toFixed(2) + " s";
  $("sNps").textContent = s.nps.toLocaleString() + " pos/s";
  $("sPv").textContent = s.pv.length > 1 ? "Expected line: " + s.pv.join(" ") : "";
  // Evaluation bar (White's point of view), squashed into 0..100 %
  const w = s.white_score;
  const pct = Math.abs(w) > 90000 ? (w > 0 ? 100 : 0) : 50 + 50 * Math.tanh(w / 600);
  $("evalFill").style.height = pct + "%";
  $("evalText").textContent = Math.abs(w) > 90000 ? "M" : (w / 100).toFixed(1);
}

// ---------------------------------------------------------------- moves ----
function onSquare(sq) {
  if (S.busy || S.over || S.turn !== S.player) return;
  const pieces = pieceAt(S.fen);
  if (S.selected) {
    const cands = S.legal.filter((m) => m.startsWith(S.selected + sq));
    if (cands.length === 1) return play(cands[0]);
    if (cands.length > 1) return askPromotion(cands);
  }
  const p = pieces[sq];
  const mine = p && ((p === p.toUpperCase()) === (S.player === "w"));
  S.selected = mine && S.selected !== sq ? sq : null;
  renderBoard();
}

function askPromotion(cands) {
  const box = $("promo");
  box.innerHTML = "";
  for (const t of ["q", "r", "b", "n"]) {
    const uci = cands.find((m) => m.endsWith(t));
    if (!uci) continue;
    const b = document.createElement("button");
    const sym = S.player === "w" ? t.toUpperCase() : t;
    b.innerHTML = `<img src="/piece/${sym}.svg" alt="${t}">`;
    b.addEventListener("click", () => { box.classList.add("hidden"); play(uci); });
    box.appendChild(b);
  }
  box.classList.remove("hidden");
}

async function play(uci) {
  S.selected = null;
  S.moves.push(uci);
  applyState(await api("/api/state", { moves: S.moves }));
  render();
  if (!S.over) aiMove();
}

async function aiMove() {
  const id = ++requestId;
  S.busy = true;
  renderStatus();
  try {
    const r = await api("/api/ai", { moves: S.moves, level: S.level, time: S.time });
    if (id !== requestId) return;          // the game changed meanwhile
    if (r.move) { S.moves.push(r.move); showStats(r.stats); }
    applyState(r.state);
  } catch (e) {
    console.error(e);
    $("status").textContent = "Error: " + e.message;
  } finally {
    if (id === requestId) { S.busy = false; render(); }
  }
}

async function newGame() {
  requestId++;
  S.busy = false;
  S.moves = [];
  S.selected = null;
  S.player = $("color").value;
  S.flipped = S.player === "b";
  $("promo").classList.add("hidden");
  for (const id of ["sMove", "sScore", "sDepth", "sNodes", "sTime", "sNps"]) $(id).textContent = "–";
  $("sPv").textContent = "";
  $("evalFill").style.height = "50%";
  $("evalText").textContent = "0.0";
  applyState(await api("/api/state", { moves: [] }));
  render();
  if (S.player !== S.turn) aiMove();
}

async function undo() {
  if (S.busy || !S.moves.length) return;
  S.moves.pop();
  // Go back to a position where it is the human's turn
  const myTurnAfter = (n) => (n % 2 === 0 ? "w" : "b") === S.player;
  if (!myTurnAfter(S.moves.length) && S.moves.length) S.moves.pop();
  S.selected = null;
  applyState(await api("/api/state", { moves: S.moves }));
  render();
  if (S.turn !== S.player && !S.over) aiMove();
}

// ---------------------------------------------------------------- setup ----
async function init() {
  S.levels = await api("/api/levels");
  renderLevels();
  $("time").addEventListener("input", (e) => {
    S.time = +e.target.value;
    $("timeVal").textContent = S.time.toFixed(1) + " s";
  });
  $("newGame").addEventListener("click", newGame);
  $("undo").addEventListener("click", undo);
  $("flip").addEventListener("click", () => { S.flipped = !S.flipped; renderBoard(); });
  await newGame();
}

init();
