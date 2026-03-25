"""
CricDisco - IPL Auction & Match Simulator

Main entry point for the CLI game. Orchestrates the full game flow:
1. Load players from unified_players.json.
2. Get manager names from users.
3. Select auction pool.
4. Run the player auction.
5. Display team squads.
6. Simulate a match between two selected teams.
7. Print match result.
"""

from auction import display_squads, run_auction
from data import load_players, select_auction_pool
from match import simulate_match
from models import Team


def main() -> None:
    players = load_players("assets/unified_players.json")
    pool = select_auction_pool(players, n=10, method="top")

    num = int(input("How many managers (2–4)? "))
    manager_names = []
    for i in range(num):
        manager_names.append(
            input(f"Manager {i + 1} name: ").strip() or f"Manager {i + 1}"
        )

    run_auction(pool, manager_names, squad_size=3, starting_budget=20.0)


def get_manager_names() -> list[str]:
    """Prompt user for manager names.

    Asks for the number of managers (2-4), then prompts for
    each manager's name individually.

    Returns:
        List of manager names.

    TODO:
        - Prompt "How many managers (2-4)?".
        - Validate input is between 2 and 4.
        - Loop to collect each manager's name.
        - Return list of names.
    """
    # TODO: Implement manager name input
    pass


def select_match_teams(teams: list[Team]) -> tuple[Team, Team]:
    """Prompt user to select two teams for the match.

    Displays list of available teams with indices, then asks
    user to choose two teams (Team A and Team B).

    Args:
        teams: List of all teams from the auction.

    Returns:
        Tuple of (team_a, team_b) selected for the match.

    TODO:
        - Display teams with indices (e.g., "0: Team Rudra").
        - Prompt user to select Team A index.
        - Prompt user to select Team B index (must be different).
        - Validate selections are valid indices.
        - Return tuple of selected teams.
    """
    # TODO: Implement team selection for match
    pass


def print_match_result(result: "MatchResult", team_a: Team, team_b: Team) -> None:
    """Display the match result to the user.

    Prints a formatted summary of the match:
    - Team A's innings score (runs/wickets in overs).
    - Team B's innings score.
    - Result line with winner and margin.

    Args:
        result: MatchResult from simulate_match().
        team_a: First team (batted first).
        team_b: Second team (batted second).

    TODO:
        - Format and print Team A's score (e.g., "Team Rudra: 78/4 in 5 overs").
        - Format and print Team B's score.
        - Print result line (e.g., "Result: Team Rudra wins by 3 runs").
        - Handle tie case if winner is None.
    """
    # TODO: Implement match result display
    pass


if __name__ == "__main__":
    main()
