# bot/session_state.py

from dataclasses import dataclass, field
from typing import Any, Dict, List

from backend.models import Player, Team


@dataclass
class TeamStats:
    """Statistics for a team in a tournament."""

    team_name: str
    manager_id: int
    played: int = 0
    won: int = 0
    lost: int = 0
    tied: int = 0
    runs_for: int = 0
    runs_against: int = 0
    overs_faced: float = 0.0
    overs_bowled: float = 0.0
    net_run_rate: float = 0.0


@dataclass
class MatchInfo:
    """Information about a tournament match."""

    team_a_name: str
    team_b_name: str
    winner_name: str | None = None
    tied: bool = False
    team_a_score: str = ""
    team_b_score: str = ""
    match_type: str = "League"  # League, Semi-Final, Final


@dataclass
class GameSession:
    guild_id: int
    channel_id: int
    players: List[Player] = field(default_factory=list)
    auction_pool: List[Player] = field(default_factory=list)
    teams: List[Team] = field(default_factory=list)
    managers: List[int] = field(default_factory=list)  # discord user IDs
    team_names: List[str] = field(default_factory=list)  # Team names chosen by managers
    active: bool = False
    squad_size: int = 6
    owner_id: int | None = None  # organiser who ran /start_game

    # Tournament tracking
    tournament_mode: bool = False
    team_stats: Dict[str, TeamStats] = field(default_factory=dict)  # team_name -> stats
    match_history: List[MatchInfo] = field(default_factory=list)
    current_match: Dict[str, Any] = field(
        default_factory=dict
    )  # Current match being played
    tournament_stage: str = ""  # e.g., "League", "Semi-Final", "Final", "Completed"
    league_phase_complete: bool = False

    # League fixture tracking
    league_fixtures: List[Dict[str, str]] = field(
        default_factory=list
    )  # [{team_a, team_b}, ...]
    fixture_index: int = 0  # Current fixture index


_SESSIONS: Dict[int, GameSession] = {}


def get_session(guild_id: int, channel_id: int) -> GameSession:
    session = _SESSIONS.get(guild_id)
    if session is None:
        session = GameSession(guild_id=guild_id, channel_id=channel_id)
        _SESSIONS[guild_id] = session
    return session


def clear_session(guild_id: int) -> None:
    _SESSIONS.pop(guild_id, None)
