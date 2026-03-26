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

from auction import display_squads, quick_assign_players, run_auction
from data import load_players, select_auction_pool
from match import simulate_match
from models import MatchResult, Team


def main() -> None:
    # 1. Load players
    players = load_players("assets/unified_players.json")
    print(f"Loaded {len(players)} players.")

    # 2. Get manager names
    manager_names = get_manager_names()

    # 3. Select auction pool (top N by overall for now)
    pool = select_auction_pool(players, n=30, method="top")

    # 4. Run the player auction
    # teams = run_auction(
    # players=pool,
    # manager_names=manager_names,
    # squad_size=6,
    # starting_budget=20.0,
    # )

    teams = quick_assign_players(
        players=pool,
        manager_names=manager_names,
        squad_size=6,
        starting_budget=20.0,
    )

    # 5. Display team squads (also done at end of run_auction, but fine to repeat)
    print("\nFinal squads after auction:\n")
    display_squads(teams)

    # 6. Select two teams for the match
    team_a, team_b = select_match_teams(teams)

    # 7. Simulate a match between the selected teams
    result = simulate_match(team_a, team_b, overs=5)

    # 8. Print match result
    print_match_result(result, team_a, team_b)


def get_manager_names() -> list[str]:
    """Prompt user for manager names (2–4), with basic validation."""
    while True:
        try:
            num = int(input("How many managers (2–4)? "))
        except ValueError:
            print("Please enter a number.")
            continue

        if 2 <= num <= 4:
            break

        print("Please choose between 2 and 4 managers.")

    manager_names: list[str] = []
    for i in range(num):
        name = input(f"Manager {i + 1} name: ").strip() or f"Manager {i + 1}"
        manager_names.append(name)

    return manager_names


def select_match_teams(teams: list[Team]) -> tuple[Team, Team]:
    """Prompt user to select two teams for the match."""
    if len(teams) < 2:
        raise ValueError("Need at least two teams to play a match.")

    print("\nAvailable teams for the match:")
    for idx, team in enumerate(teams):
        print(f"{idx}: {team.manager_name} (players: {len(team.players)})")

    # Select Team A
    while True:
        try:
            a_idx = int(input("Select Team A index: "))
            if 0 <= a_idx < len(teams):
                break
            print("Invalid index. Try again.")
        except ValueError:
            print("Please enter a valid number.")

    # Select Team B (must be different)
    while True:
        try:
            b_idx = int(input("Select Team B index (must be different): "))
            if 0 <= b_idx < len(teams) and b_idx != a_idx:
                break
            print("Invalid index or same as Team A. Try again.")
        except ValueError:
            print("Please enter a valid number.")

    team_a = teams[a_idx]
    team_b = teams[b_idx]

    print(
        f"\nMatch set: {team_a.manager_name} vs {team_b.manager_name} "
        "(5 overs per side)\n"
    )

    return team_a, team_b


def print_match_result(result: MatchResult, team_a: Team, team_b: Team) -> None:
    """Display the match result to the user."""
    overs_a = result.team_a_result.balls / 6
    overs_b = result.team_b_result.balls / 6

    print("\n=== Match Summary ===\n")

    # Team A innings
    print(
        f"{team_a.manager_name}: "
        f"{result.team_a_result.runs}/{result.team_a_result.wickets} "
        f"in {overs_a:.1f} overs"
    )

    # Team B innings
    print(
        f"{team_b.manager_name}: "
        f"{result.team_b_result.runs}/{result.team_b_result.wickets} "
        f"in {overs_b:.1f} overs"
    )

    # Winner / result line
    if result.winner is None:
        print("\nResult: Match tied.")
    else:
        print(f"\nResult: {result.winner} {result.margin}.")


if __name__ == "__main__":
    main()
