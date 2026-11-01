"""Tests for the rules side of the web app (two-player mode)."""

from app.server import app


def state(moves):
    return app.test_client().post("/api/state", json={"moves": moves})


def test_start_position():
    data = state([]).get_json()
    assert data["turn"] == "w"
    assert len(data["legal"]) == 20
    assert not data["game_over"]


def test_both_sides_can_move():
    data = state(["e2e4", "e7e5"]).get_json()
    assert data["turn"] == "w"
    assert data["san"] == ["e4", "e5"]
    assert data["last"] == "e7e5"


def test_illegal_move_is_refused():
    assert state(["e2e5"]).status_code == 400


def test_checkmate_detected():
    data = state(["f2f3", "e7e5", "g2g4", "d8h4"]).get_json()   # fool's mate
    assert data["game_over"]
    assert data["status"].startswith("Black wins")
    assert data["legal"] == []
