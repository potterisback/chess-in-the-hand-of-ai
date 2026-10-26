"""Test 3 · Evaluation – same search, three score functions.

The Level 4 search (alpha-beta + ordering + memory table + quiescence) plays
with each of the three evaluation functions, round robin:

    L4+material   vs   L4+pst   vs   L4 (full)

Because the search is identical, any difference in results comes from the
evaluation alone.

    python -m benchmark.evaluation_match --openings 24 --time 1
"""

from __future__ import annotations

import argparse

from benchmark.common import PlayerSpec, default_workers, load_openings
from benchmark.tournament import round_robin


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openings", type=int, default=24)
    ap.add_argument("--time", type=float, default=1.0)
    ap.add_argument("--max-plies", type=int, default=200)
    ap.add_argument("--workers", type=int, default=default_workers())
    args = ap.parse_args()

    specs = [PlayerSpec(name, time_limit=args.time) for name in ("L4+material", "L4+pst", "L4+full")]
    round_robin(specs, load_openings()[: args.openings], workers=args.workers,
                max_plies=args.max_plies, adjudicate=True, tag="evaluation", anchor="L4+material")


if __name__ == "__main__":
    main()
