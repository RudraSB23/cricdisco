# bot/cogs/session.py

import discord
from discord import app_commands
from discord.ext import commands

from backend.data import load_players, select_auction_pool
from bot.logging_config import get_cog_logger
from bot.session_state import clear_session, get_session

logger = get_cog_logger("Session")


class Session(commands.Cog):
    """Game session management: start, join, end."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="start_game",
        description="Start a new CricDisco session in this server.",
    )
    @app_commands.describe(
        pool_size="Number of players in auction pool",
        squad_size="Squad size per manager",
    )
    async def start_game(
        self,
        interaction: discord.Interaction,
        pool_size: int = 30,
        squad_size: int = 6,
    ):
        if interaction.guild is None:
            embed = discord.Embed(
                title="CricDisco • Error",
                description="Use this command in a server, not in DMs.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        session = get_session(interaction.guild.id, interaction.channel.id)  # type: ignore[arg-type]

        if session.active:
            embed = discord.Embed(
                title="CricDisco • Session Active",
                description=(
                    "A game is already active in this channel.\n"
                    "Use `/end_game` to reset the session."
                ),
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Make the thinking stage non-ephemeral so final message is public
        await interaction.response.defer(ephemeral=False, thinking=True)

        try:
            players = load_players("backend/assets/unified_players.json")
            pool = select_auction_pool(players, n=pool_size, method="top")

            session.players = players
            session.auction_pool = pool
            session.teams = []
            session.managers = []
            session.team_names = []
            session.active = True
            session.squad_size = squad_size
            session.owner_id = interaction.user.id  # organiser

            embed = discord.Embed(
                title="CricDisco Session Started",
                description="A new CricDisco session has been created in this channel.",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Organiser",
                value=interaction.user.mention,
                inline=False,
            )
            embed.add_field(
                name="Pool size",
                value=str(pool_size),
                inline=True,
            )
            embed.add_field(
                name="Squad size",
                value=str(squad_size),
                inline=True,
            )
            embed.add_field(
                name="Next steps",
                value=(
                    "Managers, use `/join_game` to join this session.\n"
                    "**Tournament Mode**: Supports 2-6 teams.\n"
                    "• 2 teams: Direct Final\n"
                    "• 3-4 teams: League + Final\n"
                    "• 5-6 teams: League + Semi-Finals + Final"
                ),
                inline=False,
            )

            # This is already non-ephemeral
            await interaction.followup.send(embed=embed, ephemeral=False)

        except Exception as e:
            logger.error(f"[start_game] ERROR: {type(e).__name__}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            embed = discord.Embed(
                title="CricDisco • Error",
                description=f"Failed to start game.\n`{type(e).__name__}: {e}`",
                color=discord.Color.red(),
            )
            # Error can stay ephemeral or public; keeping it private here
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="join_game",
        description="Join the current CricDisco session as a manager.",
    )
    @app_commands.describe(
        team_name="Your team name (e.g., 'Mumbai Titans', 'Chennai Kings')",
    )
    async def join_game(
        self,
        interaction: discord.Interaction,
        team_name: str,
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
                description="There is no active game in this channel.\nUse `/start_game` first.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if interaction.user.id in session.managers:
            embed = discord.Embed(
                title="CricDisco • Already Joined",
                description="You are already a manager in this session.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if len(session.managers) >= 6:
            embed = discord.Embed(
                title="CricDisco • Lobby Full",
                description=(
                    "Maximum of 6 managers has been reached for this session.\n\n"
                    "**Tournament Mode:**\n"
                    "• 2 teams: Direct Final\n"
                    "• 3-4 teams: League + Final\n"
                    "• 5-6 teams: League + Semi-Finals + Final"
                ),
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        session.managers.append(interaction.user.id)
        session.team_names.append(team_name)

        # Determine tournament info based on number of teams
        num_teams = len(session.managers)
        if num_teams == 2:
            format_info = "Direct Final (1 match)"
        elif num_teams in [3, 4]:
            format_info = "League phase + Final"
        else:
            format_info = "League phase + Semi-Finals + Final"

        embed = discord.Embed(
            title="CricDisco • Manager Joined",
            description=(
                f"{interaction.user.mention} joined as **{team_name}** "
                f"(Manager #{num_teams})."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Tournament Format",
            value=format_info,
            inline=False,
        )
        if session.owner_id is not None:
            embed.set_footer(
                text="Organiser can start the tournament with /quickplay when ready."
            )

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(
        name="end_game",
        description="End the current CricDisco session and clear state.",
    )
    async def end_game(self, interaction: discord.Interaction):
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
                description="There is no active game to end in this channel.",
                color=discord.Color.orange(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if session.owner_id is not None and interaction.user.id != session.owner_id:
            embed = discord.Embed(
                title="CricDisco • Permission Denied",
                description="Only the organiser who ran `/start_game` can end this session.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        clear_session(interaction.guild.id)

        embed = discord.Embed(
            title="CricDisco Session Ended",
            description=f"Session ended and state cleared by {interaction.user.mention}.",
            color=discord.Color.dark_red(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Session(bot))
