"""
Data models for the IPL Auction & Match Simulator.

Defines core dataclasses: Player, Team, GameState, InningsResult, MatchResult.
"""

from dataclasses import dataclass, field


@dataclass
class Player:
    """Represents a cricket player with ratings and base price.

    Attributes:
        id: Unique identifier for the player (index or UUID).
        name: Player's full name.
        role: Player role - one of "bat", "bowl", "ar", "wk".
        batting_rating: Batting strength rating (0-100).
        bowling_rating: Bowling strength rating (0-100).
        overall_rating: Overall strength rating (0-100).
        base_price: Base auction price in crore.
    """

    id: int
    name: str
    role: str
    batting_rating: float
    bowling_rating: float
    overall_rating: float
    base_price: float


@dataclass
class Team:
    """Represents a team managed by a human manager.

    Attributes:
        manager_name: Name of the human manager.
        budget: Remaining budget in crore (optional, can be very large).
        players: List of players drafted to this team.
    """

    manager_name: str
    budget: float
    players: list[Player] = field(default_factory=list)


@dataclass
class GameState:
    """Represents the overall game/session state.

    Attributes:
        teams: List of all teams in the session.
        auction_pool: List of players available for auction.
        sold_players: Mapping of player_id to manager_name for sold players.
    """

    teams: list[Team]
    auction_pool: list[Player]
    sold_players: dict[int, str] = field(default_factory=dict)


@dataclass
class InningsResult:
    """Result of a single innings in a match.

    Attributes:
        runs: Total runs scored.
        wickets: Total wickets lost.
        balls: Total balls bowled.
        ball_log: List of ball-by-ball outcome descriptions.
    """

    runs: int
    wickets: int
    balls: int
    ball_log: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """Result of a complete match between two teams.

    Attributes:
        team_a_result: Innings result for team A.
        team_b_result: Innings result for team B.
        winner: Name of the winning team (None if tie).
        margin: Description of winning margin (e.g., "by 3 runs").
    """

    team_a_result: InningsResult
    team_b_result: InningsResult
    winner: str | None
    margin: str
