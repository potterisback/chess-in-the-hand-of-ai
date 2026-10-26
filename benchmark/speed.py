"""Test 2 · Speed – how many positions each method checks.

Compares, at fixed depths 1..N on the same positions:
    minimax  |  alpha-beta  |  + move ordering  |  + transposition table
(No quiescence here, so all four search exactly the same tree depth.)

    python -m benchmark.speed --positions 20 --depth 4
"""

from __future__ import annotations

import argparse
from statistics import mean

from benchmark.common import RESULTS, save_csv, save_json, test_positions
from chessai.evaluation import get_evaluator
from chessai.search import AlphaBetaSearcher, minimax_search

METHODS = ["minimax", "alpha-beta", "+ move ordering", "+ memory table"]


def run_method(name, board, depth, evaluate):
    if name == "minimax":
        return minimax_search(board.copy(), depth, evaluate)
    opts = {"alpha-beta": dict(ordering=False),
            "+ move ordering": dict(ordering=True),
            "+ memory table": dict(ordering=True, use_tt=True, iterative=True)}[name]
    s = AlphaBetaSearcher(evaluate, iterative=opts.pop("iterative", False), **opts)
    if s.iterative:
        # With a memory table the normal way to search is iterative deepening:
        # the table from depth d-1 orders the moves at depth d.
        s.max_depth = depth
        return s.search(board)
    return s.search(board, depth=depth)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--positions", type=int, default=20)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--minimax-max-depth", type=int, default=3,
                    help="minimax gets very slow beyond depth 3 in Python")
    ap.add_argument("--eval", default="pst")
    args = ap.parse_args()

    evaluate = get_evaluator(args.eval)
    boards = test_positions(args.positions, seed=7)
    rows = []
    for d in range(1, args.depth + 1):
        for name in METHODS:
            if name == "minimax" and d > args.minimax_max_depth:
                continue
            for i, b in enumerate(boards, 1):
                r = run_method(name, b, d, evaluate)
                rows.append({"method": name, "depth": d, "position": i,
                             "nodes": r.nodes, "time": round(r.time, 4)})
            sub = [r for r in rows if r["method"] == name and r["depth"] == d]
            print(f"depth {d}  {name:<16} avg positions {mean(r['nodes'] for r in sub):>12,.0f}"
                  f"   avg time {mean(r['time'] for r in sub):7.3f} s", flush=True)

    summary = []
    for d in range(1, args.depth + 1):
        for name in METHODS:
            sub = [r for r in rows if r["method"] == name and r["depth"] == d]
            if sub:
                summary.append({"method": name, "depth": d,
                                "avg_nodes": round(mean(r["nodes"] for r in sub)),
                                "avg_time": round(mean(r["time"] for r in sub), 4)})
    save_csv(rows, RESULTS / "speed.csv")
    save_csv(summary, RESULTS / "speed_summary.csv")
    save_json(summary, RESULTS / "speed_summary.json")
    plot(summary)


def plot(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from benchmark.plotting import COLORS, style
    style(plt)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for name, color in zip(METHODS, COLORS):
        pts = [s for s in summary if s["method"] == name]
        if not pts:
            continue
        axes[0].plot([p["depth"] for p in pts], [p["avg_nodes"] for p in pts], "o-", color=color, label=name)
        axes[1].plot([p["depth"] for p in pts], [p["avg_time"] for p in pts], "o-", color=color, label=name)
    for ax, title in zip(axes, ["Positions checked", "Time per move (s)"]):
        ax.set_yscale("log")
        ax.set_xlabel("Depth (plies)")
        ax.set_title(title)
        ax.set_xticks(sorted({s["depth"] for s in summary}))
    axes[0].legend(frameon=False)
    fig.tight_layout()
    out = RESULTS / "speed.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
