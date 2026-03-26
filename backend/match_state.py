"""
Match state management for the IPL Simulator.

Handles creation and manipulation of innings state.
"""

from typing import Any, Dict, List

from backend.models import Player


def build_innings_state(
    innings_num: int,
    batting_team_name: str,
    bowling_team_name: str,
    batting_xi: List[Player],
    bowling_xi: List[Player],
    overs: int,
    target: int | None = None,
) -> Dict[str, Any]:
    """
    Create initial state for an innings.

    Args:
        innings_num: 1 or 2
        batting_team_name: Name of batting team
        bowling_team_name: Name of bowling team
        batting_xi: List of 11 batting players
        bowling_xi: List of 11 bowling players
        overs: Number of overs in the match
        target: Target to chase (None for first innings)

    Returns:
        Dictionary containing innings state
    """
    batting_order = get_batting_order(batting_xi)
    bowling_rotation = get_bowling_rotation(bowling_xi)

    return {
        "innings_num": innings_num,
        "overs": overs,
        "runs": 0,
        "wickets": 0,
        "balls": 0,
        "current_over": 0,
        "batting_team_name": batting_team_name,
        "bowling_team_name": bowling_team_name,
        "batting_order": batting_order,
        "bowling_rotation": bowling_rotation,
        "striker_index": 0,
        "non_striker_index": 1 if len(batting_order) > 1 else 0,
        "completed": False,
        "ball_log": [],
        "target": target,
        "current_bowler": None,
        # Player performance tracking
        "batter_runs": {},
        "batter_balls": {},
        "batter_fours": {},
        "batter_sixes": {},
        "bowler_wickets": {},
        "bowler_balls": {},
        "bowler_runs_conceded": {},
    }


def get_batting_order(players: List[Player]) -> List[Player]:
    """Determine the batting order for a team (sorted by batting rating)."""
    return sorted(
        players,
        key=lambda p: (p.batting_rating, p.overall_rating),
        reverse=True,
    )


def get_bowling_rotation(players: List[Player]) -> List[Player]:
    """
    Determine the bowling rotation for a team.

    Returns top 4-5 bowlers sorted by bowling rating.
    """
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


def simulate_over(
    state: Dict[str, Any],
    simulate_ball_func,
) -> Dict[str, Any]:
    """
    Simulate one over of cricket.

    Args:
        state: Current innings state
        simulate_ball_func: Function to simulate a single ball (batter, bowler) -> dict

    Returns:
        Updated state with over summary
    """
    batting_order = state["batting_order"]
    bowling_rotation = state["bowling_rotation"]

    over_index = state["current_over"]
    bowler = bowling_rotation[over_index % len(bowling_rotation)]
    state["current_bowler"] = bowler
    over_balls: List[str] = []

    runs = state["runs"]
    wickets = state["wickets"]
    balls = state["balls"]
    striker_index = state["striker_index"]
    non_striker_index = state["non_striker_index"]
    target = state["target"]

    for _ in range(6):
        if wickets >= len(batting_order) - 1:
            break
        if target is not None and runs >= target:
            break

        batter = batting_order[striker_index]
        outcome = simulate_ball_func(batter, bowler)

        runs += outcome["runs"]
        balls += 1

        # Track batter runs with detailed stats
        batter_name = batter.name
        if batter_name not in state["batter_runs"]:
            state["batter_runs"][batter_name] = 0
            state["batter_balls"][batter_name] = 0
            state["batter_fours"][batter_name] = 0
            state["batter_sixes"][batter_name] = 0

        state["batter_runs"][batter_name] += outcome["runs"]
        state["batter_balls"][batter_name] += 1

        if outcome["runs"] == 4:
            state["batter_fours"][batter_name] += 1
        elif outcome["runs"] == 6:
            state["batter_sixes"][batter_name] += 1

        if outcome["is_wicket"]:
            wickets += 1
            over_balls.append("W")
            # Track bowler wickets with detailed stats
            bowler_name = bowler.name
            if bowler_name not in state["bowler_wickets"]:
                state["bowler_wickets"][bowler_name] = 0
                state["bowler_balls"][bowler_name] = 0
                state["bowler_runs_conceded"][bowler_name] = 0

            state["bowler_wickets"][bowler_name] += 1
            state["bowler_balls"][bowler_name] += 1
            state["bowler_runs_conceded"][bowler_name] += outcome["runs"]

            next_batter_index = wickets + 1
            if next_batter_index < len(batting_order):
                striker_index = next_batter_index
            else:
                break
        else:
            over_balls.append(str(outcome["runs"]))
            # Track bowler balls and runs even for non-wicket balls
            bowler_name = bowler.name
            if bowler_name not in state["bowler_balls"]:
                state["bowler_balls"][bowler_name] = 0
                state["bowler_runs_conceded"][bowler_name] = 0

            state["bowler_balls"][bowler_name] += 1
            state["bowler_runs_conceded"][bowler_name] += outcome["runs"]

            if outcome["runs"] % 2 == 1:
                striker_index, non_striker_index = (
                    non_striker_index,
                    striker_index,
                )

        if target is not None and runs >= target:
            break

    # Swap strike at end of over
    striker_index, non_striker_index = non_striker_index, striker_index

    state["runs"] = runs
    state["wickets"] = wickets
    state["balls"] = balls
    state["striker_index"] = striker_index
    state["non_striker_index"] = non_striker_index
    state["current_over"] = over_index + 1

    # Check if innings is complete
    all_out = wickets >= len(batting_order) - 1
    innings_done = (over_index + 1) >= state["overs"] or all_out
    chased = target is not None and runs >= target

    if innings_done or chased:
        state["completed"] = True

    return {
        "over_balls": over_balls,
        "over_str": ".".join(over_balls) if over_balls else "...",
        "runs_in_over": sum(int(b) for b in over_balls if b.isdigit()),
        "wickets_in_over": over_balls.count("W"),
    }


def finalize_innings(
    state: Dict[str, Any],
    InningsResult_class,
) -> tuple[Any, Dict[str, Any]]:
    """
    Finalize an innings and create performance data.

    Args:
        state: Completed innings state
        InningsResult_class: InningsResult class to instantiate

    Returns:
        Tuple of (InningsResult, innings_perf dict)
    """
    innings_res = InningsResult_class(
        runs=state["runs"],
        wickets=state["wickets"],
        balls=state["balls"],
        ball_log=state["ball_log"],
    )

    innings_perf = {
        "result": innings_res,
        "batter_runs": dict(state["batter_runs"]),
        "batter_balls": dict(state.get("batter_balls", {})),
        "batter_fours": dict(state.get("batter_fours", {})),
        "batter_sixes": dict(state.get("batter_sixes", {})),
        "bowler_wickets": dict(state["bowler_wickets"]),
        "bowler_balls": dict(state.get("bowler_balls", {})),
        "bowler_runs_conceded": dict(state.get("bowler_runs_conceded", {})),
    }

    return innings_res, innings_perf
