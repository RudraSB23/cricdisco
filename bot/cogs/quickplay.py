# bot/cogs/quickplay.py

import asyncio
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from backend.auction import quick_assign_players
from backend.match import simulate_match
from backend.models import MatchResult, Player, Team
from bot.session_state import get_session


class QuickPlay(commands.Cog):
    """Quick auto-assign + match simulation commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="quick_play",
        description="Quickly assign players and simulate a 5-over match between two managers.",
    )
    async def quick_play(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use this in a server.", ephemeral=True
            )
            return

        session = get_session(interaction.guild.id, interaction.channel.id)  # type: ignore[arg-type]

        if not session.active:
            await interaction.response.send_message(
                "No active game. Use `/start_game` first.", ephemeral=True
            )
            return

        if len(session.managers) < 2:
            await interaction.response.send_message(
                "Need at least 2 managers joined with `/join_game`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        teams = quick_assign_players(
            players=session.auction_pool,
            manager_names=session.manager_names,
            squad_size=session.squad_size,
            starting_budget=20.0,
        )
        session.teams = teams

        # Squads summary
        lines: List[str] = []
        for team in teams:
            lines.append(f"**Team {team.manager_name}** (budget: {team.budget:.1f} Cr)")
            for p in team.players:
                lines.append(f"- {p.name} ({p.role.upper()}, {p.overall_rating})")
            lines.append("")

        await interaction.followup.send("\n".join(lines) or "No teams assigned?")

        if len(teams) < 2:
            await interaction.followup.send("Need at least 2 teams to play a match.")
            return

        team_a = teams[0]
        team_b = teams[1]

        await interaction.followup.send(
            f"Simulating 5-over match between **{team_a.manager_name}** and **{team_b.manager_name}**..."
        )

        loop = asyncio.get_running_loop()
        result: MatchResult = await loop.run_in_executor(
            None, lambda: simulate_match(team_a, team_b, overs=5)
        )

        overs_a = result.team_a_result.balls / 6
        overs_b = result.team_b_result.balls / 6

        embed = discord.Embed(
            title="🏏 Match Summary",
            color=0x3498DB,
        )
        embed.add_field(
            name=team_a.manager_name,
            value=(
                f"Score: **{result.team_a_result.runs}/"
                f"{result.team_a_result.wickets}**\n"
                f"Overs: `{overs_a:.1f}`"
            ),
            inline=True,
        )
        embed.add_field(
            name=team_b.manager_name,
            value=(
                f"Score: **{result.team_b_result.runs}/"
                f"{result.team_b_result.wickets}**\n"
                f"Overs: `{overs_b:.1f}`"
            ),
            inline=True,
        )

        if result.winner is None:
            footer = "Result: Match tied."
        else:
            footer = f"Result: {result.winner} {result.margin}."

        embed.set_footer(text=footer)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QuickPlay(bot))


if __name__ == "__main__":
    # Minimal import/self-test to pinpoint import errors
    print("Running quickplay.py self-test...")
    try:
        from backend.auction import quick_assign_players
        from backend.match import simulate_match
        from backend.models import MatchResult, Player, Team
        from bot.session_state import get_session
    except Exception as e:
        print("Import error in quickplay.py:", repr(e))
