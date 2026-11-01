"""Web interface – mid-project version (two players, no AI yet).

Run:   python -m app.server        then open http://127.0.0.1:5000

The browser keeps the list of moves played; every request sends that list,
so the server stays stateless. The server only checks the chess rules
(legal moves, check, checkmate, draws) with the python-chess library.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import chess
import chess.svg
from flask import Flask, Response, abort, jsonify, request, send_from_directory

STATIC = Path(__file__).parent / "static"
app = Flask(__name__, static_folder=None)


def board_from_moves(moves: list[str]) -> chess.Board:
    """Replay the moves from the starting position, refusing illegal ones."""
    board = chess.Board()
    for uci in moves:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            abort(400, f"Bad move {uci}")
        if move not in board.legal_moves:
            abort(400, f"Illegal move {uci}")
        board.push(move)
    return board


def board_state(board: chess.Board) -> dict:
    """Everything the page needs to draw the position."""
    replay = chess.Board()
    san = []
    for m in board.move_stack:
        san.append(replay.san(m))
        replay.push(m)

    outcome = board.outcome(claim_draw=True)
    status = "playing"
    if outcome:
        reason = outcome.termination.name.replace("_", " ").lower()
        if outcome.winner is None:
            status = f"Draw ({reason})"
        else:
            status = f"{'White' if outcome.winner else 'Black'} wins ({reason})"

    king = board.king(board.turn)
    return {
        "fen": board.fen(),
        "turn": "w" if board.turn else "b",
        "legal": [m.uci() for m in board.legal_moves] if not outcome else [],
        "san": san,
        "check": board.is_check(),
        "king": chess.square_name(king) if king is not None else None,
        "last": board.peek().uci() if board.move_stack else None,
        "status": status,
        "game_over": outcome is not None,
    }


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/static/<path:name>")
def static_files(name):
    return send_from_directory(STATIC, name)


@app.get("/piece/<symbol>.svg")
def piece_svg(symbol: str):
    if len(symbol) != 1 or symbol not in "PNBRQKpnbrqk":
        abort(404)
    svg = chess.svg.piece(chess.Piece.from_symbol(symbol))
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "max-age=86400"})


@app.post("/api/state")
def state():
    data = request.get_json(force=True) or {}
    board = board_from_moves(data.get("moves", []))
    return jsonify(board_state(board))


def main():
    parser = argparse.ArgumentParser(description="Chess in the Hand of AI – web interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    print(f"Open http://{args.host}:{args.port} in your browser")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
