"""
Auction logic for the IPL Simulator.

Handles the player auction phase where managers bid on players
to build their teams.
"""

import random
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
    manager_ids: list[int] | None = None,
    balance_roles: bool = True,
) -> list[Team]:
    """Fast, non-interactive assignment of players to teams.

    Players are assigned to teams with balanced role distribution.

    Role balance for 11 players:
    - 5 Batsmen (including 1 WK)
    - 3 All-Rounders
    - 3 Bowlers

    For smaller squads, roles are scaled proportionally.

    Args:
        players: List of players to assign
        manager_names: List of team/manager names
        squad_size: Number of players per team
        starting_budget: Starting budget for each team
        manager_ids: Optional list of Discord user IDs for each manager
        balance_roles: Whether to balance roles across teams
    """
    from collections import defaultdict

    # Initialize teams
    if manager_ids is None:
        manager_ids = [None] * len(manager_names)  # type: ignore[list-item]

    teams: list[Team] = [
        Team(manager_name=name, budget=starting_budget, manager_id=mid)
        for name, mid in zip(manager_names, manager_ids)
    ]

    # Group players by role
    players_by_role: dict[str, list[Player]] = defaultdict(list)
    for player in players:
        role = player.role.lower()
        # Normalize roles
        if role in ["wk", "wicket-keeper", "wicketkeeper"]:
            role = "wk"
        elif role in ["bat", "batsman", "batter"]:
            role = "bat"
        elif role in ["ar", "all-rounder", "allrounder"]:
            role = "ar"
        elif role in ["bowl", "bowler"]:
            role = "bowl"
        players_by_role[role].append(player)

    # Shuffle each role group
    for role in players_by_role:
        random.shuffle(players_by_role[role])

    if balance_roles:
        # Calculate role distribution for squad size
        # Base distribution for 11 players: 5 bat (incl 1 wk), 3 ar, 3 bowl
        role_targets = _calculate_role_targets(squad_size)

        # Assign players role by role to ensure balance
        _assign_balanced_squads(teams, players_by_role, role_targets, squad_size)
    else:
        # Original random assignment
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


def _calculate_role_targets(squad_size: int) -> dict[str, int]:
    """Calculate target role distribution for a given squad size."""
    # Base ratios for 11 players: 5 bat (incl 1 wk), 3 ar, 3 bowl
    # Scale proportionally for other squad sizes

    if squad_size <= 0:
        return {"wk": 0, "bat": 0, "ar": 0, "bowl": 0}

    # Minimum viable composition
    if squad_size == 1:
        return {"wk": 0, "bat": 1, "ar": 0, "bowl": 0}
    if squad_size == 2:
        return {"wk": 0, "bat": 1, "ar": 0, "bowl": 1}
    if squad_size == 3:
        return {"wk": 0, "bat": 1, "ar": 1, "bowl": 1}
    if squad_size == 4:
        return {"wk": 0, "bat": 2, "ar": 1, "bowl": 1}
    if squad_size == 5:
        return {"wk": 1, "bat": 2, "ar": 1, "bowl": 1}

    # For 6+ players, use proportional distribution
    # Reserve 1 spot for WK if squad >= 5
    wk_count = 1 if squad_size >= 5 else 0

    remaining = squad_size - wk_count

    # Split remaining: ~50% bat, ~25% ar, ~25% bowl
    bat_count = max(1, round(remaining * 0.5))
    ar_count = max(1, round(remaining * 0.25))
    bowl_count = remaining - bat_count - ar_count

    # Ensure we don't go negative
    if bowl_count < 0:
        bowl_count = 1
        bat_count = remaining - ar_count - 1

    return {
        "wk": wk_count,
        "bat": bat_count,
        "ar": ar_count,
        "bowl": bowl_count,
    }


def _assign_balanced_squads(
    teams: list[Team],
    players_by_role: dict[str, list[Player]],
    role_targets: dict[str, int],
    squad_size: int,
) -> None:
    """Assign players to teams with balanced role distribution."""
    num_teams = len(teams)

    # Track role counts per team
    team_role_counts = [
        {"wk": 0, "bat": 0, "ar": 0, "bowl": 0} for _ in range(num_teams)
    ]

    # Assign players role by role
    for role, target_count in role_targets.items():
        if target_count == 0:
            continue

        available = players_by_role.get(role, [])

        # Distribute players of this role across teams
        for team_idx in range(num_teams):
            while (
                team_role_counts[team_idx][role] < target_count
                and len(teams[team_idx].players) < squad_size
                and available
            ):
                player = available.pop(0)
                teams[team_idx].players.append(player)
                team_role_counts[team_idx][role] += 1

                # Deduct from budget
                cost = player.base_price
                if cost > teams[team_idx].budget:
                    cost = teams[team_idx].budget
                teams[team_idx].budget -= cost

    # Fill remaining spots with any available players
    remaining_pool = []
    for role_players in players_by_role.values():
        remaining_pool.extend(role_players)

    random.shuffle(remaining_pool)

    team_idx = 0
    while remaining_pool and any(len(t.players) < squad_size for t in teams):
        if len(teams[team_idx].players) < squad_size:
            player = remaining_pool.pop(0)
            teams[team_idx].players.append(player)

            cost = player.base_price
            if cost > teams[team_idx].budget:
                cost = teams[team_idx].budget
            teams[team_idx].budget -= cost

        team_idx = (team_idx + 1) % num_teams
