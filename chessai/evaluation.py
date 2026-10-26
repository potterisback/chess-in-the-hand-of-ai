"""Position evaluation (Member 4).

Three score functions, from simplest to richest:

* ``material``      – piece values only (used by Level 1, Greedy)
* ``pst``           – material + piece-square tables (Levels 2 and 3)
* ``full``          – material + tapered piece-square tables + pawn structure
                      + mobility + bishop pair + game phase (Level 4)

Every function returns a score in centipawns **from the point of view of the
side to move** (positive = good for the player who is about to move). This is
the convention needed by the negamax search.

Piece-square tables come from Tomasz Michniewski's "Simplified Evaluation
Function" (chessprogramming.org). Tables are written the way you see the
board from White's side: the first row is rank 8, the last row is rank 1.
"""

from __future__ import annotations

import chess

# ---------------------------------------------------------------------------
# Piece values (centipawns)
# ---------------------------------------------------------------------------
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# ---------------------------------------------------------------------------
# Piece-square tables (rank 8 first, as seen from White's side)
# ---------------------------------------------------------------------------
_PAWN = [
     0,   0,   0,   0,   0,   0,   0,   0,
    50,  50,  50,  50,  50,  50,  50,  50,
    10,  10,  20,  30,  30,  20,  10,  10,
     5,   5,  10,  25,  25,  10,   5,   5,
     0,   0,   0,  20,  20,   0,   0,   0,
     5,  -5, -10,   0,   0, -10,  -5,   5,
     5,  10,  10, -20, -20,  10,  10,   5,
     0,   0,   0,   0,   0,   0,   0,   0,
]
_KNIGHT = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
_BISHOP = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
_ROOK = [
     0,   0,   0,   0,   0,   0,   0,   0,
     5,  10,  10,  10,  10,  10,  10,   5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
    -5,   0,   0,   0,   0,   0,   0,  -5,
     0,   0,   0,   5,   5,   0,   0,   0,
]
_QUEEN = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
]
_KING_MG = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
]
_KING_EG = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -30,   0,   0,   0,   0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]

_VISUAL_TABLES = {
    chess.PAWN: _PAWN,
    chess.KNIGHT: _KNIGHT,
    chess.BISHOP: _BISHOP,
    chess.ROOK: _ROOK,
    chess.QUEEN: _QUEEN,
    chess.KING: _KING_MG,
}


def _square_table(visual: list[int], color: chess.Color) -> list[int]:
    """Convert a 'visual' table to a list indexed by python-chess square.

    python-chess numbers squares a1=0 ... h8=63. The visual table starts at
    a8, so for White we flip the rank (``sq ^ 56``). Black uses the mirror
    image, which is simply the visual table read in square order.
    """
    if color == chess.WHITE:
        return [visual[sq ^ 56] for sq in chess.SQUARES]
    return [visual[sq] for sq in chess.SQUARES]


# Pre-computed lookup: value + square bonus, for each (piece, colour).
# Built once at import time so the evaluation loop is just additions.
PST = {
    color: {pt: [PIECE_VALUES[pt] + v for v in _square_table(_VISUAL_TABLES[pt], color)]
            for pt in chess.PIECE_TYPES}
    for color in chess.COLORS
}
KING_EG = {color: _square_table(_KING_EG, color) for color in chess.COLORS}
KING_MG = {color: _square_table(_KING_MG, color) for color in chess.COLORS}

# Game phase: 24 at the start (all minor/major pieces), 0 in a pawn ending.
PHASE_WEIGHTS = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}
MAX_PHASE = 24

# Extra terms used by the full evaluation
DOUBLED_PAWN = -15
ISOLATED_PAWN = -15
PASSED_PAWN_BONUS = [0, 10, 15, 25, 40, 65, 100, 0]   # by rank advanced (0..7)
BISHOP_PAIR = 30
MOBILITY_WEIGHT = {chess.KNIGHT: 4, chess.BISHOP: 4, chess.ROOK: 2, chess.QUEEN: 1}

_FILE_MASKS = [chess.BB_FILES[f] for f in range(8)]
_ADJACENT_FILES = [
    (chess.BB_FILES[f - 1] if f > 0 else 0) | (chess.BB_FILES[f + 1] if f < 7 else 0)
    for f in range(8)
]


def _passed_pawn_mask(square: chess.Square, color: chess.Color) -> int:
    """Squares in front of a pawn (same + adjacent files) that enemy pawns must not occupy."""
    f = chess.square_file(square)
    r = chess.square_rank(square)
    files = _FILE_MASKS[f] | _ADJACENT_FILES[f]
    if color == chess.WHITE:
        ranks = 0
        for rr in range(r + 1, 8):
            ranks |= chess.BB_RANKS[rr]
    else:
        ranks = 0
        for rr in range(0, r):
            ranks |= chess.BB_RANKS[rr]
    return files & ranks


PASSED_MASKS = {
    color: [_passed_pawn_mask(sq, color) for sq in chess.SQUARES] for color in chess.COLORS
}


# ---------------------------------------------------------------------------
# Score functions
# ---------------------------------------------------------------------------
def evaluate_material(board: chess.Board) -> int:
    """Material only. Score from the side to move."""
    score = 0
    for pt in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        value = PIECE_VALUES[pt]
        score += value * (chess.popcount(board.pieces_mask(pt, chess.WHITE))
                          - chess.popcount(board.pieces_mask(pt, chess.BLACK)))
    return score if board.turn == chess.WHITE else -score


def evaluate_pst(board: chess.Board) -> int:
    """Material + piece-square tables. Score from the side to move."""
    score = 0
    for color in chess.COLORS:
        sign = 1 if color == chess.WHITE else -1
        tables = PST[color]
        for pt in chess.PIECE_TYPES:
            table = tables[pt]
            for sq in chess.scan_forward(board.pieces_mask(pt, color)):
                score += sign * table[sq]
    return score if board.turn == chess.WHITE else -score


def game_phase(board: chess.Board) -> int:
    """24 = opening/middlegame with all pieces, 0 = only kings and pawns."""
    phase = 0
    for pt, w in PHASE_WEIGHTS.items():
        phase += w * chess.popcount(board.pieces_mask(pt, chess.WHITE) | board.pieces_mask(pt, chess.BLACK))
    return min(phase, MAX_PHASE)


def _pawn_structure(board: chess.Board, color: chess.Color) -> tuple[int, int]:
    """Return (middlegame, endgame) pawn-structure score for one side."""
    mg = eg = 0
    own = board.pieces_mask(chess.PAWN, color)
    enemy = board.pieces_mask(chess.PAWN, not color)
    for f in range(8):
        n = chess.popcount(own & _FILE_MASKS[f])
        if n > 1:
            mg += DOUBLED_PAWN * (n - 1)
            eg += DOUBLED_PAWN * (n - 1)
        if n and not (own & _ADJACENT_FILES[f]):
            mg += ISOLATED_PAWN * n
            eg += ISOLATED_PAWN * n
    for sq in chess.scan_forward(own):
        if not (enemy & PASSED_MASKS[color][sq]):
            rank = chess.square_rank(sq) if color == chess.WHITE else 7 - chess.square_rank(sq)
            bonus = PASSED_PAWN_BONUS[rank]
            mg += bonus // 2
            eg += bonus          # passed pawns matter more in the endgame
    return mg, eg


def _mobility(board: chess.Board, color: chess.Color) -> int:
    """Number of squares attacked by minor/major pieces, not occupied by own pieces."""
    own = board.occupied_co[color]
    total = 0
    for pt, w in MOBILITY_WEIGHT.items():
        for sq in chess.scan_forward(board.pieces_mask(pt, color)):
            total += w * chess.popcount(board.attacks_mask(sq) & ~own)
    return total


def evaluate_full(board: chess.Board) -> int:
    """Full evaluation with game phase. Score from the side to move."""
    phase = game_phase(board)
    mg = eg = 0
    for color in chess.COLORS:
        sign = 1 if color == chess.WHITE else -1
        tables = PST[color]
        # Material + piece-square tables (king handled separately)
        for pt in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            table = tables[pt]
            for sq in chess.scan_forward(board.pieces_mask(pt, color)):
                v = sign * table[sq]
                mg += v
                eg += v
        king_sq = board.king(color)
        if king_sq is not None:
            mg += sign * KING_MG[color][king_sq]
            eg += sign * KING_EG[color][king_sq]
        # Pawn structure
        p_mg, p_eg = _pawn_structure(board, color)
        mg += sign * p_mg
        eg += sign * p_eg
        # Bishop pair
        if chess.popcount(board.pieces_mask(chess.BISHOP, color)) >= 2:
            mg += sign * BISHOP_PAIR
            eg += sign * BISHOP_PAIR
        # Mobility
        mob = _mobility(board, color)
        mg += sign * mob
        eg += sign * mob
    # Tapered score: blend middlegame and endgame by the game phase
    # int(.../...) rounds toward zero, so White and Black are treated the same
    score = int((mg * phase + eg * (MAX_PHASE - phase)) / MAX_PHASE)
    return score if board.turn == chess.WHITE else -score


EVALUATORS = {
    "material": evaluate_material,
    "pst": evaluate_pst,
    "full": evaluate_full,
}


def get_evaluator(name: str):
    try:
        return EVALUATORS[name]
    except KeyError:
        raise ValueError(f"Unknown evaluation '{name}'. Choose from {list(EVALUATORS)}") from None
