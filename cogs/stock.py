import os
import logging
import discord
from discord.ext import commands

from services.db import Database
from services.permissions import is_finance_or_admin

ASSET_ORG_LOGO_PNG = "assets/org_logo.png"
DEFAULT_STOCK_PRICE = 100_000
STOCK_CASHOUT_AUEC_PER_STOCK = int(os.getenv("SHARE_CASHOUT_AUEC_PER_SHARE", str(DEFAULT_STOCK_PRICE)) or DEFAULT_STOCK_PRICE)
FINANCE_CHANNEL_ID = int(os.getenv("FINANCE_CHANNEL_ID", "0") or "0")
SHARES_SELL_CHANNEL_ID = int(os.getenv("SHARES_SELL_CHANNEL_ID", "0") or "0")

logger = logging.getLogger(__name__)


def finance_or_admin():
    async def predicate(ctx: discord.ApplicationContext):
        return isinstance(ctx.author, discord.Member) and is_finance_or_admin(ctx.author)
    return commands.check(predicate)



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


    async def _get_live_stock_price(self, guild_id: int | None = None) -> int:
        state = await self.db.get_stock_price_state(guild_id=guild_id)
        price = int(state.get("current_price") or 0)
        if price > 0:
            return int(price)

        cfg = await self.db.get_stock_market_config(guild_id=guild_id)
        base = int(cfg.get("base_price") or DEFAULT_STOCK_PRICE)
        await self.db.set_stock_price_state(guild_id=guild_id, current_price=int(base), day_open_price=int(base), day_high_price=int(base), day_low_price=int(base))
        return int(base)

    async def _reprice_from_metrics(self, guild_id: int | None = None) -> tuple[int, int, int]:
        cfg = await self.db.get_stock_market_config(guild_id=guild_id)
        state = await self.db.get_stock_price_state(guild_id=guild_id)
        metrics = await self.db.get_stock_trade_metrics(guild_id=guild_id)

        current = int(state.get("current_price") or cfg.get("base_price") or DEFAULT_STOCK_PRICE)
        day_open = int(state.get("day_open_price") or current)
        net_units = int(metrics.get("net_units_24h") or 0)

        sensitivity_bps = int(cfg.get("demand_sensitivity_bps") or 50)
        cap_bps = max(0, int(cfg.get("daily_move_cap_bps") or 500))
        step_units = 100
        demand_steps = int(net_units // step_units)
        demand_bps = max(-cap_bps, min(cap_bps, demand_steps * sensitivity_bps))

        raw_price = int(round(current * (10000 + demand_bps) / 10000))

        min_price = int(cfg.get("min_price") or 1)
        max_price = int(cfg.get("max_price") or 10**12)

        day_floor = int(round(day_open * (10000 - cap_bps) / 10000))
        day_ceiling = int(round(day_open * (10000 + cap_bps) / 10000))

        lower = max(min_price, day_floor)
        upper = min(max_price, day_ceiling)
        if lower > upper:
            lower, upper = upper, lower

        new_price = min(max(raw_price, lower), upper)

        await self.db.set_stock_price_state(guild_id=guild_id, current_price=int(new_price))
        return int(current), int(new_price), int(demand_bps)

    async def _manual_price_adjust_bps(self, delta_bps: int, guild_id: int | None = None) -> tuple[int, int]:
        cfg = await self.db.get_stock_market_config(guild_id=guild_id)
        state = await self.db.get_stock_price_state(guild_id=guild_id)
        current = int(state.get("current_price") or cfg.get("base_price") or DEFAULT_STOCK_PRICE)
        day_open = int(state.get("day_open_price") or current)

        cap_bps = max(0, int(cfg.get("daily_move_cap_bps") or 500))
        min_price = int(cfg.get("min_price") or 1)
        max_price = int(cfg.get("max_price") or 10**12)

        bounded_delta = max(-cap_bps, min(cap_bps, int(delta_bps)))
        raw_price = int(round(current * (10000 + bounded_delta) / 10000))

        day_floor = int(round(day_open * (10000 - cap_bps) / 10000))
        day_ceiling = int(round(day_open * (10000 + cap_bps) / 10000))

        lower = max(min_price, day_floor)
        upper = min(max_price, day_ceiling)
        if lower > upper:
            lower, upper = upper, lower

        new_price = min(max(raw_price, lower), upper)
        await self.db.set_stock_price_state(guild_id=guild_id, current_price=int(new_price))
        return int(current), int(new_price)

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

        live_price = await self._get_live_stock_price(guild_id=(ctx.guild.id if ctx.guild else None))
        cost = int(stocks) * int(live_price)
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
            await self._reprice_from_metrics(guild_id=(ctx.guild.id if ctx.guild else None))
        except ValueError as e:
            return await ctx.respond(str(e), ephemeral=True)

        embed = discord.Embed(
            title="✅ STOCKS PURCHASED",
            description=(
                f"Purchased `{int(stocks):,}` stocks for `{int(cost):,} aUEC`.\n"
                f"Price per stock: `{int(live_price):,} aUEC`."
            ),
            colour=discord.Colour.green(),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")
        embed.add_field(name="Migration Notice", value="Stock system is now live and replaces legacy share command flow.", inline=False)
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
            await self._reprice_from_metrics(guild_id=(ctx.guild.id if ctx.guild else None))
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
            f"Estimated payout: `{payout_amount:,} aUEC`{warn}\n\n"
            "Migration Notice: Stock system is now live and legacy share commands have been retired.",
            ephemeral=True,
        )

    @stock.command(name="price_nudge", description="(Finance/Admin) Nudge stock price by basis points")
    @finance_or_admin()
    async def price_nudge(self, ctx: discord.ApplicationContext, bps: int):
        gid = (ctx.guild.id if ctx.guild else None)
        before, after = await self._manual_price_adjust_bps(delta_bps=int(bps), guild_id=gid)
        await ctx.respond(
            f"Stock price adjusted: `{before:,} -> {after:,} aUEC` (requested `{int(bps)}` bps).",
            ephemeral=True,
        )

    @stock.command(name="price_set", description="(Finance/Admin) Set stock price directly (bounded by config limits)")
    @finance_or_admin()
    async def price_set(self, ctx: discord.ApplicationContext, price: int):
        gid = (ctx.guild.id if ctx.guild else None)
        cfg = await self.db.get_stock_market_config(guild_id=gid)
        min_price = int(cfg.get("min_price") or 1)
        max_price = int(cfg.get("max_price") or 10**12)
        bounded = min(max(int(price), min_price), max_price)
        state = await self.db.get_stock_price_state(guild_id=gid)
        day_open = int(state.get("day_open_price") or bounded)
        cap_bps = max(0, int(cfg.get("daily_move_cap_bps") or 500))
        floor = int(round(day_open * (10000 - cap_bps) / 10000))
        ceil = int(round(day_open * (10000 + cap_bps) / 10000))
        bounded = min(max(int(bounded), max(min_price, floor)), min(max_price, ceil))
        old = int(state.get("current_price") or bounded)
        await self.db.set_stock_price_state(guild_id=gid, current_price=int(bounded))
        await ctx.respond(f"Stock price set: `{old:,} -> {int(bounded):,} aUEC`.", ephemeral=True)

    @stock.command(name="market", description="View stock market price and movement")
    async def market(self, ctx: discord.ApplicationContext):
        gid = (ctx.guild.id if ctx.guild else None)
        cfg = await self.db.get_stock_market_config(guild_id=gid)
        state = await self.db.get_stock_price_state(guild_id=gid)
        metrics = await self.db.get_stock_trade_metrics(guild_id=gid)
        current = int(state.get("current_price") or cfg.get("base_price") or DEFAULT_STOCK_PRICE)
        open_24h = int(state.get("day_open_price") or current)
        change_24h_bps = 0 if open_24h <= 0 else int(round(((current - open_24h) / open_24h) * 10000))
        change_7d_bps = await self.db.get_stock_change_bps(days=7, guild_id=gid)

        def fmt_bps(bps: int) -> str:
            sign = "+" if int(bps) >= 0 else ""
            return f"{sign}{int(bps)/100:.2f}%"

        embed = discord.Embed(
            title="📊 STOCK MARKET",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")
        embed.add_field(name="Current Price", value=f"`{current:,} aUEC`", inline=True)
        embed.add_field(name="Change (since open)", value=f"`{fmt_bps(change_24h_bps)}`", inline=True)
        embed.add_field(name="7d Trend", value=f"`{fmt_bps(change_7d_bps)}`", inline=True)
        embed.add_field(name="Net Flow (since reset)", value=f"`{int(metrics.get('net_units_24h') or 0):,}` units", inline=True)
        embed.add_field(name="Floor / Ceiling", value=f"`{int(cfg.get('min_price') or 0):,}` / `{int(cfg.get('max_price') or 0):,}`", inline=True)
        embed.add_field(name="Daily Move Cap", value=f"`{int(cfg.get('daily_move_cap_bps') or 0)/100:.2f}%`", inline=True)

        await ctx.respond(embed=embed, files=_logo_files(), ephemeral=True)

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
        live_price = await self._get_live_stock_price(guild_id=gid)
        embed.set_footer(text=f"Current stock price: {int(live_price):,} aUEC")

        await ctx.respond(embed=embed, files=_logo_files(), ephemeral=True)


def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    bot.add_cog(StockCog(bot, db))
