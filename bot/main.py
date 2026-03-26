# bot/main.py

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output for different log levels."""

    COLORS = {
        logging.DEBUG: "\x1b[36m",  # Cyan
        logging.INFO: "\x1b[32m",  # Green
        logging.WARNING: "\x1b[33m",  # Yellow
        logging.ERROR: "\x1b[31m",  # Red
        logging.CRITICAL: "\x1b[35m",  # Magenta
    }
    RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        levelname = f"{color}{record.levelname}{self.RESET}"
        record_copy = record.__dict__.copy()
        record_copy["levelname"] = levelname
        return super().format(logging.makeLogRecord(record_copy))


# Configure logging with colors
logger = logging.getLogger("CricDisco")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(
    ColoredFormatter(
        fmt="[%(asctime)s] %(levelname)s : %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
logger.addHandler(handler)

# Add project root to sys.path so bot.cogs can be imported
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents)

load_dotenv()


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} application commands.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")


async def load_cogs():
    print(f"\n{'-' * 33} LOADING COGS {'-' * 33}")
    cogs_dir = ROOT / "bot" / "cogs"

    for path in cogs_dir.glob("*.py"):
        if path.name.startswith("_"):
            continue
        module_name = f"bot.cogs.{path.stem}"
        try:
            await bot.load_extension(module_name)
            logger.info(f"LOADED: {module_name}")
        except Exception as e:
            logger.error(f"FAILED: {module_name}: {e}")

    print(f"{'-' * 80}\n")


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN not set")

    async def runner():
        await load_cogs()
        await bot.start(token)

    asyncio.run(runner())


if __name__ == "__main__":
    main()
