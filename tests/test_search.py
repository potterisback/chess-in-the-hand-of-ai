import chess
import pytest

from chessai.evaluation import evaluate_material, evaluate_pst
from chessai.search import MATE_BOUND, AlphaBetaSearcher, greedy_search, minimax_search

POSITIONS = [
    chess.STARTING_FEN,
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "2rr3k/pp3pp1/1nnqbN1p/3pN3/2pP4/2P3Q1/PPB4P/R4RK1 w - - 0 1",           # WAC.001
    "8/7p/5k2/5p2/p1p2P2/Pr1pPK2/1P1R3P/8 b - - 0 1",                         # WAC.002
    "r1b1k2r/ppppnppp/2n2q2/2b5/3NP3/2P1B3/PP3PPP/RN1QKB1R w KQkq - 0 1",
]


@pytest.mark.parametrize("fen", POSITIONS)
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_alphabeta_equals_minimax(fen, depth):
    board = chess.Board(fen)
    mm = minimax_search(board.copy(), depth, evaluate_pst)
    ab = AlphaBetaSearcher(evaluate_pst, ordering=False, iterative=False).search(board, depth=depth)
    ab_ord = AlphaBetaSearcher(evaluate_pst, ordering=True, iterative=False).search(board, depth=depth)
    assert mm.score == ab.score == ab_ord.score
    if depth >= 2:
        assert ab_ord.nodes <= mm.nodes


def test_alphabeta_without_pruning_visits_same_tree_as_minimax():
    board = chess.Board(POSITIONS[1])
    mm = minimax_search(board.copy(), 3, evaluate_pst)
    full = AlphaBetaSearcher(evaluate_pst, ordering=False, iterative=False, pruning=False).search(board, depth=3)
    assert mm.nodes == full.nodes and mm.score == full.score


def test_mate_in_one_found_by_all():
    board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1")    # Rd8#
    mate = chess.Move.from_uci("d1d8")
    assert greedy_search(board, evaluate_material).move == mate
    assert minimax_search(board.copy(), 3, evaluate_pst).move == mate
    r = AlphaBetaSearcher(evaluate_pst, use_tt=True, quiescence=True, time_limit=1).search(board)
    assert r.move == mate and r.score > MATE_BOUND


def test_back_rank_mate():
    # 1.Rxc8# – the engine must report a forced mate
    board = chess.Board("2r3k1/5ppp/8/8/8/8/5PPP/2R1R1K1 w - - 0 1")
    r = AlphaBetaSearcher(evaluate_pst, use_tt=True, quiescence=True, time_limit=3).search(board)
    assert r.score > MATE_BOUND
    assert r.move in (chess.Move.from_uci("e1e8"), chess.Move.from_uci("c1c8"))


def test_takes_free_queen():
    board = chess.Board("4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1")
    for searcher in (lambda b: greedy_search(b, evaluate_material),
                     lambda b: AlphaBetaSearcher(evaluate_pst, time_limit=0.5).search(b)):
        assert searcher(board).move == chess.Move.from_uci("d1d5")


def test_quiescence_avoids_poisoned_capture():
    # Qxb7?? Rxb7: without quiescence a depth-1 search grabs the pawn.
    board = chess.Board("1r4k1/1p3ppp/8/8/8/8/5PPP/1Q4K1 w - - 0 1")
    bad = chess.Move.from_uci("b1b7")
    with_q = AlphaBetaSearcher(evaluate_pst, quiescence=True, iterative=False).search(board, depth=1)
    no_q = AlphaBetaSearcher(evaluate_pst, quiescence=False, iterative=False).search(board, depth=1)
    assert no_q.move == bad
    assert with_q.move != bad


def test_time_limit_respected():
    board = chess.Board()
    r = AlphaBetaSearcher(evaluate_pst, use_tt=True, quiescence=True, time_limit=0.5).search(board)
    assert r.move in board.legal_moves
    assert r.time < 1.0
    assert r.depth >= 2


def test_search_does_not_modify_board():
    board = chess.Board(POSITIONS[2])
    fen = board.fen()
    AlphaBetaSearcher(evaluate_pst, use_tt=True, quiescence=True, time_limit=0.3).search(board)
    minimax_search(board, 2, evaluate_pst)
    assert board.fen() == fen


def test_stalemate_and_no_moves():
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")    # black stalemated
    r = AlphaBetaSearcher(evaluate_pst, time_limit=0.2).search(board)
    assert r.move is None


def test_timeout_mid_search_leaves_consistent_result():
    # Very short time: the search is cut in the middle of the tree many times.
    board = chess.Board("1r4k1/4p2p/2p1b1p1/p3Rp2/1bBP4/4P3/1PQ2PPP/6K1 b - - 0 1")
    for t in (0.01, 0.05, 0.2):
        r = AlphaBetaSearcher(evaluate_pst, use_tt=True, quiescence=True, time_limit=t).search(board)
        assert r.move in board.legal_moves
        b = board.copy()
        for m in r.pv:
            assert m in b.legal_moves
            b.push(m)
