# bot/cogs/auction.py

import discord
from discord import app_commands
from discord.ext import commands


class Auction(commands.Cog):
    """Placeholder auction cog; real implementation coming later."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="auction_wip",
        description="Auction system is under construction.",
    )
    async def auction_wip(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Auction system is not implemented yet. Stay tuned!", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Auction(bot))
