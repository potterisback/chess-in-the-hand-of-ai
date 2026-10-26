"""Search algorithms (Members 1, 2 and 3).

* ``greedy_search``      – Level 1: look 1 ply ahead, take the best-scoring move.
* ``minimax_search``     – Level 2: plain minimax (written in negamax form), fixed depth.
* ``AlphaBetaSearcher``  – Levels 3 and 4: alpha-beta with optional
    - move ordering (MVV-LVA captures, killer moves, history heuristic)   [Member 2]
    - iterative deepening under a time limit                              [Member 1]
    - transposition table ("memory of positions already seen")            [Member 3]
    - quiescence search ("extra checking of captures")                    [Member 3]

All scores are in centipawns from the side to move (negamax convention).
A depth of N means N plies (half-moves).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

import chess

from .evaluation import PIECE_VALUES

Evaluator = Callable[[chess.Board], int]

MATE = 100_000
MATE_BOUND = MATE - 1_000      # any |score| above this is a forced mate
INF = 10 ** 9

# Transposition-table entry flags
EXACT, LOWER, UPPER = 0, 1, 2


class SearchTimeout(Exception):
    """Raised inside the search when the time budget is spent."""


@dataclass
class SearchResult:
    move: Optional[chess.Move]
    score: int                    # centipawns, side to move
    depth: int                    # deepest *completed* iteration (plies)
    nodes: int                    # positions visited (main search + quiescence)
    qnodes: int = 0               # positions visited inside quiescence search
    time: float = 0.0             # seconds
    seldepth: int = 0             # deepest ply reached (including quiescence)
    tt_hits: int = 0
    cutoffs: int = 0              # beta cutoffs (alpha-beta only)
    pv: list = field(default_factory=list)
    iterations: list = field(default_factory=list)   # per-depth info (iterative deepening)

    @property
    def nps(self) -> float:
        return self.nodes / self.time if self.time > 0 else 0.0

    def score_text(self) -> str:
        return format_score(self.score)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["move"] = self.move.uci() if self.move else None
        d["pv"] = [m.uci() if isinstance(m, chess.Move) else m for m in self.pv]
        d["nps"] = round(self.nps)
        d["time"] = round(self.time, 3)
        d["score_text"] = self.score_text()
        return d


def format_score(score: int) -> str:
    if score > MATE_BOUND:
        return f"mate in {(MATE - score + 1) // 2}"
    if score < -MATE_BOUND:
        return f"mated in {(MATE + score + 1) // 2}"
    return f"{score / 100:+.2f}"


def is_search_draw(board: chess.Board) -> bool:
    """Cheap draw test used inside the search (not at the root)."""
    if board.halfmove_clock >= 100:
        return True
    if board.halfmove_clock >= 4 and board.is_repetition(2):
        return True
    if chess.popcount(board.occupied) <= 4 and board.is_insufficient_material():
        return True
    return False


# ---------------------------------------------------------------------------
# Level 1 – Greedy
# ---------------------------------------------------------------------------
def greedy_search(board: chess.Board, evaluate: Evaluator,
                  rng: Optional[random.Random] = None) -> SearchResult:
    """Look one ply ahead and pick the move with the best evaluation.

    Ties (very common with a material-only score) are broken at random, so the
    Easy level does not play the same game every time.
    """
    rng = rng or random.Random()
    start = time.perf_counter()
    best_score = -INF
    best_moves: list[chess.Move] = []
    nodes = 0
    for move in board.legal_moves:
        board.push(move)
        nodes += 1
        if board.is_checkmate():
            score = MATE - 1
        elif board.is_stalemate() or board.is_insufficient_material():
            score = 0
        else:
            score = -evaluate(board)
        board.pop()
        if score > best_score:
            best_score, best_moves = score, [move]
        elif score == best_score:
            best_moves.append(move)
    move = rng.choice(best_moves) if best_moves else None
    elapsed = time.perf_counter() - start
    return SearchResult(move=move, score=best_score if move else 0, depth=1,
                        nodes=nodes, time=elapsed, pv=[move] if move else [])


# ---------------------------------------------------------------------------
# Level 2 – Minimax (negamax form, no pruning)
# ---------------------------------------------------------------------------
def minimax_search(board: chess.Board, depth: int, evaluate: Evaluator) -> SearchResult:
    """Full-width minimax to a fixed depth.

    Negamax is the same algorithm as minimax: instead of a "max" function for
    White and a "min" function for Black, we always maximise and flip the
    sign: max(a, b) = -min(-a, -b).
    """
    start = time.perf_counter()
    counter = [0]

    def negamax(d: int, ply: int) -> int:
        counter[0] += 1
        if ply > 0 and is_search_draw(board):
            return 0
        if d == 0:
            return evaluate(board)
        moves = list(board.legal_moves)
        if not moves:
            return -(MATE - ply) if board.is_check() else 0
        best = -INF
        for m in moves:
            board.push(m)
            score = -negamax(d - 1, ply + 1)
            board.pop()
            if score > best:
                best = score
        return best

    counter[0] += 1
    best_move, best_score = None, -INF
    for m in board.legal_moves:
        board.push(m)
        score = -negamax(depth - 1, 1)
        board.pop()
        if score > best_score:
            best_move, best_score = m, score
    elapsed = time.perf_counter() - start
    return SearchResult(move=best_move, score=best_score if best_move else 0, depth=depth,
                        nodes=counter[0], time=elapsed, pv=[best_move] if best_move else [])


# ---------------------------------------------------------------------------
# Levels 3 and 4 – Alpha-beta and friends
# ---------------------------------------------------------------------------
def _position_key(board: chess.Board):
    # python-chess exposes a fast, hashable key for a position (pieces, side to
    # move, castling rights, en passant). It plays the role of a Zobrist hash.
    return board._transposition_key()


class AlphaBetaSearcher:
    """Alpha-beta search with switchable enhancements.

    Each enhancement can be turned on/off so the benchmark can measure how
    much it helps (ablation study).
    """

    def __init__(self, evaluate: Evaluator, *, ordering: bool = True,
                 iterative: bool = True, use_tt: bool = False,
                 quiescence: bool = False, max_depth: int = 64,
                 time_limit: Optional[float] = None, tt_size: int = 500_000,
                 pruning: bool = True):
        self.evaluate = evaluate
        self.ordering = ordering
        self.iterative = iterative
        self.use_tt = use_tt
        self.quiescence = quiescence
        self.max_depth = max_depth
        self.time_limit = time_limit
        self.tt_size = tt_size
        self.pruning = pruning          # False turns alpha-beta back into minimax (for tests)
        self.tt: dict = {}
        self.new_game()

    # -- state ---------------------------------------------------------------
    def new_game(self) -> None:
        self.tt.clear()
        self.history = [[0] * 64 for _ in range(64)]

    def _reset_counters(self) -> None:
        self.nodes = 0
        self.qnodes = 0
        self.tt_hits = 0
        self.cutoffs = 0
        self.seldepth = 0
        self.killers = [[None, None] for _ in range(self.max_depth + 2)]
        # Decay history so old games/moves weigh less
        for row in self.history:
            for i in range(64):
                row[i] >>= 2

    def _check_time(self) -> None:
        if self.deadline is not None and (self.nodes & 1023) == 0:
            if time.perf_counter() >= self.deadline:
                raise SearchTimeout

    # -- move ordering -------------------------------------------------------
    def _order_moves(self, board: chess.Board, moves: list, ply: int,
                     tt_move: Optional[chess.Move]) -> list:
        if not self.ordering:
            return moves
        killers = self.killers[ply] if ply < len(self.killers) else (None, None)
        history = self.history

        def key(m: chess.Move) -> int:
            if m == tt_move:
                return 10_000_000
            if board.is_capture(m):
                victim = board.piece_type_at(m.to_square) or chess.PAWN   # en passant
                attacker = board.piece_type_at(m.from_square)
                return 1_000_000 + 10 * PIECE_VALUES[victim] - PIECE_VALUES[attacker] // 10
            if m.promotion:
                return 900_000 + PIECE_VALUES[m.promotion]
            if m == killers[0]:
                return 800_000
            if m == killers[1]:
                return 790_000
            return history[m.from_square][m.to_square]

        return sorted(moves, key=key, reverse=True)

    def _store_killer(self, move: chess.Move, ply: int, board: chess.Board, depth: int) -> None:
        if board.is_capture(move) or move.promotion:
            return
        k = self.killers[ply]
        if k[0] != move:
            k[1] = k[0]
            k[0] = move
        self.history[move.from_square][move.to_square] += depth * depth

    # -- transposition table -------------------------------------------------
    @staticmethod
    def _to_tt(score: int, ply: int) -> int:
        if score > MATE_BOUND:
            return score + ply
        if score < -MATE_BOUND:
            return score - ply
        return score

    @staticmethod
    def _from_tt(score: int, ply: int) -> int:
        if score > MATE_BOUND:
            return score - ply
        if score < -MATE_BOUND:
            return score + ply
        return score

    def _tt_store(self, key, depth: int, score: int, flag: int, move, ply: int) -> None:
        if len(self.tt) >= self.tt_size:
            self.tt.clear()
        old = self.tt.get(key)
        if old is None or depth >= old[0]:
            self.tt[key] = (depth, self._to_tt(score, ply), flag, move)

    # -- quiescence search ---------------------------------------------------
    def _qsearch(self, board: chess.Board, alpha: int, beta: int, ply: int, qdepth: int) -> int:
        self.nodes += 1
        self.qnodes += 1
        if ply > self.seldepth:
            self.seldepth = ply
        self._check_time()

        in_check = board.is_check() and qdepth < 4
        if in_check:
            moves = list(board.legal_moves)
            if not moves:
                return -(MATE - ply)
            best = -INF
        else:
            stand_pat = self.evaluate(board)
            if stand_pat >= beta:
                return stand_pat
            if stand_pat > alpha:
                alpha = stand_pat
            best = stand_pat
            moves = [m for m in board.generate_legal_captures()]
            moves += [m for m in board.legal_moves
                      if m.promotion == chess.QUEEN and not board.is_capture(m)]

        moves = self._order_moves(board, moves, min(ply, self.max_depth), None) if self.ordering else moves
        for m in moves:
            if not in_check and board.is_capture(m):
                # Delta pruning: even winning this piece cannot raise alpha.
                victim = board.piece_type_at(m.to_square) or chess.PAWN
                if best + PIECE_VALUES[victim] + 200 < alpha and not m.promotion:
                    continue
            board.push(m)
            score = -self._qsearch(board, -beta, -alpha, ply + 1, qdepth + 1)
            board.pop()
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        return best

    # -- main search ---------------------------------------------------------
    def _negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.nodes += 1
        self._check_time()

        if is_search_draw(board):
            return 0

        if depth <= 0:
            if ply > self.seldepth:
                self.seldepth = ply
            if self.quiescence:
                self.nodes -= 1         # the qsearch call counts this node itself
                return self._qsearch(board, alpha, beta, ply, 0)
            return self.evaluate(board)

        alpha_orig = alpha
        tt_move = None
        key = None
        if self.use_tt:
            key = _position_key(board)
            entry = self.tt.get(key)
            if entry is not None:
                e_depth, e_score, e_flag, e_move = entry
                tt_move = e_move
                if e_depth >= depth:
                    self.tt_hits += 1
                    e_score = self._from_tt(e_score, ply)
                    if e_flag == EXACT:
                        return e_score
                    if e_flag == LOWER and e_score >= beta:
                        return e_score
                    if e_flag == UPPER and e_score <= alpha:
                        return e_score

        moves = list(board.legal_moves)
        if not moves:
            return -(MATE - ply) if board.is_check() else 0

        moves = self._order_moves(board, moves, ply, tt_move)
        best = -INF
        best_move = None
        for m in moves:
            board.push(m)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score > best:
                best = score
                best_move = m
            if score > alpha:
                alpha = score
            if self.pruning and alpha >= beta:
                self.cutoffs += 1
                if self.ordering:
                    self._store_killer(m, ply, board, depth)
                break

        if self.use_tt:
            if best <= alpha_orig:
                flag = UPPER
            elif best >= beta:
                flag = LOWER
            else:
                flag = EXACT
            self._tt_store(key, depth, best, flag, best_move, ply)
        return best

    def _search_root(self, board: chess.Board, depth: int, root_moves: list):
        alpha, beta = -INF, INF
        best_move, best_score = None, -INF
        self.nodes += 1
        for m in root_moves:
            board.push(m)
            score = -self._negamax(board, depth - 1, -beta, -alpha, 1)
            board.pop()
            if score > best_score:
                best_score, best_move = score, m
            if score > alpha:
                alpha = score
        if self.use_tt:
            self._tt_store(_position_key(board), depth, best_score, EXACT, best_move, 0)
        return best_move, best_score

    def _principal_variation(self, board: chess.Board, first: chess.Move, depth: int) -> list:
        pv = [first]
        if not self.use_tt:
            return pv
        b = board.copy(stack=False)
        b.push(first)
        seen = set()
        for _ in range(depth - 1):
            key = _position_key(b)
            if key in seen:
                break
            seen.add(key)
            entry = self.tt.get(key)
            if not entry or entry[3] is None or entry[3] not in b.legal_moves:
                break
            pv.append(entry[3])
            b.push(entry[3])
        return pv

    def search(self, board: chess.Board, depth: Optional[int] = None) -> SearchResult:
        """Search the position. ``depth`` overrides iterative deepening (fixed depth)."""
        board = board.copy()            # never modify the caller's board
        self._reset_counters()
        start = time.perf_counter()
        fixed = depth is not None
        self.deadline = (start + self.time_limit) if (self.time_limit and not fixed) else None

        root_moves = list(board.legal_moves)
        if not root_moves:
            return SearchResult(move=None, score=0, depth=0, nodes=0)
        root_moves = self._order_moves(board, root_moves, 0, None)

        best_move, best_score, done_depth = root_moves[0], 0, 0
        iterations = []
        depths = [depth] if fixed else (range(1, self.max_depth + 1) if self.iterative else [self.max_depth])

        root_ply = len(board.move_stack)
        for d in depths:
            try:
                move, score = self._search_root(board, d, root_moves)
            except SearchTimeout:
                # The search stopped in the middle of the tree: undo the moves
                # that were played on the board but never taken back.
                while len(board.move_stack) > root_ply:
                    board.pop()
                break
            best_move, best_score, done_depth = move, score, d
            elapsed = time.perf_counter() - start
            iterations.append({"depth": d, "move": move.uci(), "score": score,
                               "nodes": self.nodes, "time": round(elapsed, 3)})
            # Put the best move first for the next, deeper iteration
            if self.ordering:
                root_moves.remove(move)
                root_moves.insert(0, move)
            if abs(score) > MATE_BOUND:
                break           # forced mate found, no need to look deeper
            if self.deadline is not None and elapsed > 0.55 * self.time_limit:
                break           # the next iteration would almost surely not finish

        elapsed = time.perf_counter() - start
        return SearchResult(move=best_move, score=best_score, depth=done_depth,
                            nodes=self.nodes, qnodes=self.qnodes, time=elapsed,
                            seldepth=max(self.seldepth, done_depth), tt_hits=self.tt_hits, cutoffs=self.cutoffs,
                            pv=self._principal_variation(board, best_move, done_depth),
                            iterations=iterations)
