"""Web interface (Member 5).

Run:   python -m app.server        then open http://127.0.0.1:5000

The browser keeps the list of moves played; every request sends that list,
so the server stays stateless (except for one engine object per level, which
keeps its transposition table between moves).
"""

from __future__ import annotations

import argparse
import threading
from pathlib import Path

import chess
import chess.svg
from flask import Flask, Response, abort, jsonify, request, send_from_directory

from chessai import LEVELS, LEVEL_NAMES, make_engine

STATIC = Path(__file__).parent / "static"
app = Flask(__name__, static_folder=None)

_engines: dict = {}
_lock = threading.Lock()


def get_engine(level: int, time_limit: float):
    key = (level, time_limit)
    if key not in _engines:
        _engines[key] = make_engine(level, time_limit=time_limit)
    return _engines[key]


def board_from_moves(moves: list[str], start_fen: str | None = None) -> chess.Board:
    board = chess.Board(start_fen) if start_fen else chess.Board()
    for uci in moves:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            abort(400, f"Illegal move {uci}")
        board.push(move)
    return board


def board_state(board: chess.Board) -> dict:
    # Replay the game to produce SAN notation for the move list
    replay = board.root()
    san = []
    for m in board.move_stack:
        san.append(replay.san(m))
        replay.push(m)
    outcome = board.outcome(claim_draw=True)
    status = "playing"
    result = None
    if outcome:
        result = outcome.result()
        reason = outcome.termination.name.replace("_", " ").lower()
        if outcome.winner is None:
            status = f"Draw ({reason})"
        else:
            status = f"{'White' if outcome.winner else 'Black'} wins ({reason})"
    return {
        "fen": board.fen(),
        "turn": "w" if board.turn else "b",
        "legal": [m.uci() for m in board.legal_moves] if not outcome else [],
        "san": san,
        "check": board.is_check(),
        "king": chess.square_name(board.king(board.turn)) if board.king(board.turn) is not None else None,
        "last": board.peek().uci() if board.move_stack else None,
        "status": status,
        "result": result,
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


@app.get("/api/levels")
def levels():
    return jsonify([
        {"level": lv, "name": LEVEL_NAMES[lv], "label": cfg.name,
         "algorithm": cfg.algorithm, "evaluation": cfg.evaluation,
         "depth": cfg.depth, "time_limit": cfg.time_limit}
        for lv, cfg in LEVELS.items()
    ])


@app.post("/api/state")
def state():
    data = request.get_json(force=True) or {}
    board = board_from_moves(data.get("moves", []), data.get("fen"))
    return jsonify(board_state(board))


@app.post("/api/ai")
def ai_move():
    data = request.get_json(force=True) or {}
    board = board_from_moves(data.get("moves", []), data.get("fen"))
    if board.is_game_over(claim_draw=True):
        return jsonify({"move": None, "state": board_state(board)})
    level = int(data.get("level", 3))
    time_limit = float(data.get("time", 2.0))
    time_limit = max(0.1, min(time_limit, 30.0))
    engine = get_engine(level, time_limit)
    with _lock:
        if not board.move_stack or len(board.move_stack) <= 1:
            engine.new_game()
        result = engine.choose_move(board)
    san = board.san(result.move)
    try:
        pv_san = board.variation_san(result.pv).split()
    except ValueError:
        pv_san = [m.uci() for m in result.pv]
    board.push(result.move)
    stats = result.to_dict()
    stats["pv"] = pv_san
    stats.pop("iterations", None)
    stats["san"] = san
    stats["engine"] = engine.name
    # Score from White's point of view, for the evaluation bar
    pov = 1 if not board.turn else -1     # the side that just moved
    stats["white_score"] = pov * result.score
    return jsonify({"move": result.move.uci(), "san": san, "stats": stats,
                    "state": board_state(board)})


def main():
    parser = argparse.ArgumentParser(description="Chess in the Hand of AI – web interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    print(f"Open http://{args.host}:{args.port} in your browser")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
