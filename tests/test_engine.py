import chess
import pytest

from chessai import LEVELS, make_engine, make_variant


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_each_level_returns_legal_move(level):
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
    eng = make_engine(level, time_limit=0.3, seed=1)
    r = eng.choose_move(board)
    assert r.move in board.legal_moves
    assert r.nodes > 0
    d = r.to_dict()
    assert d["move"] == r.move.uci()


def test_level_settings_match_proposal():
    assert LEVELS[1].algorithm == "greedy" and LEVELS[1].evaluation == "material"
    assert LEVELS[2].algorithm == "minimax" and LEVELS[2].depth == 3
    assert LEVELS[3].ordering and LEVELS[3].iterative and not LEVELS[3].use_tt
    assert LEVELS[4].use_tt and LEVELS[4].quiescence and LEVELS[4].evaluation == "full"


def test_greedy_tie_break_is_random_but_seedable():
    board = chess.Board()
    a = [make_engine(1, seed=s).choose_move(board).move for s in range(10)]
    assert len(set(a)) > 1                                  # not always the same move
    assert make_engine(1, seed=3).choose_move(board).move == make_engine(1, seed=3).choose_move(board).move


def test_variants():
    v = make_variant("L3+full+TT")
    assert v.config.evaluation == "full" and v.config.use_tt and not v.config.quiescence
    with pytest.raises(ValueError):
        make_variant("L9")


def test_short_game_between_levels():
    board = chess.Board()
    white, black = make_engine(3, time_limit=0.1), make_engine(1, seed=0)
    for _ in range(20):
        if board.is_game_over():
            break
        eng = white if board.turn == chess.WHITE else black
        board.push(eng.choose_move(board).move)
    assert board.is_valid()
