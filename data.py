"""
Data loading and filtering utilities for the IPL Simulator.

Handles loading players from unified_players.json and selecting
the auction pool subset.
"""

import json
import random
from pathlib import Path

from models import Player


def load_players(path: str | Path) -> list[Player]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))

    players: list[Player] = []

    for idx, entry in enumerate(raw):
        name = entry.get("full_name", f"player {idx}")
        role = entry.get("role", "bat")

        ratings = entry.get("calculated_ratings", {}) or {}
        batting_rating = float(ratings.get("batting", 0))
        bowling_rating = float(ratings.get("bowling", 0))
        overall_rating = float(ratings.get("overall", 0))

        base_price = float(entry.get("final_base_price_crore", 0.0))

        players.append(
            Player(
                id=idx,
                name=name,
                role=role,
                batting_rating=batting_rating,
                bowling_rating=bowling_rating,
                overall_rating=overall_rating,
                base_price=base_price,
            )
        )

    return players


def select_auction_pool(
    players: list[Player], n: int = 30, method: str = "top"
) -> list[Player]:

    if not players:
        return []

    n = min(n, len(players))

    if method == "random":
        return random.sample(players, n)

    sorted_players = sorted(players, key=lambda p: p.overall_rating, reverse=True)

    return sorted_players[:n]
