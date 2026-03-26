# bot/cogs/management.py

import discord
from discord import app_commands
from discord.ext import commands


def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        # Simple owner check; change to your Discord user ID if you want it stricter
        app_owner = (await interaction.client.application_info()).owner
        if interaction.user.id != app_owner.id:
            await interaction.response.send_message(
                "You are not allowed to use this command.",
                ephemeral=True,
            )
            return False
        return True

    return app_commands.check(predicate)


class Management(commands.Cog):
    """Bot management commands: reload cogs, list cogs, etc."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="list_cogs",
        description="List all currently loaded cogs (extensions).",
    )
    @is_owner()
    async def list_cogs(self, interaction: discord.Interaction):
        exts = sorted(self.bot.extensions.keys())
        if not exts:
            await interaction.response.send_message(
                "No extensions loaded.", ephemeral=True
            )
            return

        text = "\n".join(f"- `{name}`" for name in exts)
        await interaction.response.send_message(
            f"**Loaded extensions:**\n{text}", ephemeral=True
        )

    @app_commands.command(
        name="reload",
        description="Reload a specific cog/extension by name.",
    )
    @app_commands.describe(
        module="Extension module, e.g. 'bot.cogs.info' or just 'info'"
    )
    @is_owner()
    async def reload(self, interaction: discord.Interaction, module: str):
        # Allow short names like "info"
        if not module.startswith("bot.cogs."):
            module = f"bot.cogs.{module}"

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            # If not already loaded, load; else reload
            if module in self.bot.extensions:
                await self.bot.reload_extension(module)
                action = "reloaded"
            else:
                await self.bot.load_extension(module)
                action = "loaded"

            await interaction.followup.send(
                f"Extension `{module}` {action} successfully.",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"Failed to reload `{module}`:\n```{e}```",
                ephemeral=True,
            )

    @app_commands.command(
        name="reload_all",
        description="Reload all bot cogs/extensions.",
    )
    @is_owner()
    async def reload_all(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        failed: list[str] = []
        reloaded: list[str] = []

        # Copy keys to list to avoid size-change issues
        for module in list(self.bot.extensions.keys()):
            if module == "bot.cogs.management":
                continue
            try:
                await self.bot.reload_extension(module)
                reloaded.append(module)
            except Exception as e:
                failed.append(f"{module} -> {e}")

        msg = ""
        if reloaded:
            msg += "**Reloaded:**\n" + "\n".join(f"- `{m}`" for m in reloaded) + "\n\n"
        if failed:
            msg += "**Failed:**\n" + "\n".join(f"- `{m}`" for m in failed)
        if not msg:
            msg = "No extensions to reload."

        await interaction.followup.send(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Management(bot))
