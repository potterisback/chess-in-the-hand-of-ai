import chess
import pytest

from chessai.evaluation import EVALUATORS, game_phase


@pytest.mark.parametrize("name", list(EVALUATORS))
def test_start_position_is_balanced(name):
    assert EVALUATORS[name](chess.Board()) == 0


@pytest.mark.parametrize("name", list(EVALUATORS))
def test_symmetry(name):
    """Mirroring the board and swapping colours must give the same score."""
    fens = [
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        "2rr3k/pp3pp1/1nnqbN1p/3pN3/2pP4/2P3Q1/PPB4P/R4RK1 w - - 0 1",
        "8/7p/5k2/5p2/p1p2P2/Pr1pPK2/1P1R3P/8 b - - 0 1",
    ]
    ev = EVALUATORS[name]
    for fen in fens:
        b = chess.Board(fen)
        assert ev(b) == ev(b.mirror())


@pytest.mark.parametrize("name", list(EVALUATORS))
def test_extra_queen_is_good(name):
    b = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert EVALUATORS[name](b) > 800
    b.turn = chess.BLACK
    assert EVALUATORS[name](b) < -800


def test_piece_square_tables_prefer_centre_knight():
    ev = EVALUATORS["pst"]
    centre = chess.Board("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1")
    corner = chess.Board("4k3/8/8/8/8/8/8/N3K3 w - - 0 1")
    assert ev(centre) > ev(corner)


def test_passed_pawn_and_phase():
    full = EVALUATORS["full"]
    passed = chess.Board("4k3/8/8/3P4/8/8/8/4K3 w - - 0 1")
    blocked = chess.Board("4k3/3p4/8/3P4/8/8/8/4K3 w - - 0 1")
    # a passed pawn is worth more than a plain pawn (100) in the endgame
    assert full(passed) > 130
    assert full(blocked) < full(passed)
    assert game_phase(chess.Board()) == 24
    assert game_phase(passed) == 0
