# bot/logging_config.py
"""Centralized logging configuration for CricDisco bot."""

import logging
import traceback
from functools import wraps

import discord

# Create a shared logger for all cogs
logger = logging.getLogger("CricDisco")
logger.setLevel(logging.INFO)


def get_cog_logger(cog_name: str) -> logging.Logger:
    """Get a logger instance prefixed with cog name."""
    return logging.getLogger(f"CricDisco.{cog_name}")


def log_command_errors(cog_name: str):
    """
    Decorator to log errors in app commands.

    Usage:
        @log_command_errors("QuickPlay")
        async def quickplay(self, interaction: discord.Interaction):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cog_logger = get_cog_logger(cog_name)
            try:
                return await func(*args, **kwargs)
            except discord.errors.InteractionResponded as e:
                cog_logger.warning(
                    f"Interaction already responded in {func.__name__}: {e}"
                )
                raise
            except Exception as e:
                cog_logger.error(f"Error in {func.__name__}:")
                cog_logger.error(f"  Type: {type(e).__name__}")
                cog_logger.error(f"  Message: {e}")
                cog_logger.error(f"  Traceback:\n{traceback.format_exc()}")

                # Try to send error message to user if interaction exists
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        try:
                            if interaction.response.is_done():
                                await interaction.followup.send(
                                    f"❌ **Error**: {type(e).__name__}\n"
                                    f"```\n{str(e)[:1000]}\n```",
                                    ephemeral=True,
                                )
                            else:
                                await interaction.response.send_message(
                                    f"❌ **Error**: {type(e).__name__}\n"
                                    f"```\n{str(e)[:1000]}\n```",
                                    ephemeral=True,
                                )
                        except Exception as send_error:
                            cog_logger.error(
                                f"Failed to send error message: {send_error}"
                            )
                raise

        return wrapper

    return decorator


def log_view_errors(cog_name: str):
    """
    Decorator to log errors in View callbacks (buttons, selects, etc.).

    Usage:
        @log_view_errors("MatchSim")
        async def view_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cog_logger = get_cog_logger(cog_name)
            try:
                return await func(*args, **kwargs)
            except discord.errors.InteractionResponded as e:
                cog_logger.warning(
                    f"Interaction already responded in {func.__name__}: {e}"
                )
                raise
            except Exception as e:
                cog_logger.error(f"Error in View callback {func.__name__}:")
                cog_logger.error(f"  Type: {type(e).__name__}")
                cog_logger.error(f"  Message: {e}")
                cog_logger.error(f"  Traceback:\n{traceback.format_exc()}")

                # Try to send error message to user
                for arg in args:
                    if isinstance(arg, discord.Interaction):
                        interaction = arg
                        try:
                            if interaction.response.is_done():
                                await interaction.followup.send(
                                    f"❌ **Button Error**: {type(e).__name__}\n"
                                    f"```\n{str(e)[:500]}\n```",
                                    ephemeral=True,
                                )
                            else:
                                await interaction.response.send_message(
                                    f"❌ **Button Error**: {type(e).__name__}\n"
                                    f"```\n{str(e)[:500]}\n```",
                                    ephemeral=True,
                                )
                        except Exception as send_error:
                            cog_logger.error(
                                f"Failed to send error message: {send_error}"
                            )
                raise

        return wrapper

    return decorator


def log_event_errors(cog_name: str):
    """
    Decorator to log errors in event handlers.

    Usage:
        @log_event_errors("Session")
        async def on_join_game(self, interaction: discord.Interaction):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cog_logger = get_cog_logger(cog_name)
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                cog_logger.error(f"Error in event {func.__name__}:")
                cog_logger.error(f"  Type: {type(e).__name__}")
                cog_logger.error(f"  Message: {e}")
                cog_logger.error(f"  Traceback:\n{traceback.format_exc()}")
                raise

        return wrapper

    return decorator
