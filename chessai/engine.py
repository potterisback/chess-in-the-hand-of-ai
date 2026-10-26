"""The four AI levels and a common ``Engine`` interface.

    Level 1 · Easy    Greedy       1 ply, material only
    Level 2 · Medium  Minimax      3 plies (fixed), material + piece-square tables
    Level 3 · Hard    Alpha-beta   + move ordering + iterative deepening, 2 s/move, material + PST
    Level 4 · Master  Full engine  Level 3 + transposition table + quiescence, full evaluation

Any setting can be overridden, which is how the benchmark builds the
"ablation" variants (e.g. Level 3 with the full evaluation).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace, asdict
from typing import Optional

import chess

from .evaluation import get_evaluator
from .search import AlphaBetaSearcher, SearchResult, greedy_search, minimax_search


@dataclass(frozen=True)
class EngineConfig:
    name: str
    algorithm: str                 # "greedy" | "minimax" | "alphabeta"
    evaluation: str                # "material" | "pst" | "full"
    depth: Optional[int] = None    # fixed depth (plies); None = iterative deepening
    time_limit: Optional[float] = None   # seconds per move (alpha-beta only)
    ordering: bool = False
    iterative: bool = False
    use_tt: bool = False
    quiescence: bool = False
    max_depth: int = 64


LEVELS: dict[int, EngineConfig] = {
    1: EngineConfig(name="L1 Easy (Greedy)", algorithm="greedy", evaluation="material", depth=1),
    2: EngineConfig(name="L2 Medium (Minimax)", algorithm="minimax", evaluation="pst", depth=3),
    3: EngineConfig(name="L3 Hard (Alpha-beta)", algorithm="alphabeta", evaluation="pst",
                    time_limit=2.0, ordering=True, iterative=True),
    4: EngineConfig(name="L4 Master (Full engine)", algorithm="alphabeta", evaluation="full",
                    time_limit=2.0, ordering=True, iterative=True, use_tt=True, quiescence=True),
}

LEVEL_NAMES = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Master"}


class Engine:
    """Wraps one configuration. Use ``choose_move(board)`` to get a move."""

    def __init__(self, config: EngineConfig, seed: Optional[int] = None):
        self.config = config
        self.evaluate = get_evaluator(config.evaluation)
        self.rng = random.Random(seed)
        self._searcher: Optional[AlphaBetaSearcher] = None
        if config.algorithm == "alphabeta":
            self._searcher = AlphaBetaSearcher(
                self.evaluate,
                ordering=config.ordering,
                iterative=config.iterative,
                use_tt=config.use_tt,
                quiescence=config.quiescence,
                max_depth=config.max_depth,
                time_limit=config.time_limit,
            )
        elif config.algorithm not in ("greedy", "minimax"):
            raise ValueError(f"Unknown algorithm {config.algorithm!r}")

    @property
    def name(self) -> str:
        return self.config.name

    def new_game(self) -> None:
        if self._searcher:
            self._searcher.new_game()

    def choose_move(self, board: chess.Board) -> SearchResult:
        c = self.config
        if c.algorithm == "greedy":
            return greedy_search(board, self.evaluate, self.rng)
        if c.algorithm == "minimax":
            return minimax_search(board.copy(), c.depth or 3, self.evaluate)
        return self._searcher.search(board, depth=c.depth)

    def describe(self) -> dict:
        return asdict(self.config)


def make_engine(level: int, time_limit: Optional[float] = None, seed: Optional[int] = None,
                **overrides) -> Engine:
    """Build the engine for a level (1–4). ``time_limit`` changes seconds per move."""
    if level not in LEVELS:
        raise ValueError("level must be 1, 2, 3 or 4")
    cfg = LEVELS[level]
    if time_limit is not None and cfg.algorithm == "alphabeta":
        cfg = replace(cfg, time_limit=time_limit)
    if overrides:
        cfg = replace(cfg, **overrides)
    return Engine(cfg, seed=seed)


# Variants used by the ablation / evaluation benchmarks -----------------------
def make_variant(name: str, time_limit: float = 2.0, seed: Optional[int] = None) -> Engine:
    """Named variants: L1..L4 plus ablations such as 'L3+full', 'L3+TT', 'L3+Q'."""
    base = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
    parts = name.split("+")
    level = base.get(parts[0])
    if level is None:
        raise ValueError(f"Unknown variant {name!r}")
    overrides: dict = {}
    for p in parts[1:]:
        p = p.strip()
        if p in ("material", "pst", "full"):
            overrides["evaluation"] = p
        elif p.upper() == "TT":
            overrides["use_tt"] = True
        elif p.upper() == "Q":
            overrides["quiescence"] = True
        else:
            raise ValueError(f"Unknown variant part {p!r} in {name!r}")
    eng = make_engine(level, time_limit=time_limit, seed=seed, **overrides)
    eng.config = replace(eng.config, name=name if len(parts) > 1 else eng.config.name)
    return eng
