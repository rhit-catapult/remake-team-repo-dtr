"""Shared leaderboard + high-score store.

Persists to highscores.json next to this file. For scored games each entry is a
per-player best: highscores.json looks like
    {"slime": {"ALICE": 312, "BOB": 190}, "flappy": {...}, "karate_red": 4, ...}

Games just call record(game, score); it credits the *current player* (set by the
launcher via the ARCADE_PLAYER env var, or the saved name otherwise) and keeps
that player's best — so no game needs to know about names.
"""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscores.json")
TOP_N = 10


def load():
    """Return the whole store dict (empty if missing/unreadable)."""
    try:
        with open(_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    try:
        with open(_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# --- Current player name ------------------------------------------------------

def get_player():
    """The saved player name (default 'YOU')."""
    name = load().get("_player")
    return name if isinstance(name, str) and name else "YOU"


def set_player(name):
    """Persist the player name (used by the launcher)."""
    data = load()
    data["_player"] = _clean(name)
    _save(data)


def _clean(name):
    name = (name or "YOU").strip()[:12]
    return name or "YOU"


def _current_name():
    """Name to credit a score to: the launcher's env var, else the saved name."""
    return _clean(os.environ.get("ARCADE_PLAYER") or get_player())


# --- Scored games (per-name leaderboards) ------------------------------------

def _board(data, game):
    """Normalize a game's stored value to a {name: best} dict."""
    value = data.get(game)
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (int, float)):      # legacy single score
        return {"—": int(value)}
    return {}


def record(game, score):
    """Credit `score` to the current player under `game`, keeping their best.

    Returns the overall best score for the game (so callers can display it).
    """
    data = load()
    board = _board(data, game)
    name = _current_name()
    if int(score) > board.get(name, 0):
        board[name] = int(score)
        data[game] = board
        _save(data)
    return max(board.values()) if board else 0


def get(game):
    """Overall best score for `game` (or the raw int for counter keys)."""
    value = load().get(game)
    if isinstance(value, dict):
        return max(value.values()) if value else 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def top(game, n=TOP_N):
    """Leaderboard: list of (name, score) sorted high-to-low, up to n entries."""
    board = _board(load(), game)
    return sorted(board.items(), key=lambda kv: kv[1], reverse=True)[:n]


# --- Counters (e.g. karate win tallies) --------------------------------------

def bump(game, amount=1):
    """Add `amount` to a running integer counter and save. Returns new total."""
    data = load()
    cur = data.get(game, 0)
    cur = int(cur) if isinstance(cur, (int, float)) else 0
    data[game] = cur + amount
    _save(data)
    return data[game]
