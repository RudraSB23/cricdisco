"""
Match simulation logic for the IPL Simulator.

Handles ball-by-ball simulation of a 5-over match between two teams.
"""

import random
from typing import Dict, List

from backend.models import InningsResult, MatchResult, Player, Team


def simulate_ball(batter: Player, bowler: Player) -> Dict:
    """Simulate a single ball delivery and determine outcome."""
    # Base probabilities
    probs = {
        "dot": 0.25,
        "1": 0.30,
        "2": 0.10,
        "4": 0.12,
        "6": 0.08,
        "wicket": 0.15,
    }

    # Advantage adjustment
    advantage = batter.batting_rating - bowler.bowling_rating

    # Scale factor: each 20 points of advantage shifts probabilities a bit
    factor = max(min(advantage / 20.0, 2.0), -2.0)

    # Adjust: positive advantage -> more boundaries, fewer wickets
    probs["4"] += 0.03 * factor
    probs["6"] += 0.02 * factor
    probs["wicket"] -= 0.03 * factor

    # Clamp and normalize
    values = ["dot", "1", "2", "4", "6", "wicket"]
    raw = [max(0.0, probs[k]) for k in values]
    total = sum(raw) or 1.0
    norm = [x / total for x in raw]

    r = random.random()
    cumulative = 0.0
    outcome_key = "dot"
    for key, p in zip(values, norm):
        cumulative += p
        if r <= cumulative:
            outcome_key = key
            break

    if outcome_key == "wicket":
        return {"runs": 0, "is_wicket": True, "description": "W"}

    run_map = {"dot": 0, "1": 1, "2": 2, "4": 4, "6": 6}
    runs = run_map[outcome_key]

    if runs == 0:
        desc = "0"
    elif runs == 1:
        desc = "1 run"
    else:
        desc = str(runs)

    return {"runs": runs, "is_wicket": False, "description": desc}


def select_playing_xi(team: Team, n: int = 11) -> List[Player]:
    """Select the best playing XI from a team's squad."""
    if len(team.players) <= n:
        return list(team.players)
    sorted_players = sorted(team.players, key=lambda p: p.overall_rating, reverse=True)
    return sorted_players[:n]


def get_batting_order(players: List[Player]) -> List[Player]:
    """Determine the batting order for a team."""
    return sorted(
        players,
        key=lambda p: (p.batting_rating, p.overall_rating),
        reverse=True,
    )


def get_bowling_rotation(players: List[Player]) -> List[Player]:
    """Determine the bowling rotation for a team."""
    # Filter to those who can bowl at all
    bowlers = [p for p in players if p.bowling_rating > 0]

    if not bowlers:
        # If no one has bowling rating, fall back to everyone
        bowlers = list(players)

    bowlers = sorted(
        bowlers,
        key=lambda p: p.bowling_rating,
        reverse=True,
    )

    # Use top 4–5, or all if fewer
    if len(bowlers) > 5:
        bowlers = bowlers[:5]

    return bowlers


def simulate_match(team_a: Team, team_b: Team, overs: int = 5) -> MatchResult:
    """Simulate a complete match between two teams."""
    # 1. Select playing XIs (currently just for ordering)
    _ = select_playing_xi(team_a)
    _ = select_playing_xi(team_b)

    # 2. First innings: team_a bats
    innings_a = simulate_innings(
        batting_team=team_a,
        bowling_team=team_b,
        overs=overs,
        target=None,
    )

    target = innings_a.runs + 1

    # 3. Second innings: team_b chases
    innings_b = simulate_innings(
        batting_team=team_b,
        bowling_team=team_a,
        overs=overs,
        target=target,
    )

    # 4. Determine winner and margin
    if innings_a.runs > innings_b.runs:
        winner = team_a.manager_name
        margin = f"wins by {innings_a.runs - innings_b.runs} runs"
    elif innings_b.runs > innings_a.runs:
        wickets_left = 10 - innings_b.wickets
        margin = f"wins by {max(wickets_left, 1)} wicket" + (
            "s" if wickets_left > 1 else ""
        )
        winner = team_b.manager_name
    else:
        winner = None
        margin = "match tied"

    return MatchResult(
        team_a_result=innings_a,
        team_b_result=innings_b,
        winner=winner,
        margin=margin,
    )


def simulate_innings(
    batting_team: Team, bowling_team: Team, overs: int = 5, target: int | None = None
) -> InningsResult:
    """Simulate a single innings of a match."""
    batting_xi = select_playing_xi(batting_team)
    bowling_xi = select_playing_xi(bowling_team)

    batting_order = get_batting_order(batting_xi)
    bowling_rotation = get_bowling_rotation(bowling_xi)

    runs = 0
    wickets = 0
    balls = 0
    ball_log: list[str] = []

    striker_index = 0
    non_striker_index = 1 if len(batting_order) > 1 else 0

    for over in range(overs):
        bowler = bowling_rotation[over % len(bowling_rotation)]
        over_log: list[str] = []

        over_log.append(
            f"Over {over + 1}: {bowler.name} to {batting_order[striker_index].name}"
        )

        for ball_in_over in range(6):
            if wickets >= len(batting_order) - 1:
                break  # all out

            if target is not None and runs >= target:
                break  # target chased

            batter = batting_order[striker_index]
            outcome = simulate_ball(batter, bowler)

            runs += outcome["runs"]
            balls += 1

            desc_prefix = f"{over + 1}.{ball_in_over + 1}: "
            over_log.append(desc_prefix + outcome["description"])

            if outcome["is_wicket"]:
                wickets += 1
                next_batter_index = wickets + 1
                if next_batter_index < len(batting_order):
                    striker_index = next_batter_index
                else:
                    break
            else:
                # Rotate strike on odd runs
                if outcome["runs"] % 2 == 1:
                    striker_index, non_striker_index = (
                        non_striker_index,
                        striker_index,
                    )

            if target is not None and runs >= target:
                break

        over_log.append(
            f"End of over {over + 1}: {runs}/{wickets} "
            f"(Target: {target if target is not None else '-'})"
        )

        ball_log.extend(over_log)

        if wickets >= len(batting_order) - 1:
            break
        if target is not None and runs >= target:
            break

        # Swap strike at end of over
        striker_index, non_striker_index = non_striker_index, striker_index

    return InningsResult(runs=runs, wickets=wickets, balls=balls, ball_log=ball_log)
