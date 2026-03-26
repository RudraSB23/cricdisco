"""
Player statistics calculation for the IPL Simulator.

Handles calculation of batting and bowling statistics from match data.
"""

from typing import Any, Dict, List, Optional


def calculate_player_stats(
    innings_a_perf: Dict[str, Any],
    innings_b_perf: Dict[str, Any],
    team_a_name: str,
    team_b_name: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate comprehensive player statistics from both innings.

    Returns a dictionary with player names as keys and their stats as values.
    """
    player_stats: Dict[str, Dict[str, Any]] = {}

    # Process innings 1: team_a batting, team_b bowling
    _process_innings_stats(
        innings_perf=innings_a_perf,
        batting_team=team_a_name,
        bowling_team=team_b_name,
        player_stats=player_stats,
        is_batting_innings=True,
    )

    # Process innings 2: team_b batting, team_a bowling
    _process_innings_stats(
        innings_perf=innings_b_perf,
        batting_team=team_b_name,
        bowling_team=team_a_name,
        player_stats=player_stats,
        is_batting_innings=True,
    )

    return player_stats


def _process_innings_stats(
    innings_perf: Dict[str, Any],
    batting_team: str,
    bowling_team: str,
    player_stats: Dict[str, Dict[str, Any]],
    is_batting_innings: bool = True,
) -> None:
    """Process statistics from a single innings."""
    ball_log = innings_perf["result"].ball_log

    # Track individual player details from ball log
    batter_details: Dict[str, Dict[str, int]] = {}  # name -> {runs, balls, 4s, 6s}
    bowler_details: Dict[
        str, Dict[str, int]
    ] = {}  # name -> {balls, runs_conceded, wickets}

    # Parse ball log to extract detailed stats
    current_bowler: Optional[str] = None

    for log_entry in ball_log:
        # Ball log format: "Over X: Bowler to Striker" or "X.X: outcome"
        if log_entry.startswith("Over "):
            # Extract bowler name from "Over X: Bowler to Striker"
            parts = log_entry.split(":")
            if len(parts) >= 2:
                over_details = parts[1].strip()
                if " to " in over_details:
                    bowler_part = over_details.split(" to ")[0].strip()
                    current_bowler = bowler_part
                    if current_bowler not in bowler_details:
                        bowler_details[current_bowler] = {
                            "balls": 0,
                            "runs_conceded": 0,
                            "wickets": 0,
                        }
            continue

        if current_bowler and (log_entry[0].isdigit() or log_entry.startswith("W")):
            # This is a ball outcome
            bowler_details[current_bowler]["balls"] += 1

            if log_entry.startswith("W"):
                bowler_details[current_bowler]["wickets"] += 1
            elif log_entry[0].isdigit():
                # Extract runs from the entry
                runs = int(log_entry[0])
                bowler_details[current_bowler]["runs_conceded"] += runs

    # Store batting stats
    for player_name, runs in innings_perf.get("batter_runs", {}).items():
        if player_name not in player_stats:
            player_stats[player_name] = {
                "team": batting_team,
                "role": "batter",
                "batting": {
                    "runs": 0,
                    "balls_faced": 0,
                    "fours": 0,
                    "sixes": 0,
                    "strike_rate": 0.0,
                },
                "bowling": {
                    "overs": 0.0,
                    "runs_conceded": 0,
                    "wickets": 0,
                    "economy": 0.0,
                },
            }
        player_stats[player_name]["batting"]["runs"] += runs

    # Store bowling stats
    for player_name, wickets in innings_perf.get("bowler_wickets", {}).items():
        if player_name not in player_stats:
            player_stats[player_name] = {
                "team": bowling_team,
                "role": "bowler",
                "batting": {
                    "runs": 0,
                    "balls_faced": 0,
                    "fours": 0,
                    "sixes": 0,
                    "strike_rate": 0.0,
                },
                "bowling": {
                    "overs": 0.0,
                    "runs_conceded": 0,
                    "wickets": 0,
                    "economy": 0.0,
                },
            }
        player_stats[player_name]["bowling"]["wickets"] += wickets

    # Add bowling details from parsed log
    for bowler_name, details in bowler_details.items():
        if bowler_name not in player_stats:
            player_stats[bowler_name] = {
                "team": bowling_team,
                "role": "bowler",
                "batting": {
                    "runs": 0,
                    "balls_faced": 0,
                    "fours": 0,
                    "sixes": 0,
                    "strike_rate": 0.0,
                },
                "bowling": {
                    "overs": 0.0,
                    "runs_conceded": 0,
                    "wickets": 0,
                    "economy": 0.0,
                },
            }
        player_stats[bowler_name]["bowling"]["balls"] = details["balls"]
        player_stats[bowler_name]["bowling"]["runs_conceded"] = details["runs_conceded"]
        player_stats[bowler_name]["bowling"]["wickets"] = details["wickets"]

    # Calculate derived stats
    for player_name, stats in player_stats.items():
        # Batting strike rate
        if stats["batting"]["balls_faced"] > 0:
            stats["batting"]["strike_rate"] = (
                stats["batting"]["runs"] / stats["batting"]["balls_faced"]
            ) * 100

        # Bowling economy
        if stats["bowling"]["balls"] > 0:
            overs_bowled = stats["bowling"]["balls"] / 6
            stats["bowling"]["overs"] = overs_bowled
            stats["bowling"]["economy"] = (
                stats["bowling"]["runs_conceded"] / overs_bowled
            )


def get_top_performers(
    player_stats: Dict[str, Dict[str, Any]],
    top_n: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get top performers in different categories.

    Returns top batters (by runs) and top bowlers (by wickets).
    """
    # Sort by runs
    batters = [
        {
            "name": name,
            "team": stats["team"],
            "runs": stats["batting"]["runs"],
            "strike_rate": stats["batting"]["strike_rate"],
        }
        for name, stats in player_stats.items()
        if stats["batting"]["runs"] > 0
    ]
    batters.sort(key=lambda x: x["runs"], reverse=True)

    # Sort by wickets
    bowlers = [
        {
            "name": name,
            "team": stats["team"],
            "wickets": stats["bowling"]["wickets"],
            "economy": stats["bowling"]["economy"],
            "overs": stats["bowling"]["overs"],
        }
        for name, stats in player_stats.items()
        if stats["bowling"]["wickets"] > 0
    ]
    bowlers.sort(key=lambda x: x["wickets"], reverse=True)

    return {
        "top_batters": batters[:top_n],
        "top_bowlers": bowlers[:top_n],
    }


def format_stats_embed(
    player_stats: Dict[str, Dict[str, Any]],
    team_a_name: str,
    team_b_name: str,
) -> str:
    """Format player statistics as a readable string for Discord embed."""
    lines: List[str] = []

    # Group players by team
    team_a_players = {
        name: stats
        for name, stats in player_stats.items()
        if stats["team"] == team_a_name
    }
    team_b_players = {
        name: stats
        for name, stats in player_stats.items()
        if stats["team"] == team_b_name
    }

    # Format Team A stats
    lines.append(f"**🏏 {team_a_name}**\n")
    lines.append("*Batting:*")
    for name, stats in sorted(
        team_a_players.items(),
        key=lambda x: x[1]["batting"]["runs"],
        reverse=True,
    ):
        bat = stats["batting"]
        if bat["runs"] > 0:
            lines.append(
                f"• **{name}**: {bat['runs']} runs (SR: {bat['strike_rate']:.1f})"
            )

    lines.append("\n*Bowling:*")
    for name, stats in sorted(
        team_a_players.items(),
        key=lambda x: x[1]["bowling"]["wickets"],
        reverse=True,
    ):
        bowl = stats["bowling"]
        if bowl["wickets"] > 0:
            lines.append(
                f"• **{name}**: {bowl['wickets']} wickets "
                f"in {bowl['overs']:.1f} overs (Econ: {bowl['economy']:.1f})"
            )

    lines.append("")

    # Format Team B stats
    lines.append(f"**🏏 {team_b_name}**\n")
    lines.append("*Batting:*")
    for name, stats in sorted(
        team_b_players.items(),
        key=lambda x: x[1]["batting"]["runs"],
        reverse=True,
    ):
        bat = stats["batting"]
        if bat["runs"] > 0:
            lines.append(
                f"• **{name}**: {bat['runs']} runs (SR: {bat['strike_rate']:.1f})"
            )

    lines.append("\n*Bowling:*")
    for name, stats in sorted(
        team_b_players.items(),
        key=lambda x: x[1]["bowling"]["wickets"],
        reverse=True,
    ):
        bowl = stats["bowling"]
        if bowl["wickets"] > 0:
            lines.append(
                f"• **{name}**: {bowl['wickets']} wickets "
                f"in {bowl['overs']:.1f} overs (Econ: {bowl['economy']:.1f})"
            )

    return "\n".join(lines)
