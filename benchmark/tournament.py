"""Test 4 · Strength – AI-vs-AI round robin with Elo and error bars.

Every pair of engines plays each opening twice (once with each colour).
Optionally a weakened Stockfish joins as a reference point.

    python -m benchmark.tournament --engines L1,L2,L3,L4 --openings 24 --time 2
    python -m benchmark.tournament --stockfish /usr/games/stockfish --sf-elo 1320

Outputs: results/tournament_*.csv/json/png and results/games/tournament.pgn
"""

from __future__ import annotations

import argparse
from itertools import combinations

from benchmark.common import (RESULTS, PlayerSpec, default_workers, elo_with_error, fit_ratings,
                              load_openings, run_games, save_csv, save_json, save_pgn)


def round_robin(specs: list[PlayerSpec], openings: list[dict], *, workers: int, max_plies: int,
                adjudicate: bool, tag: str, anchor: str | None = None, anchor_elo: float = 0.0) -> dict:
    jobs = []
    seed = 0
    for a, b in combinations(specs, 2):
        for op in openings:
            kw = dict(max_plies=max_plies, adjudicate=adjudicate, seed=seed)
            jobs.append((a, b, op, kw))
            jobs.append((b, a, op, dict(kw, seed=seed + 2)))
            seed += 4
    print(f"{len(jobs)} games on {workers} worker(s)…")
    games = run_games(jobs, workers)
    save_pgn(games, RESULTS / "games" / f"{tag}.pgn")
    return summarize(games, [s.label for s in specs], tag, anchor, anchor_elo)


def summarize(games: list[dict], labels: list[str], tag: str, anchor: str | None = None,
              anchor_elo: float = 0.0) -> dict:
    """Build the tables, Elo and chart from a list of finished games."""
    # Pairwise table -----------------------------------------------------------
    pairs = []
    for a, b in combinations(labels, 2):
        w = d = l = 0
        for g in games:
            if {g["white"], g["black"]} != {a, b}:
                continue
            if g["result"] == "1/2-1/2":
                d += 1
            elif (g["result"] == "1-0") == (g["white"] == a):
                w += 1
            else:
                l += 1
        elo, lo, hi = elo_with_error(w, d, l)
        pairs.append({"player": a, "opponent": b, "wins": w, "draws": d, "losses": l,
                      "score": round((w + d / 2) / max(1, w + d + l), 3),
                      "elo_diff": None if elo is None else round(elo),
                      "elo_low": None if lo is None else round(lo),
                      "elo_high": None if hi is None else round(hi)})

    # Overall ratings ------------------------------------------------------------
    scored = []
    for g in games:
        s = {"1-0": 1.0, "0-1": 0.0}.get(g["result"], 0.5)
        scored.append((g["white"], g["black"], s))
    ratings = fit_ratings(labels, scored, anchor=anchor, anchor_elo=anchor_elo)
    table = []
    for lab in labels:
        mine = [g for g in games if lab in (g["white"], g["black"])]
        pts = sum({"1-0": 1.0, "0-1": 0.0}.get(g["result"], 0.5) if g["white"] == lab
                  else 1 - {"1-0": 1.0, "0-1": 0.0}.get(g["result"], 0.5) for g in mine)
        table.append({"engine": lab, "games": len(mine), "points": pts,
                      "score_pct": round(100 * pts / max(1, len(mine)), 1), "elo": ratings[lab]})
    table.sort(key=lambda r: -r["elo"])

    print("\nPairwise results (Elo difference with 95% interval):")
    for p in pairs:
        elo = ("no finite Elo (100% score)" if p["elo_diff"] is None
               else f"Elo {p['elo_diff']:+5d}  [{p['elo_low']:+d}, {p['elo_high']:+d}]")
        print(f"  {p['player']:>14} vs {p['opponent']:<14} +{p['wins']} ={p['draws']} -{p['losses']}   {elo}")
    ref = f"anchored at {anchor} = {anchor_elo:.0f}" if anchor else "lowest engine = 0"
    print(f"\nRatings ({ref}):")
    for r in table:
        print(f"  {r['engine']:<26} {r['elo']:>7.0f}   {r['points']}/{r['games']} ({r['score_pct']}%)")

    save_csv(games, RESULTS / f"{tag}_games.csv")
    save_csv(pairs, RESULTS / f"{tag}_pairs.csv")
    save_csv(table, RESULTS / f"{tag}_ratings.csv")
    save_json({"pairs": pairs, "ratings": table, "games": len(games), "anchor": ref},
              RESULTS / f"{tag}_summary.json")
    plot(pairs, table, tag)
    return {"pairs": pairs, "ratings": table}


def plot(pairs, table, tag):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from benchmark.plotting import COLORS, style
    style(plt)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1, 1.4]})
    names = [r["engine"] for r in table][::-1]
    axes[0].barh(names, [r["elo"] for r in table][::-1], color=COLORS[0])
    axes[0].set_title("Rating (Elo)")
    axes[0].grid(axis="y", visible=False)

    labels = [f"{p['player']} vs {p['opponent']}" for p in pairs]
    y = range(len(pairs))
    w = [p["wins"] for p in pairs]
    d = [p["draws"] for p in pairs]
    l = [p["losses"] for p in pairs]
    axes[1].barh(y, w, color=COLORS[2], label="wins")
    axes[1].barh(y, d, left=w, color="#bdbdbd", label="draws")
    axes[1].barh(y, l, left=[a + b for a, b in zip(w, d)], color=COLORS[4], label="losses")
    axes[1].set_yticks(list(y), labels)
    axes[1].invert_yaxis()
    axes[1].set_title("Results (first player's view)")
    axes[1].legend(frameon=False, ncol=3, loc="lower right", bbox_to_anchor=(1, 1.06))
    axes[1].grid(axis="y", visible=False)
    fig.tight_layout()
    out = RESULTS / f"{tag}.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engines", default="L1,L2,L3,L4",
                    help="comma-separated: L1..L4 or variants like L3+full, L3+TT, L3+Q")
    ap.add_argument("--openings", type=int, default=24, help="number of openings (each played twice)")
    ap.add_argument("--time", type=float, default=2.0, help="seconds per move for L3/L4/Stockfish")
    ap.add_argument("--max-plies", type=int, default=200)
    ap.add_argument("--no-adjudicate", action="store_true")
    ap.add_argument("--workers", type=int, default=default_workers())
    ap.add_argument("--stockfish", default=None, help="path to a Stockfish binary (optional)")
    ap.add_argument("--sf-elo", type=int, default=None, help="UCI_Elo for Stockfish (minimum 1320)")
    ap.add_argument("--sf-skill", type=int, default=None, help="Skill Level 0–20 (if no --sf-elo)")
    ap.add_argument("--tag", default="tournament")
    ap.add_argument("--from-csv", action="store_true",
                    help="do not play: rebuild tables and chart from results/<tag>_games.csv")
    args = ap.parse_args()

    if args.from_csv:
        import csv
        with open(RESULTS / f"{args.tag}_games.csv", encoding="utf-8") as f:
            games = list(csv.DictReader(f))
        labels = list(dict.fromkeys([g["white"] for g in games] + [g["black"] for g in games]))
        sf = [l for l in labels if l.startswith("Stockfish (Elo")]
        anchor = sf[0] if sf else None
        anchor_elo = float(sf[0].split()[-1].rstrip(")")) if sf else 0.0
        order = sorted(labels, key=lambda l: (l.startswith("Stockfish"), l))
        summarize(games, order, args.tag, anchor, anchor_elo)
        return

    specs = [PlayerSpec(e.strip(), time_limit=args.time) for e in args.engines.split(",")]
    anchor, anchor_elo = None, 0.0
    if args.stockfish:
        sf = PlayerSpec("stockfish", time_limit=args.time, stockfish_path=args.stockfish,
                        stockfish_elo=args.sf_elo, stockfish_skill=args.sf_skill if args.sf_elo is None else None)
        if sf.stockfish_elo is None and sf.stockfish_skill is None:
            sf.stockfish_elo = 1320
        specs.append(sf)
        if sf.stockfish_elo:
            anchor, anchor_elo = sf.label, float(sf.stockfish_elo)
    openings = load_openings()[: args.openings]
    round_robin(specs, openings, workers=args.workers, max_plies=args.max_plies,
                adjudicate=not args.no_adjudicate, tag=args.tag, anchor=anchor, anchor_elo=anchor_elo)


if __name__ == "__main__":
    main()
