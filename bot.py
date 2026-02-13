import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from services.db import Database
from cogs.jobs import JobsCog, JobAcceptPersistentView
from cogs.account import AccountCog, CashoutPersistentView
from cogs.treasury import TreasuryCog
from cogs.finance import FinanceCog  # ✅ make sure this exists now

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

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

    if not hasattr(bot, "job_accept_view"):
        bot.job_accept_view = JobAcceptPersistentView(db)  # type: ignore
        bot.add_view(bot.job_accept_view)  # type: ignore
        print("Registered JobAcceptPersistentView.")

    if GUILD_ID != 0:
        await bot.sync_commands(guild_ids=[GUILD_ID])
        print(f"Synced slash commands to guild {GUILD_ID}")


# Register cogs
bot.add_cog(JobsCog(bot, db))
bot.add_cog(AccountCog(bot, db))
bot.add_cog(TreasuryCog(bot, db))
bot.add_cog(FinanceCog(bot, db))  # ✅ finance dashboard


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing in .env")

bot.run(TOKEN)
