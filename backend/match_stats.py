"""
Match statistics calculation for the IPL Simulator.

Handles calculation of player stats, Man of the Match, and match results.
"""

from typing import Any, Dict, Optional

from backend.models import InningsResult, MatchResult


def compute_match_result(
    team_a_name: str,
    team_b_name: str,
    innings_a: InningsResult,
    innings_b: InningsResult,
    innings_a_perf: Dict[str, Any],
    innings_b_perf: Dict[str, Any],
) -> MatchResult:
    """
    Determine the result of a match.

    Args:
        team_a_name: Name of team A
        team_b_name: Name of team B
        innings_a: First innings result
        innings_b: Second innings result
        innings_a_perf: First innings performance data
        innings_b_perf: Second innings performance data

    Returns:
        MatchResult with winner, margin, and Man of the Match
    """
    # Decide winner + margin
    if innings_a.runs > innings_b.runs:
        winner = team_a_name
        margin = f"wins by {innings_a.runs - innings_b.runs} runs"
    elif innings_b.runs > innings_a.runs:
        wickets_left = 10 - innings_b.wickets
        wickets_left = max(wickets_left, 1)
        margin = f"wins by {wickets_left} wicket" + ("s" if wickets_left > 1 else "")
        winner = team_b_name
    else:
        winner = None
        margin = "match tied"

    # Calculate Man of the Match
    mom = calculate_man_of_the_match(
        innings_a_perf=innings_a_perf,
        innings_b_perf=innings_b_perf,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        winning_team=winner,
    )

    return MatchResult(
        team_a_result=innings_a,
        team_b_result=innings_b,
        winner=winner,
        margin=margin,
        man_of_the_match=mom,
    )


def calculate_man_of_the_match(
    innings_a_perf: Dict[str, Any],
    innings_b_perf: Dict[str, Any],
    team_a_name: str,
    team_b_name: str,
    winning_team: Optional[str],
) -> Optional[str]:
    """
    Calculate Man of the Match based on runs scored and wickets taken.

    Scoring:
    - 1 point per run scored
    - 20 points per wicket taken
    - 10 point bonus if in winning team

    Args:
        innings_a_perf: First innings performance data
        innings_b_perf: Second innings performance data
        team_a_name: Name of team A
        team_b_name: Name of team B
        winning_team: Name of winning team (None if tied)

    Returns:
        Name of Man of the Match, or None
    """
    player_scores: Dict[str, int] = {}
    player_teams: Dict[str, str] = {}

    # Innings 1: team_a batting, team_b bowling
    for batter_name, runs in innings_a_perf.get("batter_runs", {}).items():
        player_scores[batter_name] = player_scores.get(batter_name, 0) + runs
        player_teams[batter_name] = team_a_name

    for bowler_name, wickets in innings_a_perf.get("bowler_wickets", {}).items():
        player_scores[bowler_name] = player_scores.get(bowler_name, 0) + (wickets * 20)
        player_teams[bowler_name] = team_b_name

    # Innings 2: team_b batting, team_a bowling
    for batter_name, runs in innings_b_perf.get("batter_runs", {}).items():
        player_scores[batter_name] = player_scores.get(batter_name, 0) + runs
        player_teams[batter_name] = team_b_name

    for bowler_name, wickets in innings_b_perf.get("bowler_wickets", {}).items():
        player_scores[bowler_name] = player_scores.get(bowler_name, 0) + (wickets * 20)
        player_teams[bowler_name] = team_a_name

    if not player_scores:
        return None

    # Find top scorer with winning team bonus
    if winning_team is not None:
        best_player = None
        best_score = -1
        for player, score in player_scores.items():
            if player_teams.get(player) == winning_team:
                bonus_score = score + 10
            else:
                bonus_score = score
            if bonus_score > best_score:
                best_score = bonus_score
                best_player = player
        return best_player

    return max(player_scores, key=player_scores.get)


def calculate_match_stats(
    innings_a_perf: Dict[str, Any],
    innings_b_perf: Dict[str, Any],
    team_a_name: str,
    team_b_name: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate comprehensive match statistics for all players.

    Args:
        innings_a_perf: First innings performance data
        innings_b_perf: Second innings performance data
        team_a_name: Name of team A
        team_b_name: Name of team B

    Returns:
        Dictionary mapping player names to their stats
    """
    player_stats: Dict[str, Dict[str, Any]] = {}

    # Process both innings
    for innings_perf, batting_team, bowling_team in [
        (innings_a_perf, team_a_name, team_b_name),
        (innings_b_perf, team_b_name, team_a_name),
    ]:
        # Batting stats
        for player_name in innings_perf.get("batter_runs", {}).keys():
            if player_name not in player_stats:
                player_stats[player_name] = {
                    "team": batting_team,
                    "batting": {
                        "runs": 0,
                        "balls_faced": 0,
                        "fours": 0,
                        "sixes": 0,
                        "strike_rate": 0.0,
                        "not_out": True,
                    },
                    "bowling": {
                        "overs": 0.0,
                        "runs_conceded": 0,
                        "wickets": 0,
                        "economy": 0.0,
                        "balls": 0,
                    },
                }
            player_stats[player_name]["batting"]["runs"] += innings_perf[
                "batter_runs"
            ].get(player_name, 0)
            player_stats[player_name]["batting"]["balls_faced"] += innings_perf.get(
                "batter_balls", {}
            ).get(player_name, 0)
            player_stats[player_name]["batting"]["fours"] += innings_perf.get(
                "batter_fours", {}
            ).get(player_name, 0)
            player_stats[player_name]["batting"]["sixes"] += innings_perf.get(
                "batter_sixes", {}
            ).get(player_name, 0)

        # Bowling stats
        for player_name in innings_perf.get("bowler_wickets", {}).keys():
            if player_name not in player_stats:
                player_stats[player_name] = {
                    "team": bowling_team,
                    "batting": {
                        "runs": 0,
                        "balls_faced": 0,
                        "fours": 0,
                        "sixes": 0,
                        "strike_rate": 0.0,
                        "not_out": True,
                    },
                    "bowling": {
                        "overs": 0.0,
                        "runs_conceded": 0,
                        "wickets": 0,
                        "economy": 0.0,
                        "balls": 0,
                    },
                }
            player_stats[player_name]["bowling"]["wickets"] += innings_perf[
                "bowler_wickets"
            ].get(player_name, 0)
            player_stats[player_name]["bowling"]["balls"] = innings_perf.get(
                "bowler_balls", {}
            ).get(player_name, 0)
            player_stats[player_name]["bowling"]["runs_conceded"] += innings_perf.get(
                "bowler_runs_conceded", {}
            ).get(player_name, 0)

    # Calculate derived stats
    for stats in player_stats.values():
        # Batting strike rate
        if stats["batting"]["balls_faced"] > 0:
            stats["batting"]["strike_rate"] = (
                stats["batting"]["runs"] / stats["batting"]["balls_faced"]
            ) * 100

        # Bowling economy and overs
        balls_bowled = stats["bowling"].get("balls", 0)
        if balls_bowled > 0:
            stats["bowling"]["overs"] = balls_bowled / 6
            stats["bowling"]["economy"] = (
                stats["bowling"]["runs_conceded"] / stats["bowling"]["overs"]
            )

    return player_stats
