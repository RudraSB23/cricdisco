# bot/session_state.py

from dataclasses import dataclass, field
from typing import Dict, List

from backend.models import Player, Team


@dataclass
class GameSession:
    guild_id: int
    channel_id: int
    players: List[Player] = field(default_factory=list)
    auction_pool: List[Player] = field(default_factory=list)
    teams: List[Team] = field(default_factory=list)
    managers: List[int] = field(default_factory=list)  # discord user IDs
    manager_names: List[str] = field(default_factory=list)
    active: bool = False
    squad_size: int = 6


_SESSIONS: Dict[int, GameSession] = {}  # guild_id -> session


def get_session(guild_id: int, channel_id: int) -> GameSession:
    session = _SESSIONS.get(guild_id)
    if session is None:
        session = GameSession(guild_id=guild_id, channel_id=channel_id)
        _SESSIONS[guild_id] = session
    return session


def clear_session(guild_id: int) -> None:
    _SESSIONS.pop(guild_id, None)
