"""
Auction logic for the IPL Simulator.

Handles the player auction phase where managers bid on players
to build their teams.
"""

from typing import Set

from backend.models import Player, Team


def run_auction(
    players: list[Player],
    manager_names: list[str],
    squad_size: int = 6,
    starting_budget: float = 100.0,
) -> list[Team]:

    teams: list[Team] = [
        Team(manager_name=name, budget=starting_budget) for name in manager_names
    ]

    for player in players:
        if all(len(team.players) >= squad_size for team in teams):
            print("\nAll teams have reached the squad size. AUCTION ENDED")
            break

        active_managers: Set[str] = {
            t.manager_name for t in teams if len(t.players) < squad_size
        }

        winner_name, final_price = auction_player(player, teams, active_managers)

        if not winner_name:
            print(f"NO BIDS for {player.name}. PLAYER UNSOLD")
            continue

        for team in teams:
            if team.manager_name == winner_name:
                team.players.append(player)
                team.budget -= final_price
                print(
                    f"SOLD: {player.name} to {team.manager_name} "
                    f"for {final_price} Cr. (Budget left: {team.budget:.2f} Cr)\n"
                )
                break

    print("\n=== Auction complete! ===\n")
    display_squads(teams)
    return teams


def auction_player(
    player: Player, teams: list[Team], active_managers: set[str]
) -> tuple[str | None, float]:

    print("=" * 80)
    print(
        f"Auctioning: {player.name} | Role: {player.role.upper()} | "
        f"Rating: {player.overall_rating} | Base: {player.base_price} Cr"
    )
    print("=" * 80)

    current_price = player.base_price
    current_winner: str | None = None
    opened = False  # has anyone placed a valid bid yet?

    # Turn-based loop until we have a winner or everyone passes
    while active_managers:
        for team in teams:
            if team.manager_name not in active_managers:
                continue

            print(f"\nCurrent price: {current_price} Cr")
            print(
                f"{team.manager_name}'s turn "
                f"(budget: {team.budget:.2f} Cr, 'p' to pass): ",
                end="",
            )
            raw = input().strip().lower()

            if raw in {"p", "pass", ""}:
                print(f"{team.manager_name} passes.")
                active_managers.remove(team.manager_name)
                if not active_managers:
                    break
                continue

            try:
                bid = float(raw)
            except ValueError:
                print("Invalid bid. Treated as pass.")
                active_managers.remove(team.manager_name)
                if not active_managers:
                    break
                continue

            if bid < current_price:
                print("Bid must be >= current price. Treated as pass.")
                active_managers.remove(team.manager_name)
                if not active_managers:
                    break
                continue

            if bid > team.budget:
                print("You don't have enough budget. Treated as pass.")
                active_managers.remove(team.manager_name)
                if not active_managers:
                    break
                continue

            opened = True
            current_price = bid
            current_winner = team.manager_name
            print(f"{team.manager_name} bids {current_price} Cr for {player.name}.")

        # End conditions
        if not opened and not active_managers:
            # everyone passed without opening
            return None, 0.0

        if opened and (len(active_managers) <= 1):
            # one or zero active bidders left after at least one bid
            break

    return current_winner, current_price if current_winner else (None, 0.0)


def display_squads(teams: list[Team]) -> None:
    """Print all squads in a readable format."""
    for team in teams:
        print(f"Team {team.manager_name} (Budget left: {team.budget:.2f} Cr)")
        if not team.players:
            print("  [No players]")
        else:
            for p in team.players:
                print(
                    f"  - {p.name} ({p.role.upper()}, "
                    f"Rating: {p.overall_rating}, Base: {p.base_price} Cr)"
                )
        print()


# ----------------------------------------------------
# TESTING FUNCTIONS
# ----------------------------------------------------


def quick_assign_players(
    players: list[Player],
    manager_names: list[str],
    squad_size: int = 6,
    starting_budget: float = 20.0,
) -> list[Team]:
    """Fast, non-interactive assignment of players to teams for testing.

    Players are shuffled and then assigned round-robin to managers
    until squads reach squad_size or players run out.
    """
    import random

    # Initialize teams
    teams: list[Team] = [
        Team(manager_name=name, budget=starting_budget) for name in manager_names
    ]

    pool = list(players)
    random.shuffle(pool)

    team_idx = 1  # start from second manager for fun
    while pool and any(len(t.players) < squad_size for t in teams):
        player = pool.pop(0)

        # Find next team that still has room
        attempts = 0
        while attempts < len(teams) and len(teams[team_idx].players) >= squad_size:
            team_idx = (team_idx + 1) % len(teams)
            attempts += 1

        if len(teams[team_idx].players) >= squad_size:
            # everyone full
            break

        team = teams[team_idx]
        team.players.append(player)
        # Optional: simple cost = base_price, subtract from budget
        cost = player.base_price
        if cost > team.budget:
            cost = team.budget
        team.budget -= cost

        team_idx = (team_idx + 1) % len(teams)

    return teams
