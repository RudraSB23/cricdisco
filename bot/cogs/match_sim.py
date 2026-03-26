# bot/cogs/match_sim.py
"""
Match simulation cog for CricDisco.

This cog handles Discord UI for match simulation, delegating core logic to backend modules.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import discord
from discord.ext import commands

from backend.match import simulate_ball
from backend.match_state import (
    build_innings_state,
    finalize_innings,
    get_batting_order,
    get_bowling_rotation,
    simulate_over,
)
from backend.match_stats import calculate_match_stats, compute_match_result
from backend.models import InningsResult, MatchResult, Team
from backend.tournament_update import (
    MatchInfo,
    TeamStats,
    check_league_phase_complete,
    update_tournament_standings,
)
from bot.logging_config import get_cog_logger, log_view_errors
from bot.session_state import get_session

logger = get_cog_logger("MatchSim")

MATCH_STATE_ATTR = "match_state"


async def start_toss_for_channel(
    interaction: discord.Interaction,
    team_a: Team,
    team_b: Team,
    overs: int = 5,
) -> None:
    """
    Run a coin toss + choice (bat/bowl) flow before starting the match.
    - Team A manager is asked to choose heads/tails via ephemeral buttons.
    - Public embed shows toss in progress.
    - Random coin result decides winner.
    - Winner then chooses bat/bowl via another ephemeral view.
    - Finally calls start_match_for_channel with correct batting order.
    """
    if interaction.guild is None or interaction.channel is None:
        embed = discord.Embed(
            title="CricDisco • Error",
            description="Use this command in a server channel.",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    chooser_team = team_a
    other_team = team_b

    session = get_session(interaction.guild.id, interaction.channel.id)  # type: ignore[arg-type]

    # Get the Discord user ID of the manager who owns team_a
    # team_a.manager_id should be set from quick_assign_players
    chooser_id = team_a.manager_id

    # Fallback if manager_id is not set
    if chooser_id is None:
        # Use the first manager in the session as fallback
        chooser_id = (
            session.managers[0]
            if session.managers
            else session.owner_id or interaction.user.id
        )

    # Toss choice view for chooser (public message, but restricted clicks)
    view = TossChoiceView(
        chooser_id=chooser_id,
        team_a=chooser_team,
        team_b=other_team,
        overs=overs,
        public_message=None,  # Will be set below
    )

    # Send public embed with toss choice buttons
    public_embed = discord.Embed(
        title="🪙 Toss Time",
        description=(
            f"**{chooser_team.manager_name}** is choosing **Heads or Tails**...\n\n"
            f"Only {chooser_team.manager_name} can make this choice."
        ),
        color=discord.Color.gold(),
    )
    public_msg = await interaction.followup.send(embed=public_embed, view=view)
    view.public_message = public_msg  # Store reference for later editing


async def start_match_for_channel(
    interaction: discord.Interaction,
    team_a: Team,
    team_b: Team,
    overs: int = 5,
) -> None:
    """
    Generic entry-point to start an over-by-over match in this channel.

    - Picks playing XIs
    - Sets up innings 1 state
    - Stores state on the session
    - Sends the initial match embed with control view
    """
    if interaction.guild is None or interaction.channel is None:
        embed = discord.Embed(
            title="CricDisco • Error",
            description="Use this command in a server channel.",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    session = get_session(interaction.guild.id, interaction.channel.id)  # type: ignore[arg-type]

    # Prepare playing XIs
    xi_a = select_playing_xi(team_a)
    xi_b = select_playing_xi(team_b)

    # First innings setup
    state = build_innings_state(
        innings_num=1,
        batting_team_name=team_a.manager_name,
        bowling_team_name=team_b.manager_name,
        batting_xi=xi_a,
        bowling_xi=xi_b,
        overs=overs,
        target=None,
    )

    # Persist state on the session so the View can access it
    setattr(
        session,
        MATCH_STATE_ATTR,
        {
            "innings_state": state,
            "team_a_name": team_a.manager_name,
            "team_b_name": team_b.manager_name,
            "team_a_xi": xi_a,
            "team_b_xi": xi_b,
            "overs": overs,
            "innings_a": None,
            "innings_b": None,
        },
    )

    start_embed = discord.Embed(
        title="🏏 Match Starting",
        description=(
            f"**{team_a.manager_name}** vs **{team_b.manager_name}**\n"
            f"Format: **{overs} overs** per innings.\n\n"
            f"First innings: **{team_a.manager_name}** batting."
        ),
        color=discord.Color.green(),
    )
    start_embed.add_field(
        name="Status",
        value="Press **Next Over** to simulate the first over.",
        inline=False,
    )

    view = OverControlView(
        organiser_id=session.owner_id,
        session_key=(interaction.guild.id, interaction.channel.id),
    )

    # Assume caller already did interaction.response.defer();
    await interaction.followup.send(embed=start_embed, view=view)


def build_innings_state(
    innings_num: int,
    batting_team_name: str,
    bowling_team_name: str,
    batting_xi,
    bowling_xi,
    overs: int,
    target: int | None,
) -> Dict[str, Any]:
    batting_order = get_batting_order(batting_xi)
    bowling_rotation = get_bowling_rotation(bowling_xi)

    return {
        "innings_num": innings_num,
        "overs": overs,
        "runs": 0,
        "wickets": 0,
        "balls": 0,
        "current_over": 0,
        "batting_team_name": batting_team_name,
        "bowling_team_name": bowling_team_name,
        "batting_order": batting_order,
        "bowling_rotation": bowling_rotation,
        "striker_index": 0,
        "non_striker_index": 1 if len(batting_order) > 1 else 0,
        "completed": False,
        "ball_log": [],
        "target": target,
        "current_bowler": None,
        # Player performance tracking for MoM
        "batter_runs": {},  # player_name -> runs scored
        "bowler_wickets": {},  # player_name -> wickets taken
    }


class TossChoiceView(discord.ui.View):
    def __init__(
        self,
        chooser_id: int,
        team_a: Team,
        team_b: Team,
        overs: int,
        public_message: discord.Message | None = None,
    ) -> None:
        super().__init__(timeout=60)
        self.chooser_id = chooser_id
        self.team_a = team_a
        self.team_b = team_b
        self.overs = overs
        self.public_message = public_message  # "choosing" message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.chooser_id:
            await interaction.response.send_message(
                f"🚫 Only the captain of **{self.team_a.manager_name}** can choose the toss.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve_toss(interaction, "Heads")

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._resolve_toss(interaction, "Tails")

    async def _resolve_toss(self, interaction: discord.Interaction, choice: str):
        # Acknowledge the interaction first
        await interaction.response.defer()

        # Disable buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        # Random coin flip
        outcome = random.choice(["Heads", "Tails"])

        # Suspense on public message
        suspense_embed = discord.Embed(
            title="🪙 Toss in the Air...",
            description="The coin is flipping...",
            color=discord.Color.gold(),
        )
        if self.public_message:
            await self.public_message.edit(embed=suspense_embed, view=None)

        # Decide winner team
        if choice == outcome:
            winner_team = self.team_a
            loser_team = self.team_b
        else:
            winner_team = self.team_b
            loser_team = self.team_a

        # Show result publicly
        result_embed = discord.Embed(
            title="🪙 Toss Result",
            description=(
                f"The coin lands on **{outcome}**!\n\n"
                f"**{winner_team.manager_name}** wins the toss against **{loser_team.manager_name}**."
            ),
            color=discord.Color.green(),
        )
        if self.public_message:
            await self.public_message.edit(embed=result_embed)

        # Public bat/bowl choice for winner (restricted clicks)
        choose_embed = discord.Embed(
            title="🏏 Toss Won – Choose to Bat or Bowl",
            description=(
                f"**{winner_team.manager_name}** won the toss.\n\n"
                f"Only {winner_team.manager_name} can make this choice."
            ),
            color=discord.Color.blurple(),
        )

        choice_view = BatBowlChoiceView(
            chooser_id=winner_team.manager_id or self.chooser_id,
            winner_team=winner_team,
            loser_team=loser_team,
            overs=self.overs,
        )
        await interaction.followup.send(embed=choose_embed, view=choice_view)


class BatBowlChoiceView(discord.ui.View):
    def __init__(
        self,
        chooser_id: int,
        winner_team: Team,
        loser_team: Team,
        overs: int,
    ) -> None:
        super().__init__(timeout=60)
        self.chooser_id = chooser_id
        self.winner_team = winner_team
        self.loser_team = loser_team
        self.overs = overs

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only the toss winner can choose
        if interaction.user.id != self.chooser_id:
            await interaction.response.send_message(
                f"🚫 Only the captain of **{self.winner_team.manager_name}** can make this choice.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Batting first", style=discord.ButtonStyle.success)
    async def bat_first(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self._finalise_decision(interaction, batting_first=self.winner_team)

    @discord.ui.button(label="Bowling first", style=discord.ButtonStyle.danger)
    async def bowl_first(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self._finalise_decision(interaction, batting_first=self.loser_team)

    async def _finalise_decision(
        self,
        interaction: discord.Interaction,
        batting_first: Team,
    ):
        # Acknowledge the interaction first
        await interaction.response.defer()

        # Disable buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        bowling_first = (
            self.winner_team if batting_first is self.loser_team else self.loser_team
        )

        choice_text = "bat first" if batting_first is self.winner_team else "bowl first"

        summary_embed = discord.Embed(
            title="🏏 Toss Decision",
            description=(
                f"**{self.winner_team.manager_name}** won the toss and chose to **{choice_text.upper()}**.\n\n"
                f"**{batting_first.manager_name}** will bat first.\n"
                f"**{bowling_first.manager_name}** will bowl first."
            ),
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=summary_embed)

        # Now start the match with chosen batting order
        await start_match_for_channel(
            interaction=interaction,
            team_a=batting_first,
            team_b=bowling_first,
            overs=self.overs,
        )


class OverControlView(discord.ui.View):
    def __init__(self, organiser_id: int, session_key: Tuple[int, int]) -> None:
        super().__init__(timeout=900)  # 15 minutes
        self.organiser_id = organiser_id
        self.session_key = session_key  # (guild_id, channel_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.organiser_id:
            embed = discord.Embed(
                title="CricDisco • Not Your Match",
                description="Only the organiser of this game can control the simulation.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    @discord.ui.button(
        label="Next Over",
        style=discord.ButtonStyle.primary,
        custom_id="match_sim_next_over",
    )
    async def next_over_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild_id = interaction.guild.id if interaction.guild else None
        channel_id = interaction.channel.id if interaction.channel else None
        if guild_id is None or channel_id is None:
            await interaction.response.send_message(
                "Use this in a server.", ephemeral=True
            )
            return

        session = get_session(guild_id, channel_id)  # type: ignore[arg-type]
        wrapper = getattr(session, MATCH_STATE_ATTR, None)
        if not wrapper:
            embed_done = discord.Embed(
                title="CricDisco • No Active Match",
                description="There is no active match running in this channel.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed_done, ephemeral=True)
            return

        state: Dict[str, Any] = wrapper.get("innings_state")
        if not state:
            logger.error("No innings_state found in wrapper")
            button.disabled = True
            await interaction.response.edit_message(view=self)
            return

        overs = state["overs"]

        # If innings already completed, see if we should move to next innings or show result
        if state.get("completed"):
            await self._handle_completed_innings(interaction, button, session, wrapper)
            return

        # Simulate one over using backend logic
        over_summary = simulate_over(state, simulate_ball)

        # Commentary + embed
        commentary = build_commentary(
            over_num=state["current_over"],
            runs_in_over=over_summary["runs_in_over"],
            wickets_in_over=over_summary["wickets_in_over"],
            total_runs=state["runs"],
            total_wkts=state["wickets"],
            target=state["target"],
            balls_bowled=state["balls"],
            max_balls=state["overs"] * 6,
        )

        embed = discord.Embed(
            title=f"🏏 Innings {state['innings_num']} • Over {state['current_over']}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Batting",
            value=state["batting_team_name"],
            inline=True,
        )
        embed.add_field(
            name="Bowling",
            value=state["bowling_team_name"],
            inline=True,
        )
        embed.add_field(
            name="This over",
            value=over_summary["over_str"],
            inline=False,
        )

        # Batters & bowler view
        batting_order = state["batting_order"]
        striker = batting_order[state["striker_index"]]
        non_striker = batting_order[state["non_striker_index"]]
        bowler_obj = state.get("current_bowler")

        batters_lines = [
            f"▶ {striker.name} (STR)",
            f"• {non_striker.name} (NON-STR)",
        ]
        if bowler_obj is not None:
            batters_lines.append(f"🎯 {bowler_obj.name} (BOWL)")

        embed.add_field(
            name="Batters & Bowler",
            value="\n".join(batters_lines),
            inline=False,
        )

        score_line = f"{runs}/{wickets} in {balls // 6}.{balls % 6} overs"
        if target:
            remaining = target - runs
            balls_left = (overs * 6) - balls
            if remaining > 0:
                score_line += f"\nNeed **{remaining}** from **{balls_left}** balls"
            else:
                score_line += "\nTarget achieved!"

        embed.add_field(
            name="Score",
            value=score_line,
            inline=False,
        )
        embed.add_field(
            name="Commentary",
            value=commentary,
            inline=False,
        )

        if state["completed"]:
            embed.set_footer(text="Innings complete. Press Next Over to proceed.")

        await interaction.response.edit_message(embed=embed, view=self)

        # If completed, store the innings result with player performances
        if state["completed"]:
            innings_res, innings_perf = finalize_innings(state, InningsResult)

            if state["innings_num"] == 1:
                wrapper["innings_a"] = innings_perf
                logger.info(
                    f"Stored innings_a: {innings_res.runs}/{innings_res.wickets} in {innings_res.balls / 6:.1f} overs"
                )
            else:
                wrapper["innings_b"] = innings_perf
                logger.info(
                    f"Stored innings_b: {innings_res.runs}/{innings_res.wickets} in {innings_res.balls / 6:.1f} overs"
                )

    async def _handle_completed_innings(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
        session,
        wrapper: Dict[str, Any],
    ):
        """Move from first to second innings, or show final result."""
        state: Dict[str, Any] = wrapper.get("innings_state")
        if not state:
            logger.error("No innings_state in _handle_completed_innings")
            button.disabled = True
            await interaction.response.edit_message(view=self)
            return

        overs = state["overs"]

        # If only first innings done, start second
        if state["innings_num"] == 1 and wrapper.get("innings_b") is None:
            # Defensive: check innings_a exists and has result
            innings_a_perf = wrapper.get("innings_a")
            if not innings_a_perf or not isinstance(innings_a_perf, dict):
                logger.error(f"innings_a_perf is missing or invalid: {innings_a_perf}")
                error_embed = discord.Embed(
                    title="❌ Match Error",
                    description="Match data is corrupted. Please restart the match.",
                    color=discord.Color.red(),
                )
                button.disabled = True
                await interaction.response.edit_message(embed=error_embed, view=self)
                return

            innings_a: InningsResult = innings_a_perf.get("result")
            if not innings_a:
                logger.error(
                    f"innings_a result is missing from innings_a_perf: {innings_a_perf}"
                )
                error_embed = discord.Embed(
                    title="❌ Match Error",
                    description="Match data is corrupted. Please restart the match.",
                    color=discord.Color.red(),
                )
                button.disabled = True
                await interaction.response.edit_message(embed=error_embed, view=self)
                return

            target = innings_a.runs + 1

            second_state = build_innings_state(
                innings_num=2,
                batting_team_name=wrapper["team_b_name"],
                bowling_team_name=wrapper["team_a_name"],
                batting_xi=wrapper["team_b_xi"],
                bowling_xi=wrapper["team_a_xi"],
                overs=overs,
                target=target,
            )
            wrapper["innings_state"] = second_state
            logger.info(f"Starting 2nd innings. Target: {target}")

            embed = discord.Embed(
                title="🔄 Innings Break",
                description=(
                    f"{wrapper['team_a_name']}: **{innings_a.runs}/{innings_a.wickets}** "
                    f"({innings_a.balls / 6:.1f} overs)\n"
                    f"Target for {wrapper['team_b_name']}: **{target}**"
                ),
                color=discord.Color.gold(),
            )
            embed.add_field(
                name="Status",
                value="Second innings starting. Press **Next Over** to continue.",
                inline=False,
            )
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # Both innings done: show final result and disable button
        innings_a_perf = wrapper.get("innings_a")
        innings_b_perf = wrapper.get("innings_b")

        # Defensive checks for innings data
        if not innings_a_perf or not isinstance(innings_a_perf, dict):
            logger.error(f"innings_a_perf is missing or invalid: {innings_a_perf}")
            button.disabled = True
            error_embed = discord.Embed(
                title="❌ Match Data Error",
                description="First innings data is missing. Cannot show result.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=error_embed, view=self)
            return

        if innings_b_perf is None:
            logger.error("innings_b_perf is None but innings_num != 1")
            button.disabled = True
            error_embed = discord.Embed(
                title="❌ Match Data Error",
                description="Second innings data is missing. Cannot show result.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=error_embed, view=self)
            return

        if not isinstance(innings_b_perf, dict):
            logger.error(f"innings_b_perf is not a dict: {innings_b_perf}")
            button.disabled = True
            error_embed = discord.Embed(
                title="❌ Match Data Error",
                description="Second innings data is corrupted. Cannot show result.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=error_embed, view=self)
            return

        innings_a: InningsResult = innings_a_perf.get("result")
        innings_b: InningsResult = innings_b_perf.get("result")

        if not innings_a:
            logger.error(f"innings_a result missing: {innings_a_perf}")
            button.disabled = True
            error_embed = discord.Embed(
                title="❌ Match Data Error",
                description="First innings result is missing.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=error_embed, view=self)
            return

        if not innings_b:
            logger.error(f"innings_b result missing: {innings_b_perf}")
            button.disabled = True
            error_embed = discord.Embed(
                title="❌ Match Data Error",
                description="Second innings result is missing.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=error_embed, view=self)
            return

        # Compute match result using backend logic
        match_res = compute_match_result(
            wrapper["team_a_name"],
            wrapper["team_b_name"],
            innings_a,
            innings_b,
            innings_a_perf,
            innings_b_perf,
        )
        button.disabled = True

        overs_a = innings_a.balls / 6 if innings_a.balls else 0.0
        overs_b = innings_b.balls / 6 if innings_b.balls else 0.0

        embed = discord.Embed(
            title="🏁 Match Summary",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name=wrapper["team_a_name"],
            value=(
                f"Score: **{innings_a.runs}/{innings_a.wickets}**\n"
                f"Overs: `{overs_a:.1f}`"
            ),
            inline=True,
        )
        embed.add_field(
            name=wrapper["team_b_name"],
            value=(
                f"Score: **{innings_b.runs}/{innings_b.wickets}**\n"
                f"Overs: `{overs_b:.1f}`"
            ),
            inline=True,
        )

        # Man of the Match
        if match_res.man_of_the_match is not None:
            embed.add_field(
                name="🏆 Man of the Match",
                value=f"**{match_res.man_of_the_match}**",
                inline=False,
            )

        if match_res.winner is None:
            footer = "Result: Match tied."
        else:
            footer = f"Result: {match_res.winner} {match_res.margin}."

        embed.set_footer(text=footer)

        # Add stats button
        view = MatchEndView(
            innings_a_perf=innings_a_perf,
            innings_b_perf=innings_b_perf,
            team_a_name=wrapper["team_a_name"],
            team_b_name=wrapper["team_b_name"],
            show_next_button=session.tournament_mode
            and not session.tournament_stage == "Completed"
            if hasattr(session, "tournament_mode")
            else False,
            next_match_info=None,
            session_key=self.session_key,
            overs=overs,
        )
        view.children[0].disabled = False  # Enable the stats button

        logger.info(
            f"Match complete: {wrapper['team_a_name']} vs {wrapper['team_b_name']}"
        )
        await interaction.response.edit_message(embed=embed, view=view)


class MatchEndView(discord.ui.View):
    """View with stats and next match buttons for match end."""

    def __init__(
        self,
        innings_a_perf: Dict[str, Any],
        innings_b_perf: Dict[str, Any],
        team_a_name: str,
        team_b_name: str,
        show_next_button: bool = False,
        next_match_info: str | None = None,
        session_key: Tuple[int, int] | None = None,
        overs: int = 5,
    ) -> None:
        super().__init__(timeout=300)
        self.innings_a_perf = innings_a_perf
        self.innings_b_perf = innings_b_perf
        self.team_a_name = team_a_name
        self.team_b_name = team_b_name
        self.show_next_button = show_next_button
        self.next_match_info = next_match_info
        self.session_key = session_key
        self.overs = overs

    @discord.ui.button(
        label="📊 View Player Stats",
        style=discord.ButtonStyle.secondary,
        custom_id="match_stats_view",
    )
    @log_view_errors("MatchSim")
    async def view_stats(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        try:
            # Calculate stats
            player_stats = calculate_match_stats(
                innings_a_perf=self.innings_a_perf,
                innings_b_perf=self.innings_b_perf,
                team_a_name=self.team_a_name,
                team_b_name=self.team_b_name,
            )

            # Create stats embed
            stats_embed = discord.Embed(
                title="📊 Match Statistics",
                description="Detailed player performance statistics",
                color=discord.Color.blue(),
            )
            # ... (rest of stats embed code - same as before)
            # Group by team
            team_a_stats = [
                (name, stats)
                for name, stats in player_stats.items()
                if stats["team"] == self.team_a_name
            ]
            team_b_stats = [
                (name, stats)
                for name, stats in player_stats.items()
                if stats["team"] == self.team_b_name
            ]

            # Format Team A batting
            bat_lines_a = []
            for name, stats in sorted(
                team_a_stats,
                key=lambda x: x[1]["batting"]["runs"],
                reverse=True,
            ):
                bat = stats["batting"]
                if bat["balls_faced"] > 0:
                    sr = bat["strike_rate"]
                    not_out = "*" if bat["not_out"] else ""
                    bat_lines_a.append(
                        f"**{name}**: {bat['runs']}{not_out} ({bat['balls_faced']}) "
                        f"4s:{bat['fours']} 6s:{bat['sixes']} SR:{sr:.1f}"
                    )

            if bat_lines_a:
                stats_embed.add_field(
                    name=f"🏏 {self.team_a_name} - Batting",
                    value="\n".join(bat_lines_a)[:1024],
                    inline=False,
                )

            # Format Team A bowling
            bowl_lines_a = []
            for name, stats in sorted(
                team_a_stats,
                key=lambda x: x[1]["bowling"].get("wickets", 0),
                reverse=True,
            ):
                bowl = stats["bowling"]
                overs = bowl.get("balls", 0) / 6 if bowl.get("balls", 0) > 0 else 0
                if overs > 0:
                    economy = bowl.get("runs_conceded", 0) / overs if overs > 0 else 0
                    bowl_lines_a.append(
                        f"**{name}**: {bowl.get('wickets', 0)}/{bowl.get('runs_conceded', 0)} "
                        f"({overs:.1f} ov, Econ:{economy:.1f})"
                    )

            if bowl_lines_a:
                stats_embed.add_field(
                    name=f"🎯 {self.team_a_name} - Bowling",
                    value="\n".join(bowl_lines_a)[:1024],
                    inline=False,
                )

            # Format Team B batting
            bat_lines_b = []
            for name, stats in sorted(
                team_b_stats,
                key=lambda x: x[1]["batting"]["runs"],
                reverse=True,
            ):
                bat = stats["batting"]
                if bat["balls_faced"] > 0:
                    sr = bat["strike_rate"]
                    not_out = "*" if bat["not_out"] else ""
                    bat_lines_b.append(
                        f"**{name}**: {bat['runs']}{not_out} ({bat['balls_faced']}) "
                        f"4s:{bat['fours']} 6s:{bat['sixes']} SR:{sr:.1f}"
                    )

            if bat_lines_b:
                stats_embed.add_field(
                    name=f"🏏 {self.team_b_name} - Batting",
                    value="\n".join(bat_lines_b)[:1024],
                    inline=False,
                )

            # Format Team B bowling
            bowl_lines_b = []
            for name, stats in sorted(
                team_b_stats,
                key=lambda x: x[1]["bowling"].get("wickets", 0),
                reverse=True,
            ):
                bowl = stats["bowling"]
                overs = bowl.get("balls", 0) / 6 if bowl.get("balls", 0) > 0 else 0
                if overs > 0:
                    economy = bowl.get("runs_conceded", 0) / overs if overs > 0 else 0
                    bowl_lines_b.append(
                        f"**{name}**: {bowl.get('wickets', 0)}/{bowl.get('runs_conceded', 0)} "
                        f"({overs:.1f} ov, Econ:{economy:.1f})"
                    )

            if bowl_lines_b:
                stats_embed.add_field(
                    name=f"🎯 {self.team_b_name} - Bowling",
                    value="\n".join(bowl_lines_b)[:1024],
                    inline=False,
                )

            # Add summary if no stats available
            if (
                not bat_lines_a
                and not bowl_lines_a
                and not bat_lines_b
                and not bowl_lines_b
            ):
                stats_embed.description = (
                    "No detailed statistics available for this match."
                )

            stats_embed.set_footer(text="Stats calculated from match data")
            stats_embed.timestamp = interaction.created_at

            await interaction.response.send_message(embed=stats_embed, ephemeral=True)

        except Exception as e:
            # Send error message ephemeral
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to load statistics.\n`{type(e).__name__}: {e}`",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @discord.ui.button(
        label="▶️ Start Next Match",
        style=discord.ButtonStyle.primary,
        custom_id="match_next_game",
    )
    @log_view_errors("MatchSim")
    async def next_match(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        """Start the next match in the tournament."""
        if self.session_key is None:
            await interaction.response.send_message(
                "Error: No session found.",
                ephemeral=True,
            )
            return

        guild_id, channel_id = self.session_key
        session = get_session(guild_id, channel_id)

        if not session.tournament_mode:
            await interaction.response.send_message(
                "Not in tournament mode.",
                ephemeral=True,
            )
            return

        if len(session.teams) < 2:
            await interaction.response.send_message(
                "Not enough teams.",
                ephemeral=True,
            )
            return

        # Determine next match teams
        if session.league_phase_complete:
            # Knockout phase
            if session.tournament_stage == "Final":
                sorted_teams = sorted(
                    session.team_stats.items(),
                    key=lambda x: (x[1].won, x[1].net_run_rate),
                    reverse=True,
                )
                top_2_names = [sorted_teams[0][0], sorted_teams[1][0]]
                team_a = next(
                    (t for t in session.teams if t.manager_name == top_2_names[0]),
                    session.teams[0],
                )
                team_b = next(
                    (t for t in session.teams if t.manager_name == top_2_names[1]),
                    session.teams[1],
                )
                match_type = "🏆 FINAL"
            elif session.tournament_stage == "Semi-Final":
                sorted_teams = sorted(
                    session.team_stats.items(),
                    key=lambda x: (x[1].won, x[1].net_run_rate),
                    reverse=True,
                )
                top_4_names = [
                    sorted_teams[i][0] for i in range(min(4, len(sorted_teams)))
                ]
                team_a = next(
                    (t for t in session.teams if t.manager_name == top_4_names[0]),
                    session.teams[0],
                )
                team_b = (
                    next(
                        (t for t in session.teams if t.manager_name == top_4_names[3]),
                        session.teams[3],
                    )
                    if len(top_4_names) > 3
                    else session.teams[1]
                )
                match_type = "Semi-Final"
            else:
                await interaction.response.send_message(
                    "Tournament complete or invalid stage.",
                    ephemeral=True,
                )
                return
        else:
            # League phase - use fixture schedule
            if session.fixture_index < len(session.league_fixtures):
                fixture = session.league_fixtures[session.fixture_index]
                team_a_name = fixture["team_a"]
                team_b_name = fixture["team_b"]

                # Find Team objects
                team_a = next(
                    (t for t in session.teams if t.manager_name == team_a_name),
                    session.teams[0],
                )
                team_b = next(
                    (t for t in session.teams if t.manager_name == team_b_name),
                    session.teams[1],
                )
                match_type = "League"

                logger.info(
                    f"Next fixture: {team_a_name} vs {team_b_name} "
                    f"({session.fixture_index + 1}/{len(session.league_fixtures)})"
                )
            else:
                # All fixtures played, move to knockout
                session.league_phase_complete = True
                logger.info("All league fixtures complete, moving to knockout phase")

                if len(session.managers) <= 4:
                    session.tournament_stage = "Final"
                else:
                    session.tournament_stage = "Semi-Final"

                # Recursively determine next match (knockout)
                await interaction.response.send_message(
                    "🏆 **League phase complete!** Moving to knockout stage...",
                    ephemeral=True,
                )
                # Call self again to get knockout match
                await self.next_match(interaction, button)
                return

        # Store current match
        session.current_match = {
            "team_a": team_a,
            "team_b": team_b,
            "overs": self.overs,
            "match_type": match_type,
        }

        # Announce next match
        next_embed = discord.Embed(
            title=f"🏆 Tournament {match_type}",
            description=f"**{team_a.manager_name}** vs **{team_b.manager_name}**",
            color=discord.Color.gold(),
        )
        next_embed.add_field(
            name="Format",
            value=f"{self.overs} overs per innings",
            inline=True,
        )

        await interaction.response.send_message(embed=next_embed)

        # Start toss
        await start_toss_for_channel(
            interaction=interaction,
            team_a=team_a,
            team_b=team_b,
            overs=self.overs,
        )


class MatchStatsView(discord.ui.View):
    """View with stats button for displaying match statistics."""

    def __init__(
        self,
        innings_a_perf: Dict[str, Any],
        innings_b_perf: Dict[str, Any],
        team_a_name: str,
        team_b_name: str,
    ) -> None:
        super().__init__(timeout=300)
        self.innings_a_perf = innings_a_perf
        self.innings_b_perf = innings_b_perf
        self.team_a_name = team_a_name
        self.team_b_name = team_b_name
        # Initially disable the button until match ends
        self.children[0].disabled = True

    @discord.ui.button(
        label="📊 View Player Stats",
        style=discord.ButtonStyle.secondary,
        custom_id="match_stats_view",
    )
    @log_view_errors("MatchSim")
    async def view_stats(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        try:
            # Calculate stats
            player_stats = calculate_match_stats(
                innings_a_perf=self.innings_a_perf,
                innings_b_perf=self.innings_b_perf,
                team_a_name=self.team_a_name,
                team_b_name=self.team_b_name,
            )

            # Create stats embed
            stats_embed = discord.Embed(
                title="📊 Match Statistics",
                description="Detailed player performance statistics",
                color=discord.Color.blue(),
            )

            # Group by team
            team_a_stats = [
                (name, stats)
                for name, stats in player_stats.items()
                if stats["team"] == self.team_a_name
            ]
            team_b_stats = [
                (name, stats)
                for name, stats in player_stats.items()
                if stats["team"] == self.team_b_name
            ]

            # Format Team A batting
            bat_lines_a = []
            for name, stats in sorted(
                team_a_stats,
                key=lambda x: x[1]["batting"]["runs"],
                reverse=True,
            ):
                bat = stats["batting"]
                if bat["balls_faced"] > 0:
                    sr = bat["strike_rate"]
                    not_out = "*" if bat["not_out"] else ""
                    bat_lines_a.append(
                        f"**{name}**: {bat['runs']}{not_out} ({bat['balls_faced']}) "
                        f"4s:{bat['fours']} 6s:{bat['sixes']} SR:{sr:.1f}"
                    )

            if bat_lines_a:
                stats_embed.add_field(
                    name=f"🏏 {self.team_a_name} - Batting",
                    value="\n".join(bat_lines_a)[:1024],
                    inline=False,
                )

            # Format Team A bowling
            bowl_lines_a = []
            for name, stats in sorted(
                team_a_stats,
                key=lambda x: x[1]["bowling"].get("wickets", 0),
                reverse=True,
            ):
                bowl = stats["bowling"]
                overs = bowl.get("balls", 0) / 6 if bowl.get("balls", 0) > 0 else 0
                if overs > 0:
                    economy = bowl.get("runs_conceded", 0) / overs if overs > 0 else 0
                    bowl_lines_a.append(
                        f"**{name}**: {bowl.get('wickets', 0)}/{bowl.get('runs_conceded', 0)} "
                        f"({overs:.1f} ov, Econ:{economy:.1f})"
                    )

            if bowl_lines_a:
                stats_embed.add_field(
                    name=f"🎯 {self.team_a_name} - Bowling",
                    value="\n".join(bowl_lines_a)[:1024],
                    inline=False,
                )

            # Format Team B batting
            bat_lines_b = []
            for name, stats in sorted(
                team_b_stats,
                key=lambda x: x[1]["batting"]["runs"],
                reverse=True,
            ):
                bat = stats["batting"]
                if bat["balls_faced"] > 0:
                    sr = bat["strike_rate"]
                    not_out = "*" if bat["not_out"] else ""
                    bat_lines_b.append(
                        f"**{name}**: {bat['runs']}{not_out} ({bat['balls_faced']}) "
                        f"4s:{bat['fours']} 6s:{bat['sixes']} SR:{sr:.1f}"
                    )

            if bat_lines_b:
                stats_embed.add_field(
                    name=f"🏏 {self.team_b_name} - Batting",
                    value="\n".join(bat_lines_b)[:1024],
                    inline=False,
                )

            # Format Team B bowling
            bowl_lines_b = []
            for name, stats in sorted(
                team_b_stats,
                key=lambda x: x[1]["bowling"].get("wickets", 0),
                reverse=True,
            ):
                bowl = stats["bowling"]
                overs = bowl.get("balls", 0) / 6 if bowl.get("balls", 0) > 0 else 0
                if overs > 0:
                    economy = bowl.get("runs_conceded", 0) / overs if overs > 0 else 0
                    bowl_lines_b.append(
                        f"**{name}**: {bowl.get('wickets', 0)}/{bowl.get('runs_conceded', 0)} "
                        f"({overs:.1f} ov, Econ:{economy:.1f})"
                    )

            if bowl_lines_b:
                stats_embed.add_field(
                    name=f"🎯 {self.team_b_name} - Bowling",
                    value="\n".join(bowl_lines_b)[:1024],
                    inline=False,
                )

            # Add summary if no stats available
            if (
                not bat_lines_a
                and not bowl_lines_a
                and not bat_lines_b
                and not bowl_lines_b
            ):
                stats_embed.description = (
                    "No detailed statistics available for this match."
                )

            stats_embed.set_footer(text="Stats calculated from match data")
            stats_embed.timestamp = interaction.created_at

            await interaction.response.send_message(embed=stats_embed, ephemeral=True)

        except Exception as e:
            # Send error message ephemeral
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to load statistics.\n`{type(e).__name__}: {e}`",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)


def decide_result(
    team_a_name: str,
    team_b_name: str,
    innings_a: InningsResult,
    innings_b: InningsResult,
    innings_a_perf: Dict[str, Any],
    innings_b_perf: Dict[str, Any],
) -> MatchResult:
    # Decide winner + margin
    if innings_a.runs > innings_b.runs:
        winner = team_a_name
        margin = f"wins by {innings_a.runs - innings_b.runs} runs"
    elif innings_b.runs > innings_a.runs:
        wickets_left = 10 - innings_b.wickets
        wickets_left = max(wickets_left, 1)
        margin = f"wins by {wickets_left} wicket" + ("s" if wickets_left > 1 else "")
        winner = team_b_name
    else:
        winner = None
        margin = "match tied"

    # Calculate Man of the Match based on player performances
    mom = calculate_man_of_the_match(
        innings_a_perf=innings_a_perf,
        innings_b_perf=innings_b_perf,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        winning_team=winner,
    )

    return MatchResult(
        team_a_result=innings_a,
        team_b_result=innings_b,
        winner=winner,
        margin=margin,
        man_of_the_match=mom,
    )


def calculate_man_of_the_match(
    innings_a_perf: Dict[str, Any],
    innings_b_perf: Dict[str, Any],
    team_a_name: str,
    team_b_name: str,
    winning_team: str | None,
) -> str | None:
    """
    MoM scoring:
    - 1 point per run scored
    - 25 points per wicket
    - minus runs conceded (so cheaper spells are better)
    - +10 bonus if in winning team
    """
    player_scores: Dict[str, int] = {}
    player_teams: Dict[str, str] = {}

    # Innings 1: team_a batting, team_b bowling
    for batter_name, runs in innings_a_perf.get("batter_runs", {}).items():
        player_scores[batter_name] = player_scores.get(batter_name, 0) + runs
        player_teams[batter_name] = team_a_name

    for bowler_name, wickets in innings_a_perf.get("bowler_wickets", {}).items():
        runs_conceded = innings_a_perf.get("bowler_runs_conceded", {}).get(
            bowler_name, 0
        )
        score = 25 * wickets - runs_conceded
        player_scores[bowler_name] = player_scores.get(bowler_name, 0) + score
        player_teams[bowler_name] = team_b_name

    # Innings 2: team_b batting, team_a bowling
    for batter_name, runs in innings_b_perf.get("batter_runs", {}).items():
        player_scores[batter_name] = player_scores.get(batter_name, 0) + runs
        player_teams[batter_name] = team_b_name

    for bowler_name, wickets in innings_b_perf.get("bowler_wickets", {}).items():
        runs_conceded = innings_b_perf.get("bowler_runs_conceded", {}).get(
            bowler_name, 0
        )
        score = 25 * wickets - runs_conceded
        player_scores[bowler_name] = player_scores.get(bowler_name, 0) + score
        player_teams[bowler_name] = team_a_name

    if not player_scores:
        return None

    # Winning team bonus
    if winning_team is not None:
        best_player = None
        best_score = -(10**9)
        for player, base_score in player_scores.items():
            bonus = 10 if player_teams.get(player) == winning_team else 0
            total = base_score + bonus
            if total > best_score:
                best_score = total
                best_player = player
        return best_player

    return max(player_scores, key=player_scores.get)


def calculate_match_stats(
    innings_a_perf: Dict[str, Any],
    innings_b_perf: Dict[str, Any],
    team_a_name: str,
    team_b_name: str,
) -> Dict[str, Dict[str, Any]]:
    """Calculate comprehensive match statistics for all players."""
    player_stats: Dict[str, Dict[str, Any]] = {}

    # Process both innings
    for innings_perf, batting_team, bowling_team in [
        (innings_a_perf, team_a_name, team_b_name),
        (innings_b_perf, team_b_name, team_a_name),
    ]:
        # Batting stats
        for player_name in innings_perf.get("batter_runs", {}).keys():
            if player_name not in player_stats:
                player_stats[player_name] = {
                    "team": batting_team,
                    "batting": {
                        "runs": 0,
                        "balls_faced": 0,
                        "fours": 0,
                        "sixes": 0,
                        "strike_rate": 0.0,
                        "not_out": True,
                    },
                    "bowling": {
                        "overs": 0.0,
                        "runs_conceded": 0,
                        "wickets": 0,
                        "economy": 0.0,
                    },
                }
            player_stats[player_name]["batting"]["runs"] += innings_perf[
                "batter_runs"
            ].get(player_name, 0)
            player_stats[player_name]["batting"]["balls_faced"] += innings_perf.get(
                "batter_balls", {}
            ).get(player_name, 0)
            player_stats[player_name]["batting"]["fours"] += innings_perf.get(
                "batter_fours", {}
            ).get(player_name, 0)
            player_stats[player_name]["batting"]["sixes"] += innings_perf.get(
                "batter_sixes", {}
            ).get(player_name, 0)

        # Bowling stats
        for player_name in innings_perf.get("bowler_wickets", {}).keys():
            if player_name not in player_stats:
                player_stats[player_name] = {
                    "team": bowling_team,
                    "batting": {
                        "runs": 0,
                        "balls_faced": 0,
                        "fours": 0,
                        "sixes": 0,
                        "strike_rate": 0.0,
                        "not_out": True,
                    },
                    "bowling": {
                        "overs": 0.0,
                        "runs_conceded": 0,
                        "wickets": 0,
                        "economy": 0.0,
                        "balls": 0,  # Initialize balls key
                    },
                }
            player_stats[player_name]["bowling"]["wickets"] += innings_perf[
                "bowler_wickets"
            ].get(player_name, 0)
            player_stats[player_name]["bowling"]["balls"] = innings_perf.get(
                "bowler_balls", {}
            ).get(player_name, 0)
            player_stats[player_name]["bowling"]["runs_conceded"] += innings_perf.get(
                "bowler_runs_conceded", {}
            ).get(player_name, 0)

    # Calculate derived stats
    for stats in player_stats.values():
        # Batting strike rate
        if stats["batting"]["balls_faced"] > 0:
            stats["batting"]["strike_rate"] = (
                stats["batting"]["runs"] / stats["batting"]["balls_faced"]
            ) * 100

        # Bowling economy and overs (ensure balls key exists)
        balls_bowled = stats["bowling"].get("balls", 0)
        if balls_bowled > 0:
            stats["bowling"]["overs"] = balls_bowled / 6
            stats["bowling"]["economy"] = (
                stats["bowling"]["runs_conceded"] / stats["bowling"]["overs"]
            )

    return player_stats


def build_commentary(
    over_num: int,
    runs_in_over: int,
    wickets_in_over: int,
    total_runs: int,
    total_wkts: int,
    target: int | None,
    balls_bowled: int,
    max_balls: int,
) -> str:
    bits: List[str] = []

    if wickets_in_over >= 2:
        bits.append(
            f"Over {over_num}: Huge moment for the bowlers – {wickets_in_over} wickets!"
        )
    elif wickets_in_over == 1:
        bits.append(f"Over {over_num}: Breakthrough! That wicket could shift momentum.")
    elif runs_in_over >= 12:
        bits.append(
            f"Over {over_num}: Batters cut loose, big over with {runs_in_over} runs."
        )
    elif runs_in_over <= 2:
        bits.append(
            f"Over {over_num}: Tight, miserly bowling – just {runs_in_over} off it."
        )
    else:
        bits.append(f"Over {over_num}: Decent over, both sides trading punches.")

    if target is not None:
        remaining = target - total_runs
        balls_left = max_balls - balls_bowled
        if remaining > 0:
            bits.append(f"{remaining} needed from {balls_left} balls.")
        else:
            bits.append("They’ve hunted down the target in style!")

    if not bits:
        bits.append("Steady stuff, game nicely poised.")

    return " ".join(bits)


async def update_tournament_after_match(
    session,
    team_a_name: str,
    team_b_name: str,
    winner_name: str | None,
    team_a_score: str,
    team_b_score: str,
    tied: bool,
    interaction: discord.Interaction,
) -> Tuple[str | None, bool]:
    """
    Update tournament state after a match completes.

    Returns:
        Tuple of (next_match_info, tournament_complete)
    """
    # Update team stats using backend logic
    update_tournament_standings(
        team_stats=session.team_stats,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        winner_name=winner_name,
        team_a_score=team_a_score,
        team_b_score=team_b_score,
        tied=tied,
    )

    # Add match to history
    match_info = MatchInfo(
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        winner_name=winner_name,
        tied=tied,
        team_a_score=team_a_score,
        team_b_score=team_b_score,
        match_type=session.current_match.get("match_type", "League"),
    )
    session.match_history.append(match_info)

    # Increment fixture index for league matches
    if session.tournament_mode and not session.league_phase_complete:
        session.fixture_index += 1
        logger.info(
            f"Fixture {session.fixture_index}/{len(session.league_fixtures)} complete"
        )

    # Check if tournament is complete or needs next match
    num_teams = len(session.managers)

    # Determine if all league matches are done
    league_phase_complete = check_league_phase_complete(
        match_history=session.match_history,
        num_teams=num_teams,
    )

    if league_phase_complete:
        session.league_phase_complete = True

        if num_teams == 2:
            # Tournament complete
            session.tournament_stage = "Completed"
            await send_tournament_complete(interaction, session)
            return None, True
        elif num_teams <= 4:
            # Move to final
            session.tournament_stage = "Final"
            await send_league_standings(interaction, session)
            next_info = "🏆 FINAL - Top 2 teams"
            await interaction.followup.send(
                f"🏆 **League phase complete!**\nMoving to the **Final**.\n\n"
                f"Next: {next_info}\n"
                f"Click '▶️ Start Next Match' to begin."
            )
            return next_info, False
        else:
            # Move to semi-finals
            session.tournament_stage = "Semi-Final"
            await send_league_standings(interaction, session)
            next_info = "Semi-Final - Top 4 teams"
            await interaction.followup.send(
                f"🏆 **League phase complete!**\nMoving to **Semi-Finals**.\n\n"
                f"Next: {next_info}\n"
                f"Click '▶️ Start Next Match' to begin."
            )
            return next_info, False
    else:
        # More league matches to play
        total_league_matches = num_teams * (num_teams - 1) // 2
        league_matches_played = len(session.match_history)
        remaining = total_league_matches - league_matches_played
        await interaction.followup.send(
            f"✅ Match recorded!\n\n"
            f"**Standings updated.**\n"
            f"Matches played: {league_matches_played}/{total_league_matches}\n"
            f"Remaining: {remaining}\n\n"
            f"Click '▶️ Start Next Match' to continue."
        )
        return f"League Match #{league_matches_played + 1}", False


async def send_league_standings(interaction: discord.Interaction, session):
    """Send league standings embed."""
    sorted_teams = sorted(
        session.team_stats.items(),
        key=lambda x: (x[1].won, x[1].net_run_rate),
        reverse=True,
    )

    lines = ["**Tournament Standings**\n"]
    lines.append("| Pos | Team | P | W | L | T | NRR |")
    lines.append("|-----|------|---|---|---|---|-----|")

    for pos, (team_name, stats) in enumerate(sorted_teams, 1):
        lines.append(
            f"| {pos} | {team_name} | {stats.played} | {stats.won} | "
            f"{stats.lost} | {stats.tied} | {stats.net_run_rate:+.2f} |"
        )

    embed = discord.Embed(
        title="📊 League Standings",
        description="\n".join(lines),
        color=discord.Color.blue(),
    )
    await interaction.followup.send(embed=embed)


async def send_tournament_complete(interaction: discord.Interaction, session):
    """Send tournament completion message with winner."""
    # Find the winner (team with most wins)
    if session.team_stats:
        winner = max(
            session.team_stats.items(),
            key=lambda x: (x[1].won, x[1].net_run_rate),
        )

        embed = discord.Embed(
            title="🏆 Tournament Complete!",
            description=f"**Champions: {winner[0]}**",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Record",
            value=f"Won: {winner[1].won} | Lost: {winner[1].lost} | Tied: {winner[1].tied}",
            inline=True,
        )
        embed.add_field(
            name="Net Run Rate",
            value=f"{winner[1].net_run_rate:+.2f}",
            inline=True,
        )

        # Match history
        if session.match_history:
            history_lines = []
            for match in session.match_history:
                result = match.winner_name or "Tied"
                history_lines.append(
                    f"{match.team_a_name} vs {match.team_b_name}: **{result}**"
                )
            embed.add_field(
                name="Match History",
                value="\n".join(history_lines)[:1024],
                inline=False,
            )

        await interaction.followup.send(embed=embed)


class MatchSim(commands.Cog):
    """Cog wrapper so Discord loads this extension; commands are elsewhere."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MatchSim(bot))
