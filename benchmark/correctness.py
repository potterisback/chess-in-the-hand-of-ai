"""Test 1 · Correctness – alpha-beta must give the same score as minimax.

Alpha-beta and minimax search the same 50 positions at the same depth.
We compare the *scores* (two different moves can have the same score, so
comparing moves would give false alarms). The transposition table and
quiescence search are switched off, because they legitimately change scores.

    python -m benchmark.correctness --depth 3
"""

from __future__ import annotations

import argparse

from benchmark.common import RESULTS, save_csv, save_json, test_positions
from chessai.evaluation import get_evaluator
from chessai.search import AlphaBetaSearcher, minimax_search


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--positions", type=int, default=50)
    ap.add_argument("--depth", type=int, default=3, help="max depth (plies); every depth 1..N is tested")
    ap.add_argument("--eval", default="pst", choices=["material", "pst", "full"])
    args = ap.parse_args()

    evaluate = get_evaluator(args.eval)
    boards = test_positions(args.positions)
    rows = []
    for d in range(1, args.depth + 1):
        same = 0
        for i, board in enumerate(boards, 1):
            mm = minimax_search(board.copy(), d, evaluate)
            ab_plain = AlphaBetaSearcher(evaluate, ordering=False, iterative=False).search(board, depth=d)
            ab_order = AlphaBetaSearcher(evaluate, ordering=True, iterative=False).search(board, depth=d)
            ok = mm.score == ab_plain.score == ab_order.score
            same += ok
            rows.append({"position": i, "fen": board.fen(), "depth": d,
                         "minimax_score": mm.score, "alphabeta_score": ab_plain.score,
                         "alphabeta_ordered_score": ab_order.score,
                         "minimax_move": mm.move.uci(), "alphabeta_move": ab_order.move.uci(),
                         "same_score": ok, "same_move": mm.move == ab_order.move})
        print(f"depth {d}: {same}/{len(boards)} positions give the same score")

    total_ok = sum(r["same_score"] for r in rows)
    summary = {"positions": len(boards), "depths": list(range(1, args.depth + 1)),
               "checks": len(rows), "same_score": total_ok,
               "same_move": sum(r["same_move"] for r in rows),
               "all_correct": total_ok == len(rows)}
    save_csv(rows, RESULTS / "correctness.csv")
    save_json(summary, RESULTS / "correctness_summary.json")
    print(f"\n{'PASS' if summary['all_correct'] else 'FAIL'}: {total_ok}/{len(rows)} checks give the same score "
          f"(same move in {summary['same_move']}/{len(rows)}).")
    print(f"Saved {RESULTS / 'correctness.csv'}")


if __name__ == "__main__":
    main()
