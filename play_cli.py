"""Play against the AI in the terminal (no browser needed).

    python play_cli.py --level 3 --color white --time 2

Type moves in SAN (e4, Nf3, O-O, exd5, e8=Q) or UCI (e2e4).
Commands: 'undo', 'board', 'quit'.
"""

from __future__ import annotations

import argparse

import chess

from chessai import LEVEL_NAMES, make_engine


def print_board(board: chess.Board, white_bottom: bool) -> None:
    text = str(board) if white_bottom else "\n".join(line[::-1] for line in str(board).split("\n")[::-1])
    files = "a b c d e f g h" if white_bottom else "h g f e d c b a"
    ranks = range(8, 0, -1) if white_bottom else range(1, 9)
    for r, line in zip(ranks, text.split("\n")):
        print(f" {r}  {line}")
    print(f"\n    {files}\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--level", type=int, default=3, choices=[1, 2, 3, 4])
    p.add_argument("--color", default="white", choices=["white", "black"])
    p.add_argument("--time", type=float, default=2.0, help="seconds per move (levels 3–4)")
    p.add_argument("--fen", default=None, help="start from this position")
    args = p.parse_args()

    board = chess.Board(args.fen) if args.fen else chess.Board()
    human = chess.WHITE if args.color == "white" else chess.BLACK
    engine = make_engine(args.level, time_limit=args.time)
    print(f"You play {args.color} against Level {args.level} · {LEVEL_NAMES[args.level]} ({engine.name})\n")

    while not board.is_game_over(claim_draw=True):
        if board.turn == human:
            print_board(board, human == chess.WHITE)
            text = input("Your move: ").strip()
            if text in ("quit", "exit"):
                return
            if text == "board":
                continue
            if text == "undo":
                for _ in range(2):
                    if board.move_stack:
                        board.pop()
                continue
            try:
                move = board.parse_san(text)
            except ValueError:
                try:
                    move = chess.Move.from_uci(text)
                    if move not in board.legal_moves:
                        raise ValueError
                except ValueError:
                    print("  Illegal or unreadable move. Example: e4, Nf3, O-O, e7e8q")
                    continue
            board.push(move)
        else:
            result = engine.choose_move(board)
            san = board.san(result.move)
            board.push(result.move)
            print(f"AI plays {san}   (score {result.score_text()}, depth {result.depth}, "
                  f"{result.nodes:,} positions, {result.time:.2f} s)")

    print_board(board, human == chess.WHITE)
    outcome = board.outcome(claim_draw=True)
    print(f"Game over: {outcome.result()} ({outcome.termination.name.lower()})")


if __name__ == "__main__":
    main()
