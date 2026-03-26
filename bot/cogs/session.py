# bot/cogs/session.py

import discord
from discord import app_commands
from discord.ext import commands

from backend.data import load_players, select_auction_pool
from bot.session_state import clear_session, get_session


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
            await interaction.response.send_message(
                "Use this in a server, not in DMs.", ephemeral=True
            )
            return

        session = get_session(interaction.guild.id, interaction.channel.id)  # type: ignore[arg-type]

        if session.active:
            await interaction.response.send_message(
                "A game is already active in this server. Use `/end_game` to reset.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        players = load_players("assets/unified_players.json")
        pool = select_auction_pool(players, n=pool_size, method="top")

        session.players = players
        session.auction_pool = pool
        session.teams = []
        session.managers = []
        session.manager_names = []
        session.active = True
        session.squad_size = squad_size

        await interaction.followup.send(
            f"New CricDisco session started!\n"
            f"- Pool size: **{pool_size}**\n"
            f"- Squad size: **{squad_size}**\n\n"
            f"Managers, use `/join_game` to join."
        )

    @app_commands.command(
        name="join_game",
        description="Join the current CricDisco session as a manager.",
    )
    async def join_game(self, interaction: discord.Interaction):
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

        if interaction.user.id in session.managers:
            await interaction.response.send_message(
                "You are already a manager in this session.", ephemeral=True
            )
            return

        if len(session.managers) >= 4:
            await interaction.response.send_message(
                "Maximum 4 managers reached.", ephemeral=True
            )
            return

        session.managers.append(interaction.user.id)
        session.manager_names.append(interaction.user.display_name)

        await interaction.response.send_message(
            f"{interaction.user.mention} joined as manager #{len(session.managers)}.",
            ephemeral=False,
        )

    @app_commands.command(
        name="end_game",
        description="End the current CricDisco session and clear state.",
    )
    async def end_game(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use this in a server.", ephemeral=True
            )
            return

        clear_session(interaction.guild.id)
        await interaction.response.send_message(
            "CricDisco session ended and state cleared."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Session(bot))
