// Chess in the Hand of AI – browser side (mid-project: two human players).
// The page keeps the list of moves; the Python server checks the rules.

const S = {
  moves: [], legal: [], fen: "", turn: "w", last: null, check: false, king: null,
  over: false, status: "", san: [],
  flipped: false, selected: null,
  hints: true, coords: true, autoFlip: false,
};

const $ = (id) => document.getElementById(id);
const FILES = "abcdefgh";

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function refresh() {
  const st = await api("/api/state", { moves: S.moves });
  Object.assign(S, {
    fen: st.fen, legal: st.legal, turn: st.turn, last: st.last, check: st.check,
    king: st.king, over: st.game_over, status: st.status, san: st.san,
  });
  if (S.autoFlip) S.flipped = S.turn === "b";
  render();
}

// ---------------------------------------------------------------- board ----
function pieceAt(fen) {
  const map = {};
  fen.split(" ")[0].split("/").forEach((row, i) => {
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
  const targets = new Set();
  if (S.selected && S.hints) {
    for (const m of S.legal) if (m.startsWith(S.selected)) targets.add(m.slice(2, 4));
  }
  const ranks = S.flipped ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
  const files = S.flipped ? [...FILES].reverse() : [...FILES];
  ranks.forEach((r, ri) => {
    files.forEach((f, fi) => {
      const sq = f + r;
      const el = document.createElement("div");
      el.className = "sq " + ((FILES.indexOf(f) + r) % 2 === 1 ? "l" : "d");
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
      if (S.coords && ri === 7) el.insertAdjacentHTML("beforeend", `<span class="coord f">${f}</span>`);
      if (S.coords && fi === 0) el.insertAdjacentHTML("beforeend", `<span class="coord r">${r}</span>`);
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
  const side = S.turn === "w" ? "White" : "Black";
  $("status").textContent = S.over ? S.status : S.check ? `Check! ${side} to move` : `${side} to move`;
  $("undo").disabled = S.moves.length === 0;
}

function render() { renderBoard(); renderMoves(); renderStatus(); }

// ---------------------------------------------------------------- moves ----
function onSquare(sq) {
  if (S.over) return;
  if (S.selected) {
    const cands = S.legal.filter((m) => m.startsWith(S.selected + sq));
    if (cands.length === 1) return play(cands[0]);
    if (cands.length > 1) return askPromotion(cands);
  }
  // Select a piece of the side to move (click again to unselect)
  const p = pieceAt(S.fen)[sq];
  const own = p && ((p === p.toUpperCase()) === (S.turn === "w"));
  S.selected = own && S.selected !== sq ? sq : null;
  renderBoard();
}

function askPromotion(cands) {
  const box = $("promo");
  box.innerHTML = "";
  for (const t of ["q", "r", "b", "n"]) {
    const uci = cands.find((m) => m.endsWith(t));
    if (!uci) continue;
    const b = document.createElement("button");
    const sym = S.turn === "w" ? t.toUpperCase() : t;
    b.innerHTML = `<img src="/piece/${sym}.svg" alt="${t}">`;
    b.addEventListener("click", () => { box.classList.add("hidden"); play(uci); });
    box.appendChild(b);
  }
  box.classList.remove("hidden");
}

async function play(uci) {
  S.selected = null;
  S.moves.push(uci);
  await refresh();
}

async function newGame() {
  S.moves = [];
  S.selected = null;
  S.flipped = false;
  $("promo").classList.add("hidden");
  await refresh();
}

async function undo() {
  if (!S.moves.length) return;
  S.moves.pop();
  S.selected = null;
  $("promo").classList.add("hidden");
  await refresh();
}

// ---------------------------------------------------------------- setup ----
function init() {
  $("newGame").addEventListener("click", newGame);
  $("undo").addEventListener("click", undo);
  $("flip").addEventListener("click", () => { S.flipped = !S.flipped; renderBoard(); });
  $("showHints").addEventListener("change", (e) => { S.hints = e.target.checked; renderBoard(); });
  $("showCoords").addEventListener("change", (e) => { S.coords = e.target.checked; renderBoard(); });
  $("autoFlip").addEventListener("change", (e) => {
    S.autoFlip = e.target.checked;
    if (S.autoFlip) S.flipped = S.turn === "b";
    renderBoard();
  });
  newGame();
}

init();
