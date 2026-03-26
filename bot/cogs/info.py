# bot/cogs/info.py

import datetime

import discord
from discord import app_commands
from discord.ext import commands

CRICDISCO_GREEN = 0x57F287
CRICDISCO_BLUE = 0x3498DB


class Info(commands.Cog):
    """Basic informational commands: ping, help, about."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check if the bot is alive.")
    async def ping(self, interaction: discord.Interaction):
        # Capture response time for accurate roundtrip measurement
        response_time = datetime.datetime.now(datetime.timezone.utc)
        api_latency_ms = round(self.bot.latency * 1000)
        roundtrip_ms = int(
            (response_time - interaction.created_at).total_seconds() * 1000
        )

        embed = discord.Embed(
            title="🏓 Pong!",
            color=CRICDISCO_GREEN,
            timestamp=response_time,
        )

        embed.add_field(
            name="Roundtrip",
            value=f"```{roundtrip_ms}ms```",
            inline=True,
        )
        embed.add_field(
            name="API Latency",
            value=f"```{api_latency_ms}ms```",
            inline=True,
        )
        embed.add_field(
            name="📡 Status",
            value="```🟢 Online```",
            inline=True,
        )

        embed.set_footer(text="CricDisco • An IPL Auction Simulator")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="help",
        description="Show basic help for CricDisco commands.",
    )
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📝 CricDisco Help",
            description="Slash commands to run IPL-style auctions and mini-matches.",
            color=CRICDISCO_BLUE,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        embed.add_field(
            name="🎮 Game Flow",
            value=(
                "`/start_game` — start a new CricDisco session in this server\n"
                "`/join_game` — join the current session as a manager\n"
                "`/quick_play` — auto-assign squads and simulate a 5-over match\n"
                "`/end_game` — end the current session and clear state"
            ),
            inline=False,
        )

        embed.add_field(
            name="🛠 Utility",
            value=(
                "`/ping` — check bot latency\n"
                "`/help` — show this help embed\n"
                "`/about` — info about CricDisco"
            ),
            inline=False,
        )

        embed.set_footer(text="CricDisco • Use /start_game to begin")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="about", description="About this bot.")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏏 About CricDisco",
            color=CRICDISCO_GREEN,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        embed.add_field(
            name="What is this?",
            value=(
                "CricDisco is an IPL-style **auction and match simulator**.\n"
                "Draft squads, then play 5-over mini-matches powered by a Python engine."
            ),
            inline=False,
        )

        embed.add_field(
            name="Features (MVP)",
            value=(
                "• Console + Discord support\n"
                "• Player pool from real IPL-style data\n"
                "• Quick auto-assign squads\n"
                "• 5-over simulated matches with ball-by-ball logic"
            ),
            inline=False,
        )

        embed.set_footer(text="Built by Rudra • Backend: Python · Frontend: Discord")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))
