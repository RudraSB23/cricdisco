# bot/cogs/quickplay.py

from __future__ import annotations

from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from backend.auction import quick_assign_players
from backend.models import Team
from backend.tournament import TournamentBracket
from bot.cogs import match_sim  # adjust import if your package path is different
from bot.logging_config import get_cog_logger, log_command_errors, log_view_errors
from bot.session_state import MatchInfo, TeamStats, get_session

logger = get_cog_logger("QuickPlay")


class QuickPlay(commands.Cog):
    """Quick auto-assign + start tournament simulation."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="quickplay",
        description="Start a tournament with auto-assigned players.",
    )
    @app_commands.describe(
        overs="Number of overs per innings (default: 5, max: 20)",
    )
    async def quickplay(
        self,
        interaction: discord.Interaction,
        overs: app_commands.Range[int, 1, 20] = 5,
    ):
        if interaction.guild is None:
            embed = discord.Embed(
                title="CricDisco • Error",
                description="Use this command in a server.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        session = get_session(interaction.guild.id, interaction.channel.id)  # type: ignore[arg-type]

        if not session.active:
            embed = discord.Embed(
                title="CricDisco • No Active Session",
                description="No active game. Use `/start_game` first.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if len(session.managers) < 2:
            embed = discord.Embed(
                title="CricDisco • Not Enough Managers",
                description="Need at least 2 managers joined with `/join_game`.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if session.owner_id is None or interaction.user.id != session.owner_id:
            embed = discord.Embed(
                title="CricDisco • Permission Denied",
                description="Only the organiser who ran `/start_game` can start quick play.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Defer with ephemeral=False so we can send public followups
        await interaction.response.defer(ephemeral=False, thinking=True)

        try:
            # Auto-assign squads
            teams: List[Team] = quick_assign_players(
                players=session.auction_pool,
                manager_names=session.team_names,
                squad_size=session.squad_size,
                starting_budget=20.0,
                manager_ids=session.managers,
                balance_roles=True,
            )
            session.teams = teams

            # Initialize tournament
            num_teams = len(teams)
            session.tournament_mode = True
            session.tournament_stage = "Final" if num_teams == 2 else "League"

            # Generate league fixtures (round-robin)
            session.league_fixtures = []
            session.fixture_index = 0
            team_name_list = [t.manager_name for t in teams]

            # Generate all unique pairings for round-robin
            for i in range(len(team_name_list)):
                for j in range(i + 1, len(team_name_list)):
                    session.league_fixtures.append(
                        {
                            "team_a": team_name_list[i],
                            "team_b": team_name_list[j],
                        }
                    )

            logger.info(
                f"Generated {len(session.league_fixtures)} league fixtures for {num_teams} teams"
            )

            # Initialize team stats
            for team in teams:
                session.team_stats[team.manager_name] = TeamStats(
                    team_name=team.manager_name,
                    manager_id=team.manager_id or 0,
                )

            # Squads embed
            embed_squads = discord.Embed(
                title="🧢 Tournament Started",
                description=f"**{num_teams} teams** competing in a tournament.\nFormat: {self._get_format_info(num_teams)}",
                color=discord.Color.blurple(),
            )

            for team in teams:
                # Count roles
                role_counts = {"wk": 0, "bat": 0, "ar": 0, "bowl": 0}
                for p in team.players:
                    role = p.role.lower()
                    if role in ["wk", "wicket-keeper", "wicketkeeper"]:
                        role_counts["wk"] += 1
                    elif role in ["bat", "batsman", "batter"]:
                        role_counts["bat"] += 1
                    elif role in ["ar", "all-rounder", "allrounder"]:
                        role_counts["ar"] += 1
                    elif role in ["bowl", "bowler"]:
                        role_counts["bowl"] += 1

                role_summary = f"🏏 {role_counts['bat']} | 🧤 {role_counts['wk']} | ⚡ {role_counts['ar']} | 🎯 {role_counts['bowl']}"

                value_lines = [
                    f"- {p.name} ({p.role.upper()}, {p.overall_rating})"
                    for p in team.players
                ]
                embed_squads.add_field(
                    name=f"🏏 {team.manager_name}\n{role_summary}",
                    value="\n".join(value_lines)[:1024] or "`No players`",
                    inline=False,
                )

            await interaction.followup.send(embed=embed_squads)

            if len(teams) < 2:
                embed_err = discord.Embed(
                    title="CricDisco • Not Enough Teams",
                    description="Need at least 2 teams to play a match.",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed_err)
                return

            # Start first match
            await self._start_next_match(
                interaction=interaction,
                teams=teams,
                overs=overs,
                session=session,
            )

        except Exception as e:
            import traceback

            error_msg = f"```\n{traceback.format_exc()}\n```"
            error_embed = discord.Embed(
                title="❌ Error Starting Tournament",
                description=f"An error occurred:\n{error_msg}",
                color=discord.Color.red(),
            )
            try:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except:
                # If followup fails, the defer might have failed
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )

    def _get_format_info(self, num_teams: int) -> str:
        """Get tournament format description."""
        if num_teams == 2:
            return "Direct Final (1 match)"
        elif num_teams <= 4:
            return "League phase + Final"
        else:
            return "League phase + Semi-Finals + Final"

    async def _start_next_match(
        self,
        interaction: discord.Interaction,
        teams: List[Team],
        overs: int,
        session,
    ):
        """Start the next match in the tournament."""
        try:
            num_teams = len(teams)

            # Check if we're in knockout phase
            if session.league_phase_complete:
                if session.tournament_stage == "Final":
                    # Get top 2 teams from standings
                    sorted_teams = sorted(
                        session.team_stats.items(),
                        key=lambda x: (x[1].won, x[1].net_run_rate),
                        reverse=True,
                    )
                    top_2_names = [sorted_teams[0][0], sorted_teams[1][0]]

                    # Find Team objects for top 2
                    team_a = next(
                        (t for t in teams if t.manager_name == top_2_names[0]), teams[0]
                    )
                    team_b = next(
                        (t for t in teams if t.manager_name == top_2_names[1]), teams[1]
                    )
                    match_type = "Final"

                    # Announce finalists
                    finalists_embed = discord.Embed(
                        title="🏆 FINAL",
                        description=f"**{team_a.manager_name}** vs **{team_b.manager_name}**",
                        color=discord.Color.gold(),
                    )
                    finalists_embed.add_field(
                        name="League Position",
                        value=f"1st: {team_a.manager_name}\n2nd: {team_b.manager_name}",
                        inline=False,
                    )
                    await interaction.followup.send(embed=finalists_embed)

                elif session.tournament_stage == "Semi-Final":
                    # Get top 4 teams for semi-finals
                    sorted_teams = sorted(
                        session.team_stats.items(),
                        key=lambda x: (x[1].won, x[1].net_run_rate),
                        reverse=True,
                    )
                    # SF1: 1st vs 4th, SF2: 2nd vs 3rd
                    # For now, just pick 1st vs 4th
                    top_4_names = [
                        sorted_teams[i][0] for i in range(min(4, len(sorted_teams)))
                    ]
                    team_a = next(
                        (t for t in teams if t.manager_name == top_4_names[0]), teams[0]
                    )
                    team_b = (
                        next(
                            (t for t in teams if t.manager_name == top_4_names[3]),
                            teams[3],
                        )
                        if len(top_4_names) > 3
                        else teams[1]
                    )
                    match_type = "Semi-Final 1"
                else:
                    team_a = teams[0]
                    team_b = teams[1]
                    match_type = "League"
            else:
                # League phase - use fixture schedule
                if num_teams == 2:
                    team_a = teams[0]
                    team_b = teams[1]
                    match_type = "Final"
                else:
                    # Get next fixture from schedule
                    if session.fixture_index < len(session.league_fixtures):
                        fixture = session.league_fixtures[session.fixture_index]
                        team_a_name = fixture["team_a"]
                        team_b_name = fixture["team_b"]

                        # Find Team objects
                        team_a = next(
                            (t for t in teams if t.manager_name == team_a_name),
                            teams[0],
                        )
                        team_b = next(
                            (t for t in teams if t.manager_name == team_b_name),
                            teams[1],
                        )
                        match_type = "League"

                        logger.info(
                            f"League fixture {session.fixture_index + 1}/{len(session.league_fixtures)}: "
                            f"{team_a_name} vs {team_b_name}"
                        )
                    else:
                        # All fixtures played, move to knockout
                        session.league_phase_complete = True
                        logger.info(
                            "All league fixtures complete, moving to knockout phase"
                        )

                        if num_teams <= 4:
                            session.tournament_stage = "Final"
                        else:
                            session.tournament_stage = "Semi-Final"

                        # Recursively call to start knockout phase
                        await self._start_next_match(
                            interaction=interaction,
                            teams=teams,
                            overs=overs,
                            session=session,
                        )
                        return

            # Store current match info
            session.current_match = {
                "team_a": team_a,
                "team_b": team_b,
                "overs": overs,
                "match_type": match_type,
            }

            # Send match announcement (if not already sent for Final)
            if not (
                session.league_phase_complete and session.tournament_stage == "Final"
            ):
                match_embed = discord.Embed(
                    title=f"🏆 Tournament {match_type}",
                    description=f"**{team_a.manager_name}** vs **{team_b.manager_name}**",
                    color=discord.Color.gold(),
                )
                match_embed.add_field(
                    name="Format",
                    value=f"{overs} overs per innings",
                    inline=True,
                )
                match_embed.add_field(
                    name="Stage",
                    value=session.tournament_stage or "League",
                    inline=True,
                )

                await interaction.followup.send(embed=match_embed)

            # Start toss for this match
            await match_sim.start_toss_for_channel(
                interaction=interaction,
                team_a=team_a,
                team_b=team_b,
                overs=overs,
            )
        except Exception as e:
            import traceback

            error_embed = discord.Embed(
                title="❌ Error Starting Match",
                description=f"```\n{traceback.format_exc()}\n```",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QuickPlay(bot))
