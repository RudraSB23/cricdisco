import asyncio
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import discord
from auction import display_squads, quick_assign_players, run_auction
from data import load_players, select_auction_pool
from discord import app_commands
from discord.ext import commands
from match import simulate_match
from models import Player, Team

GUILD_SESSIONS: Dict[int, "GameSession"] = {}  # guild_id -> GameSession


@dataclass
class GameSession:
    guild_id: int
    channel_id: int
    players: List[Player] = field(default_factory=list)
    auction_pool: List[Player] = field(default_factory=list)
    teams: List[Team] = field(default_factory=list)
    managers: List[int] = field(default_factory=list)  # discord user IDs
    manager_names: List[str] = field(default_factory=list)
    active: bool = False


intents = discord.Intents.default()
intents.message_content = False  # slash commands, no prefix needed

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
