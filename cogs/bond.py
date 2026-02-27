import os
import logging
import discord
from discord.ext import commands

from services.db import Database

ASSET_ORG_LOGO_PNG = "assets/org_logo.png"
logger = logging.getLogger(__name__)


def _logo_files():
    try:
        if os.path.exists(ASSET_ORG_LOGO_PNG):
            return [discord.File(ASSET_ORG_LOGO_PNG, filename="org_logo.png")]
    except Exception:
        logger.exception("Failed to load org logo asset: %s", ASSET_ORG_LOGO_PNG)
    return []


class BondCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    bond = discord.SlashCommandGroup("bond", "Outstanding payout bond commands")

    @bond.command(name="redeem", description="Redeem your pending bonds using available treasury funds")
    async def redeem(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        gid = ctx.guild.id if ctx.guild else None
        pending = await self.db.list_pending_bonds(user_id=int(ctx.author.id), guild_id=gid, limit=1000)
        if not pending:
            return await ctx.followup.send("You have no pending bonds.", ephemeral=True)

        result = await self.db.redeem_bonds_for_user(
            user_id=int(ctx.author.id),
            guild_id=gid,
            redeemed_by=int(ctx.author.id),
        )

        redeemed_count = int(result.get("redeemed_count", 0))
        paid_total = int(result.get("paid_total", 0))
        treasury_after = int(result.get("treasury_after", 0))
        pending_after = int(result.get("pending_after", 0))

        embed = discord.Embed(
            title="💵 Bond Redemption",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")

        if redeemed_count <= 0 or paid_total <= 0:
            embed.description = "Treasury currently has insufficient funds to redeem your outstanding bonds."
            embed.add_field(name="Pending Bonds", value=f"`{len(pending):,}`", inline=True)
            embed.add_field(name="Treasury Available", value=f"`{treasury_after:,} aUEC`", inline=True)
            return await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)

        embed.description = "Outstanding payout bonds redeemed."
        embed.add_field(name="Redeemed Bonds", value=f"`{redeemed_count:,}`", inline=True)
        embed.add_field(name="Paid Now", value=f"`{paid_total:,} aUEC`", inline=True)
        embed.add_field(name="Treasury Remaining", value=f"`{treasury_after:,} aUEC`", inline=True)
        if pending_after > 0:
            embed.add_field(name="Still Pending", value=f"`{pending_after:,}` bond(s)", inline=False)

        await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)


def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    bot.add_cog(BondCog(bot, db))
