"""
Tournament update logic for the IPL Simulator.

Handles updating tournament standings and determining next fixtures.
"""

from typing import Any, Dict, List, Tuple

from backend.models import InningsResult


class MatchInfo:
    """Information about a tournament match."""

    def __init__(
        self,
        team_a_name: str,
        team_b_name: str,
        winner_name: str | None = None,
        tied: bool = False,
        team_a_score: str = "",
        team_b_score: str = "",
        match_type: str = "League",
    ):
        self.team_a_name = team_a_name
        self.team_b_name = team_b_name
        self.winner_name = winner_name
        self.tied = tied
        self.team_a_score = team_a_score
        self.team_b_score = team_b_score
        self.match_type = match_type


class TeamStats:
    """Statistics for a team in a tournament."""

    def __init__(
        self,
        team_name: str,
        manager_id: int,
        played: int = 0,
        won: int = 0,
        lost: int = 0,
        tied: int = 0,
        runs_for: int = 0,
        runs_against: int = 0,
        overs_faced: float = 0.0,
        overs_bowled: float = 0.0,
        net_run_rate: float = 0.0,
    ):
        self.team_name = team_name
        self.manager_id = manager_id
        self.played = played
        self.won = won
        self.lost = lost
        self.tied = tied
        self.runs_for = runs_for
        self.runs_against = runs_against
        self.overs_faced = overs_faced
        self.overs_bowled = overs_bowled
        self.net_run_rate = net_run_rate


def update_tournament_standings(
    team_stats: Dict[str, TeamStats],
    team_a_name: str,
    team_b_name: str,
    winner_name: str | None,
    team_a_score: str,
    team_b_score: str,
    tied: bool,
) -> None:
    """
    Update team standings after a match.

    Args:
        team_stats: Dictionary of team stats
        team_a_name: Name of team A
        team_b_name: Name of team B
        winner_name: Name of winning team (None if tied)
        team_a_score: Team A score (e.g., "150/5")
        team_b_score: Team B score (e.g., "145/8")
        tied: Whether the match was tied
    """
    # Parse runs from scores
    runs_a = int(team_a_score.split("/")[0]) if "/" in team_a_score else 0
    runs_b = int(team_b_score.split("/")[0]) if "/" in team_b_score else 0

    # Update team A stats
    if team_a_name in team_stats:
        stats_a = team_stats[team_a_name]
        stats_a.played += 1
        if tied or winner_name is None:
            stats_a.tied += 1
        elif winner_name == team_a_name:
            stats_a.won += 1
        else:
            stats_a.lost += 1

        stats_a.runs_for += runs_a
        stats_a.runs_against += runs_b

    # Update team B stats
    if team_b_name in team_stats:
        stats_b = team_stats[team_b_name]
        stats_b.played += 1
        if tied or winner_name is None:
            stats_b.tied += 1
        elif winner_name == team_b_name:
            stats_b.won += 1
        else:
            stats_b.lost += 1

        stats_b.runs_for += runs_b
        stats_b.runs_against += runs_a

    # Calculate NRR for all teams
    for stats in team_stats.values():
        if stats.played > 0:
            avg_runs_scored = stats.runs_for / stats.played
            avg_runs_conceded = stats.runs_against / stats.played
            stats.net_run_rate = avg_runs_scored - avg_runs_conceded


def check_league_phase_complete(
    match_history: List[MatchInfo],
    num_teams: int,
) -> bool:
    """
    Check if all league matches have been played.

    Args:
        match_history: List of completed matches
        num_teams: Number of teams in tournament

    Returns:
        True if all league matches are complete
    """
    total_league_matches = num_teams * (num_teams - 1) // 2
    league_matches_played = sum(1 for m in match_history if m.match_type == "League")
    return league_matches_played >= total_league_matches


def get_next_match_info(
    league_fixtures: List[Dict[str, str]],
    fixture_index: int,
    team_stats: Dict[str, TeamStats],
    league_phase_complete: bool,
    tournament_stage: str,
    num_teams: int,
) -> Tuple[str | None, bool]:
    """
    Get information about the next match in the tournament.

    Args:
        league_fixtures: List of league fixtures
        fixture_index: Current fixture index
        team_stats: Team statistics
        league_phase_complete: Whether league phase is complete
        tournament_stage: Current tournament stage
        num_teams: Number of teams

    Returns:
        Tuple of (next_match_info, tournament_complete)
    """
    if not league_phase_complete:
        if fixture_index < len(league_fixtures):
            fixture = league_fixtures[fixture_index]
            return f"League: {fixture['team_a']} vs {fixture['team_b']}", False
        else:
            # League complete, moving to knockout
            return None, False

    # Knockout phase
    if tournament_stage == "Completed":
        return None, True
    elif tournament_stage == "Final":
        return "🏆 FINAL", False
    elif tournament_stage == "Semi-Final":
        return "Semi-Final", False

    return None, False
