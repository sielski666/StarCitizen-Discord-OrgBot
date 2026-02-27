import os
import signal
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

from services.db import Database
from cogs.jobs import JobsCog, JobWorkflowView
from cogs.account import AccountCog, CashoutPersistentView
from cogs.treasury import TreasuryCog
from cogs.finance import FinanceCog  # ✅ make sure this exists now
from cogs.setup import SetupCog
from cogs.bond import BondCog
from cogs.stock import StockCog

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
if hasattr(intents, "guild_scheduled_events"):
    intents.guild_scheduled_events = True

bot = commands.Bot(command_prefix="!", intents=intents)

db = Database()
bot.db = db  # ✅ so cogs can access bot.db if they use that pattern


@bot.event
async def on_connect():
    if db.conn is None:
        await db.connect()
        print("Database connected (bot.db created/ready).")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Persistent views (cashouts + jobs)
    if not hasattr(bot, "cashout_view"):
        bot.cashout_view = CashoutPersistentView(db)  # type: ignore
        bot.add_view(bot.cashout_view)  # type: ignore
        print("Registered CashoutPersistentView.")

    if not hasattr(bot, "job_workflow_registered"):
        bot.add_view(JobWorkflowView(db, status="open"))  # type: ignore
        bot.job_workflow_registered = True  # type: ignore
        print("Registered JobWorkflowView.")

    # Multi-guild: sync app commands into every connected guild for immediate availability.
    guild_ids = [int(g.id) for g in bot.guilds]
    if guild_ids:
        await bot.sync_commands(guild_ids=guild_ids)
        print(f"Synced slash commands to guilds: {guild_ids}")
    elif GUILD_ID != 0:
        # Legacy fallback when guild cache is empty.
        await bot.sync_commands(guild_ids=[GUILD_ID])
        print(f"Synced slash commands to fallback guild {GUILD_ID}")


@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        await bot.sync_commands(guild_ids=[int(guild.id)])
        print(f"Synced slash commands on guild join: {guild.id}")
    except Exception as e:
        print(f"Failed to sync commands on guild join {guild.id}: {e}")


# Register cogs
bot.add_cog(JobsCog(bot, db))
bot.add_cog(AccountCog(bot, db))
bot.add_cog(TreasuryCog(bot, db))
bot.add_cog(FinanceCog(bot, db))  # ✅ finance dashboard
bot.add_cog(BondCog(bot, db))
bot.add_cog(StockCog(bot, db))
bot.add_cog(SetupCog(bot))


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing in .env")




if __name__ == "__main__":
    bot.run(TOKEN)
