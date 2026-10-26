"""Test 5 · Tactics – how many Win At Chess puzzles each level solves.

A puzzle is solved when the AI's move is one of the "best moves" (bm) of the
EPD record. Levels 3 and 4 get ``--time`` seconds per puzzle; levels 1 and 2
search to their fixed depth.

    python -m benchmark.puzzles --time 2
"""

from __future__ import annotations

import argparse
from multiprocessing import Pool

from benchmark.common import RESULTS, default_workers, load_epd, save_csv, save_json
from chessai import make_variant


def _solve(job):
    variant, time_limit, puzzle = job
    eng = make_variant(variant, time_limit=time_limit, seed=0)
    r = eng.choose_move(puzzle["board"])
    return {"engine": variant, "puzzle": puzzle["id"], "fen": puzzle["fen"],
            "best_moves": " ".join(puzzle["board"].san(m) for m in puzzle["bm"]),
            "played": puzzle["board"].san(r.move), "solved": r.move in puzzle["bm"],
            "depth": r.depth, "nodes": r.nodes, "time": round(r.time, 3)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engines", default="L1,L2,L3,L4", help="comma-separated, e.g. L1,L2,L3,L4,L3+Q")
    ap.add_argument("--time", type=float, default=2.0)
    ap.add_argument("--limit", type=int, default=50, help="number of puzzles")
    ap.add_argument("--workers", type=int, default=default_workers())
    args = ap.parse_args()

    puzzles = load_epd()[: args.limit]
    engines = [e.strip() for e in args.engines.split(",")]
    jobs = [(e, args.time, p) for e in engines for p in puzzles]
    print(f"{len(jobs)} searches on {args.workers} worker(s)…")
    with Pool(args.workers) as pool:
        rows = pool.map(_solve, jobs)

    summary = []
    for e in engines:
        sub = [r for r in rows if r["engine"] == e]
        solved = sum(r["solved"] for r in sub)
        summary.append({"engine": e, "solved": solved, "total": len(sub),
                        "percent": round(100 * solved / len(sub), 1),
                        "avg_depth": round(sum(r["depth"] for r in sub) / len(sub), 2)})
        print(f"{e:<10} {solved:>3}/{len(sub)} solved ({summary[-1]['percent']}%), "
              f"average depth {summary[-1]['avg_depth']}")

    save_csv(rows, RESULTS / "puzzles.csv")
    save_json(summary, RESULTS / "puzzles_summary.json")
    plot(summary)


def plot(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from benchmark.plotting import COLORS, style
    style(plt)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    names = [s["engine"] for s in summary]
    vals = [s["percent"] for s in summary]
    bars = ax.bar(names, vals, color=COLORS[: len(names)])
    for b, s in zip(bars, summary):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{s['solved']}/{s['total']}",
                ha="center", fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Puzzles solved (%)")
    ax.set_title("Win At Chess puzzles solved")
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    out = RESULTS / "puzzles.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
