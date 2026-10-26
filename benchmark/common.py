"""Shared helpers for the benchmark scripts (Member 1 and Member 5).

Everything here runs without the graphical interface.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chess
import chess.engine
import chess.pgn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chessai import make_variant  # noqa: E402
from chessai.evaluation import evaluate_material  # noqa: E402

DATA = ROOT / "data"
RESULTS = ROOT / "results"


# --------------------------------------------------------------------- data --
def load_epd(path: Path = DATA / "wac50.epd") -> list[dict]:
    """Return [{'id', 'fen', 'bm': [Move], 'board'}] from an EPD file."""
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            board, ops = chess.Board.from_epd(line)
            items.append({"id": ops.get("id", f"pos{len(items) + 1}"), "fen": board.fen(),
                          "bm": ops.get("bm", []), "board": board})
    return items


def load_openings(path: Path = DATA / "openings.txt") -> list[dict]:
    """Return [{'name', 'moves': [SAN], 'fen'}] from the openings file."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, moves = (part.strip() for part in line.split("|"))
            board = chess.Board()
            ucis = []
            for san in moves.split():
                mv = board.parse_san(san)
                ucis.append(mv.uci())
                board.push(mv)
            out.append({"name": name, "moves": ucis, "fen": board.fen()})
    return out


def test_positions(n: int = 50, seed: int = 1) -> list[chess.Board]:
    """A mixed set of positions: WAC puzzles + positions after each opening."""
    boards = [p["board"] for p in load_epd()]
    boards += [chess.Board(o["fen"]) for o in load_openings()]
    rng = random.Random(seed)
    rng.shuffle(boards)
    return boards[:n]


# ------------------------------------------------------------------ players --
@dataclass
class PlayerSpec:
    """A picklable description of a player, so games can run in other processes."""
    name: str                       # "L1".."L4", "L3+full", ... or "stockfish"
    time_limit: float = 2.0
    stockfish_path: Optional[str] = None
    stockfish_elo: Optional[int] = None
    stockfish_skill: Optional[int] = None

    @property
    def label(self) -> str:
        if self.name == "stockfish":
            if self.stockfish_elo:
                return f"Stockfish (Elo {self.stockfish_elo})"
            return f"Stockfish (skill {self.stockfish_skill})"
        return self.name


class Player:
    def __init__(self, spec: PlayerSpec, seed: Optional[int] = None):
        self.spec = spec
        self.sf = None
        self.engine = None
        if spec.name == "stockfish":
            self.sf = chess.engine.SimpleEngine.popen_uci(spec.stockfish_path or "stockfish")
            opts = {"Threads": 1, "Hash": 16}
            if spec.stockfish_elo:
                opts.update({"UCI_LimitStrength": True, "UCI_Elo": spec.stockfish_elo})
            elif spec.stockfish_skill is not None:
                opts["Skill Level"] = spec.stockfish_skill
            self.sf.configure(opts)
        else:
            self.engine = make_variant(spec.name, time_limit=spec.time_limit, seed=seed)

    def new_game(self):
        if self.engine:
            self.engine.new_game()

    def choose(self, board: chess.Board) -> tuple[chess.Move, dict]:
        if self.sf:
            res = self.sf.play(board, chess.engine.Limit(time=self.spec.time_limit))
            return res.move, {}
        r = self.engine.choose_move(board)
        return r.move, {"depth": r.depth, "nodes": r.nodes, "time": r.time}

    def close(self):
        if self.sf:
            self.sf.quit()


# -------------------------------------------------------------------- games --
def play_game(white: PlayerSpec, black: PlayerSpec, opening: dict, *, max_plies: int = 200,
              adjudicate: bool = True, seed: int = 0) -> dict:
    """Play one game and return the result, PGN text and search statistics.

    Adjudication (to save time): a game is declared won when one side is up
    at least 10 pawns of material for 6 plies in a row, and drawn after
    ``max_plies`` plies.
    """
    board = chess.Board()
    for uci in opening["moves"]:
        board.push(chess.Move.from_uci(uci))
    players = {chess.WHITE: Player(white, seed=seed), chess.BLACK: Player(black, seed=seed + 1)}
    stats = {chess.WHITE: [], chess.BLACK: []}
    big_lead = 0
    reason = None
    result = None
    try:
        while not board.is_game_over(claim_draw=True):
            if len(board.move_stack) >= max_plies:
                result, reason = "1/2-1/2", "move limit"
                break
            player = players[board.turn]
            move, info = player.choose(board)
            if info:
                stats[board.turn].append(info)
            board.push(move)
            if adjudicate:
                mat = evaluate_material(board) * (1 if board.turn == chess.WHITE else -1)
                big_lead = big_lead + 1 if abs(mat) >= 1000 else 0
                if big_lead >= 6:
                    result = "1-0" if mat > 0 else "0-1"
                    reason = "adjudicated (material)"
                    break
        if result is None:
            outcome = board.outcome(claim_draw=True)
            result = outcome.result()
            reason = outcome.termination.name.lower().replace("_", " ")
    finally:
        for p in players.values():
            p.close()

    game = chess.pgn.Game.from_board(board)
    game.headers.update({"Event": "Chess in the Hand of AI benchmark", "White": white.label,
                         "Black": black.label, "Result": result, "Opening": opening["name"],
                         "Termination": reason})
    pgn = io.StringIO()
    print(game, file=pgn, end="\n\n")

    def avg(color, key):
        vals = [s[key] for s in stats[color]]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {"white": white.label, "black": black.label, "opening": opening["name"],
            "result": result, "reason": reason, "plies": len(board.move_stack),
            "white_avg_depth": avg(chess.WHITE, "depth"), "black_avg_depth": avg(chess.BLACK, "depth"),
            "white_avg_nodes": avg(chess.WHITE, "nodes"), "black_avg_nodes": avg(chess.BLACK, "nodes"),
            "pgn": pgn.getvalue()}


def _play_job(args):
    white, black, opening, kwargs = args
    return play_game(white, black, opening, **kwargs)


def run_games(jobs: list, workers: int, progress: bool = True) -> list[dict]:
    """Run (white, black, opening, kwargs) jobs in parallel processes."""
    results = []
    start = time.time()
    if workers <= 1:
        for i, job in enumerate(jobs, 1):
            results.append(_play_job(job))
            if progress:
                _progress(i, len(jobs), results[-1], start)
        return results
    from multiprocessing import Pool
    with Pool(workers) as pool:
        for i, res in enumerate(pool.imap_unordered(_play_job, jobs), 1):
            results.append(res)
            if progress:
                _progress(i, len(jobs), res, start)
    return results


def _progress(i, n, res, start):
    print(f"  [{i:>3}/{n}] {res['white']:>14} vs {res['black']:<14} {res['result']:>7}  "
          f"({res['plies']} plies, {res['reason']}) · {time.time() - start:.0f}s", flush=True)


# ---------------------------------------------------------------------- Elo --
def score_to_elo(score: float) -> float:
    score = min(max(score, 1e-3), 1 - 1e-3)
    return -400 * math.log10(1 / score - 1)


def elo_with_error(wins: int, draws: int, losses: int) -> tuple[float, float, float]:
    """Elo difference and its 95% confidence interval (low, high)."""
    n = wins + draws + losses
    if n == 0:
        return 0.0, 0.0, 0.0
    s = (wins + 0.5 * draws) / n
    if s in (0.0, 1.0):
        # A 0% or 100% score has no finite Elo: report it as None ("too strong to measure").
        return None, None, None
    var = (wins * (1 - s) ** 2 + draws * (0.5 - s) ** 2 + losses * (0 - s) ** 2) / n
    se = math.sqrt(var / n)
    return score_to_elo(s), score_to_elo(s - 1.96 * se), score_to_elo(s + 1.96 * se)


def fit_ratings(players: list[str], games: list[tuple[str, str, float]],
                anchor: Optional[str] = None, anchor_elo: float = 0.0) -> dict[str, float]:
    """Bradley–Terry (Elo) ratings by the MM algorithm.

    ``games`` holds (player_a, player_b, score_of_a). One virtual draw is added
    between every pair that met, so a 100% score does not give infinite Elo.
    """
    idx = {p: i for i, p in enumerate(players)}
    k = len(players)
    wins = [0.0] * k
    n = [[0.0] * k for _ in range(k)]
    for a, b, s in games:
        i, j = idx[a], idx[b]
        wins[i] += s
        wins[j] += 1 - s
        n[i][j] += 1
        n[j][i] += 1
    for i in range(k):
        for j in range(i + 1, k):
            if n[i][j]:
                n[i][j] += 1
                n[j][i] += 1
                wins[i] += 0.5
                wins[j] += 0.5
    gamma = [1.0] * k
    for _ in range(2000):
        new = []
        for i in range(k):
            denom = sum(n[i][j] / (gamma[i] + gamma[j]) for j in range(k) if j != i and n[i][j])
            new.append(wins[i] / denom if denom else gamma[i])
        gmean = math.exp(sum(math.log(max(g, 1e-12)) for g in new) / k)
        new = [g / gmean for g in new]
        if max(abs(a - b) for a, b in zip(new, gamma)) < 1e-9:
            gamma = new
            break
        gamma = new
    elo = {p: 400 * math.log10(max(gamma[idx[p]], 1e-12)) for p in players}
    ref = elo[anchor] if anchor in elo else min(elo.values())
    return {p: round(v - ref + anchor_elo, 1) for p, v in elo.items()}


# ------------------------------------------------------------------- output --
def save_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    keys = [k for k in rows[0].keys() if k != "pgn"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def save_pgn(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(r["pgn"])


def default_workers() -> int:
    return max(1, (os.cpu_count() or 2) - 1) if (os.cpu_count() or 1) > 2 else (os.cpu_count() or 1)
