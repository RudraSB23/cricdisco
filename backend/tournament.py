"""
Tournament bracket logic for the IPL Simulator.

Handles tournament structure, match scheduling, and standings calculation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from backend.models import Team


@dataclass
class TournamentMatch:
    """Represents a match in the tournament."""

    team_a: Team
    team_b: Team
    winner: str | None = None
    tied: bool = False
    team_a_score: str = ""
    team_b_score: str = ""
    match_type: str = "League"  # League, Semi-Final 1, Semi-Final 2, Final
    completed: bool = False


class TournamentBracket:
    """
    Manages tournament bracket for 2-6 teams.

    Format:
    - 2 teams: Direct Final
    - 3-4 teams: Round-robin league + Final
    - 5-6 teams: Round-robin league + Semi-Finals + Final
    """

    def __init__(self, teams: List[Team], overs: int = 5):
        self.teams = teams
        self.overs = overs
        self.team_names = [t.manager_name for t in teams]
        self.num_teams = len(teams)

        # Tournament state
        self.matches: List[TournamentMatch] = []
        self.standings: Dict[str, Dict[str, Any]] = {}
        self.current_match_index: int = 0
        self.stage: str = ""  # "League", "Semi-Final", "Final", "Completed"

        # Initialize standings
        for team in teams:
            self.standings[team.manager_name] = {
                "played": 0,
                "won": 0,
                "lost": 0,
                "tied": 0,
                "runs_for": 0,
                "runs_against": 0,
                "overs_faced": 0.0,
                "overs_bowled": 0.0,
                "points": 0,
                "net_run_rate": 0.0,
            }

        # Generate fixture
        self._generate_fixture()

    def _generate_fixture(self) -> None:
        """Generate match fixture based on number of teams."""
        if self.num_teams == 2:
            self._generate_direct_final()
        elif self.num_teams <= 4:
            self._generate_league_phase()
        else:
            self._generate_league_phase()

    def _generate_direct_final(self) -> None:
        """Generate direct final for 2 teams."""
        self.stage = "Final"
        match = TournamentMatch(
            team_a=self.teams[0],
            team_b=self.teams[1],
            match_type="Final",
        )
        self.matches.append(match)

    def _generate_league_phase(self) -> None:
        """Generate round-robin league phase."""
        self.stage = "League"

        # Round-robin: each team plays every other team once
        for i in range(len(self.teams)):
            for j in range(i + 1, len(self.teams)):
                match = TournamentMatch(
                    team_a=self.teams[i],
                    team_b=self.teams[j],
                    match_type="League",
                )
                self.matches.append(match)

    def get_next_match(self) -> TournamentMatch | None:
        """Get the next match to be played."""
        if self.current_match_index >= len(self.matches):
            return None
        return self.matches[self.current_match_index]

    def complete_match(
        self,
        winner_name: str | None,
        team_a_score: str,
        team_b_score: str,
        tied: bool = False,
    ) -> Tuple[bool, str]:
        """
        Mark current match as complete and update standings.

        Returns:
            Tuple of (is_tournament_complete, next_stage_message)
        """
        if self.current_match_index >= len(self.matches):
            return False, "No more matches to play"

        match = self.matches[self.current_match_index]
        match.winner = winner_name
        match.team_a_score = team_a_score
        match.team_b_score = team_b_score
        match.tied = tied
        match.completed = True

        # Update standings
        self._update_standings(match)

        # Move to next match
        self.current_match_index += 1

        # Check if league phase is complete
        if self.current_match_index >= len(self.matches):
            if self.num_teams >= 5:
                # Generate semi-finals
                self._generate_semi_finals()
                return False, "League phase complete! Moving to Semi-Finals."
            elif self.num_teams >= 3:
                # Generate final
                self._generate_final()
                return False, "League phase complete! Moving to Final."
            else:
                # Tournament complete (2 teams, direct final)
                self.stage = "Completed"
                return True, "Tournament complete!"

        # Check if we need to move to next stage
        if self.stage == "League" and self._should_move_to_knockout():
            if self.num_teams >= 5:
                self._generate_semi_finals()
                return False, "League phase complete! Moving to Semi-Finals."
            elif self.num_teams >= 3:
                self._generate_final()
                return False, "League phase complete! Moving to Final."

        return False, f"Match complete! Next: {self.get_next_match_info()}"

    def _should_move_to_knockout(self) -> bool:
        """Check if all league matches are complete."""
        return all(m.completed for m in self.matches if m.match_type == "League")

    def _generate_semi_finals(self) -> None:
        """Generate semi-finals based on league standings."""
        self.stage = "Semi-Final"

        # Sort teams by points, then NRR
        sorted_teams = sorted(
            self.standings.items(),
            key=lambda x: (x[1]["points"], x[1]["net_run_rate"]),
            reverse=True,
        )

        # Top 4 teams qualify
        top_4 = sorted_teams[:4]

        # Semi-Final 1: 1st vs 4th
        sf1_team_a = self._get_team_by_name(top_4[0][0])
        sf1_team_b = self._get_team_by_name(top_4[3][0])

        # Semi-Final 2: 2nd vs 3rd
        sf2_team_a = self._get_team_by_name(top_4[1][0])
        sf2_team_b = self._get_team_by_name(top_4[2][0])

        sf1 = TournamentMatch(
            team_a=sf1_team_a,
            team_b=sf1_team_b,
            match_type="Semi-Final 1",
        )
        sf2 = TournamentMatch(
            team_a=sf2_team_a,
            team_b=sf2_team_b,
            match_type="Semi-Final 2",
        )

        self.matches.append(sf1)
        self.matches.append(sf2)

    def _generate_final(self) -> None:
        """Generate final based on league standings or semi-final winners."""
        self.stage = "Final"

        if self.num_teams >= 5:
            # Final is already generated after semi-finals
            return

        # For 3-4 teams, get top 2 from league
        sorted_teams = sorted(
            self.standings.items(),
            key=lambda x: (x[1]["points"], x[1]["net_run_rate"]),
            reverse=True,
        )

        final_team_a = self._get_team_by_name(sorted_teams[0][0])
        final_team_b = self._get_team_by_name(sorted_teams[1][0])

        final = TournamentMatch(
            team_a=final_team_a,
            team_b=final_team_b,
            match_type="Final",
        )
        self.matches.append(final)

    def _get_team_by_name(self, team_name: str) -> Team:
        """Get Team object by manager name."""
        for team in self.teams:
            if team.manager_name == team_name:
                return team
        return self.teams[0]  # Fallback

    def _update_standings(self, match: TournamentMatch) -> None:
        """Update standings after a match."""
        team_a_name = match.team_a.manager_name
        team_b_name = match.team_b.manager_name

        # Parse scores (format: "runs/wickets (overs)")
        team_a_runs = int(match.team_a_score.split("/")[0]) if match.team_a_score else 0
        team_b_runs = int(match.team_b_score.split("/")[0]) if match.team_b_score else 0

        # Update matches played
        self.standings[team_a_name]["played"] += 1
        self.standings[team_b_name]["played"] += 1

        # Update runs
        self.standings[team_a_name]["runs_for"] += team_a_runs
        self.standings[team_a_name]["runs_against"] += team_b_runs
        self.standings[team_b_name]["runs_for"] += team_b_runs
        self.standings[team_b_name]["runs_against"] += team_a_runs

        # Update win/loss/tied
        if match.tied or match.winner is None:
            self.standings[team_a_name]["tied"] += 1
            self.standings[team_b_name]["tied"] += 1
            self.standings[team_a_name]["points"] += 1
            self.standings[team_b_name]["points"] += 1
        else:
            winner = match.winner
            loser = team_b_name if winner == team_a_name else team_a_name
            self.standings[winner]["won"] += 1
            self.standings[winner]["points"] += 2
            self.standings[loser]["lost"] += 1

        # Calculate net run rate
        for team_name in [team_a_name, team_b_name]:
            stats = self.standings[team_name]
            if stats["played"] > 0:
                # Simplified NRR: (runs_for / overs_faced) - (runs_against / overs_bowled)
                # For now, use matches as proxy for overs
                avg_runs_scored = stats["runs_for"] / stats["played"]
                avg_runs_conceded = stats["runs_against"] / stats["played"]
                stats["net_run_rate"] = (avg_runs_scored - avg_runs_conceded) / 10

    def get_standings_table(self) -> str:
        """Get formatted standings table."""
        sorted_teams = sorted(
            self.standings.items(),
            key=lambda x: (x[1]["points"], x[1]["net_run_rate"]),
            reverse=True,
        )

        lines = ["**Tournament Standings**\n"]
        lines.append("| Pos | Team | P | W | L | T | Pts | NRR |")
        lines.append("|-----|------|---|---|---|---|-----|-----|")

        for pos, (team_name, stats) in enumerate(sorted_teams, 1):
            lines.append(
                f"| {pos} | {team_name} | {stats['played']} | {stats['won']} | "
                f"{stats['lost']} | {stats['tied']} | {stats['points']} | "
                f"{stats['net_run_rate']:+.2f} |"
            )

        return "\n".join(lines)

    def get_next_match_info(self) -> str:
        """Get info about the next match."""
        next_match = self.get_next_match()
        if next_match is None:
            return "No more matches"

        return f"{next_match.team_a.manager_name} vs {next_match.team_b.manager_name} ({next_match.match_type})"

    def get_tournament_status(self) -> str:
        """Get overall tournament status."""
        completed = sum(1 for m in self.matches if m.completed)
        total = len(self.matches)

        return f"**Stage**: {self.stage}\n**Progress**: {completed}/{total} matches complete"

    def get_winner(self) -> str | None:
        """Get the tournament winner."""
        if self.stage != "Completed":
            return None

        # Find the final match winner
        for match in self.matches:
            if match.match_type == "Final" and match.completed:
                return match.winner

        return None
