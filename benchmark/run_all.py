"""Run all five tests one after another.

    python -m benchmark.run_all --quick     # ~30–40 min on a laptop, smaller settings
    python -m benchmark.run_all             # full settings from the proposal (several hours)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time


def run(module: str, *args: str) -> None:
    cmd = [sys.executable, "-m", f"benchmark.{module}", *args]
    print("\n" + "=" * 78 + f"\n$ {' '.join(cmd[1:])}\n" + "=" * 78, flush=True)
    start = time.time()
    subprocess.run(cmd, check=True)
    print(f"({time.time() - start:.0f} s)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="smaller settings for a fast check")
    ap.add_argument("--stockfish", default=None, help="path to Stockfish, to add it to the tournament")
    args = ap.parse_args()

    if args.quick:
        run("correctness", "--positions", "50", "--depth", "3")
        run("speed", "--positions", "10", "--depth", "4")
        run("puzzles", "--time", "1")
        run("evaluation_match", "--openings", "4", "--time", "0.3")
        extra = ["--stockfish", args.stockfish, "--sf-elo", "1320"] if args.stockfish else []
        run("tournament", "--openings", "6", "--time", "0.3", *extra)
    else:
        run("correctness", "--positions", "50", "--depth", "4")
        run("speed", "--positions", "20", "--depth", "5")
        run("puzzles", "--time", "2")
        run("evaluation_match", "--openings", "24", "--time", "1")
        extra = ["--stockfish", args.stockfish, "--sf-elo", "1320"] if args.stockfish else []
        run("tournament", "--openings", "24", "--time", "2", *extra)
    print("\nAll tests done. See the results/ folder.")


if __name__ == "__main__":
    main()
