import os
import logging
import discord
from discord.ext import commands

from services.db import Database

ASSET_ORG_LOGO_PNG = "assets/org_logo.png"
STOCK_PRICE = 100_000
STOCK_CASHOUT_AUEC_PER_STOCK = int(os.getenv("SHARE_CASHOUT_AUEC_PER_SHARE", str(STOCK_PRICE)) or STOCK_PRICE)
FINANCE_CHANNEL_ID = int(os.getenv("FINANCE_CHANNEL_ID", "0") or "0")
SHARES_SELL_CHANNEL_ID = int(os.getenv("SHARES_SELL_CHANNEL_ID", "0") or "0")

logger = logging.getLogger(__name__)


def _logo_files():
    try:
        if os.path.exists(ASSET_ORG_LOGO_PNG):
            return [discord.File(ASSET_ORG_LOGO_PNG, filename="org_logo.png")]
    except Exception:
        logger.exception("Failed to load org logo asset: %s", ASSET_ORG_LOGO_PNG)
    return []


class StockCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    stock = discord.SlashCommandGroup("stock", "Stock market commands")

    @staticmethod
    def _cashout_embed(request_id: int, requester_id: int, stocks: int, status: str) -> discord.Embed:
        e = discord.Embed(
            title=f"🏦 CASH-OUT REQUEST • #{int(request_id)}",
            description=(
                f"**Requester:** <@{int(requester_id)}>\n"
                f"**Stocks to sell:** `{int(stocks):,}`\n"
                f"**Estimated payout:** `{int(stocks) * int(STOCK_CASHOUT_AUEC_PER_STOCK):,} aUEC`\n"
                f"**Status:** `{str(status).upper()}`"
            ),
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        e.set_thumbnail(url="attachment://org_logo.png")
        e.set_footer(text="Escrow enabled: stocks are locked until approved/rejected.")
        return e

    @stock.command(name="buy", description="Buy stocks with aUEC from your account")
    async def buy(self, ctx: discord.ApplicationContext, stocks: int):
        if stocks < 1:
            return await ctx.respond("Stocks must be at least 1.", ephemeral=True)

        cost = int(stocks) * int(STOCK_PRICE)
        try:
            await self.db.buy_shares(
                ctx.author.id,
                shares_delta=int(stocks),
                cost=int(cost),
                reference=f"buy {stocks}",
                guild_id=(ctx.guild.id if ctx.guild else None),
            )
            await self.db.record_stock_trade_metrics(
                side="buy",
                units=int(stocks),
                guild_id=(ctx.guild.id if ctx.guild else None),
            )
        except ValueError as e:
            return await ctx.respond(str(e), ephemeral=True)

        embed = discord.Embed(
            title="✅ STOCKS PURCHASED",
            description=(
                f"Purchased `{int(stocks):,}` stocks for `{int(cost):,} aUEC`.\n"
                f"Price per stock: `{int(STOCK_PRICE):,} aUEC`."
            ),
            colour=discord.Colour.green(),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")
        await ctx.respond(embed=embed, files=_logo_files(), ephemeral=True)

    @stock.command(name="sell", description="Request to cash-out by selling stocks (locks stocks until handled)")
    async def sell(self, ctx: discord.ApplicationContext, stocks: int):
        await ctx.defer(ephemeral=True)
        if stocks < 1:
            return await ctx.followup.send("Stocks must be at least 1.", ephemeral=True)

        available = await self.db.get_shares_available(ctx.author.id, guild_id=(ctx.guild.id if ctx.guild else None))
        if available < int(stocks):
            locked = await self.db.get_shares_locked(ctx.author.id, guild_id=(ctx.guild.id if ctx.guild else None))
            total = await self.db.get_shares(ctx.author.id, guild_id=(ctx.guild.id if ctx.guild else None))
            return await ctx.followup.send(
                f"Not enough **available** stocks.\nTotal: `{total:,}` | Locked: `{locked:,}` | Available: `{available:,}`",
                ephemeral=True,
            )

        try:
            await self.db.lock_shares(ctx.author.id, int(stocks), guild_id=(ctx.guild.id if ctx.guild else None))
            await self.db.record_stock_trade_metrics(
                side="sell",
                units=int(stocks),
                guild_id=(ctx.guild.id if ctx.guild else None),
            )
        except ValueError as e:
            return await ctx.followup.send(str(e), ephemeral=True)

        post_channel: discord.abc.MessageableChannel = ctx.channel
        target_channel_id = SHARES_SELL_CHANNEL_ID or FINANCE_CHANNEL_ID
        if target_channel_id and ctx.guild:
            ch = ctx.guild.get_channel(target_channel_id)
            if ch:
                post_channel = ch

        placeholder = discord.Embed(
            title="Creating cash-out request…",
            description="Please wait.",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        msg = await post_channel.send(embed=placeholder, files=_logo_files())

        request_id = await self.db.create_cashout_request(
            guild_id=ctx.guild.id if ctx.guild else 0,
            channel_id=msg.channel.id,
            message_id=msg.id,
            requester_id=ctx.author.id,
            shares=int(stocks),
        )

        thread = await msg.create_thread(
            name=f"Cash-out #{request_id} — {ctx.author.display_name}",
            auto_archive_duration=1440,
        )
        await self.db.set_cashout_thread(request_id, thread.id, guild_id=(ctx.guild.id if ctx.guild else None))

        embed = self._cashout_embed(request_id, ctx.author.id, int(stocks), "pending")

        view = getattr(self.bot, "cashout_view", None)
        if view is None:
            await msg.edit(embed=embed, view=None, files=_logo_files())
        else:
            await msg.edit(embed=embed, view=view, files=_logo_files())

        payout_amount = int(stocks) * int(STOCK_CASHOUT_AUEC_PER_STOCK)
        treasury_amount = await self.db.get_treasury(guild_id=(ctx.guild.id if ctx.guild else None))
        warn = ""
        if treasury_amount < payout_amount:
            warn = f"\n\n⚠️ Treasury currently: `{treasury_amount:,} aUEC` (below estimated payout `{payout_amount:,} aUEC`)."

        await ctx.followup.send(
            f"Cash-out request **#{request_id}** created. Your `{int(stocks):,}` stocks are now **locked** until handled.\n"
            f"Estimated payout: `{payout_amount:,} aUEC`{warn}",
            ephemeral=True,
        )

    @stock.command(name="portfolio", description="View your stock holdings and account balance")
    async def portfolio(self, ctx: discord.ApplicationContext):
        gid = (ctx.guild.id if ctx.guild else None)
        bal = await self.db.get_balance(ctx.author.id, guild_id=gid)
        total = await self.db.get_shares(ctx.author.id, guild_id=gid)
        locked = await self.db.get_shares_locked(ctx.author.id, guild_id=gid)
        available = await self.db.get_shares_available(ctx.author.id, guild_id=gid)
        pending_bonds_count, pending_bonds_total = await self.db.get_user_outstanding_bonds(ctx.author.id, guild_id=gid)

        embed = discord.Embed(
            title="📈 STOCK PORTFOLIO",
            description=f"**Member:** {ctx.author.mention}",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")
        embed.add_field(name="Account Balance", value=f"`{int(bal):,} aUEC`", inline=True)
        embed.add_field(name="Stocks (Total)", value=f"`{int(total):,}`", inline=True)
        embed.add_field(name="Stocks (Available)", value=f"`{int(available):,}`", inline=True)
        embed.add_field(name="Stocks (Locked)", value=f"`{int(locked):,}`", inline=True)
        embed.add_field(name="Pending Bonds", value=f"`{int(pending_bonds_count):,}`", inline=True)
        embed.add_field(name="Outstanding Bonds", value=f"`{int(pending_bonds_total):,} aUEC`", inline=True)
        embed.set_footer(text=f"Reference stock price: {int(STOCK_PRICE):,} aUEC")

        await ctx.respond(embed=embed, files=_logo_files(), ephemeral=True)


def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    bot.add_cog(StockCog(bot, db))
