import os
import discord
from discord.ext import commands

from services.db import Database
from services.permissions import is_finance_or_admin

TREASURY_CHANNEL_ID = int(os.getenv("TREASURY_CHANNEL_ID", os.getenv("FINANCE_CHANNEL_ID", "0")) or "0")


class TreasuryCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    def _in_treasury_channel(self, ctx: discord.ApplicationContext) -> bool:
        if TREASURY_CHANNEL_ID <= 0:
            return True
        return bool(ctx.channel and int(ctx.channel.id) == int(TREASURY_CHANNEL_ID))

    treasury = discord.SlashCommandGroup("treasury", "Treasury commands (org aUEC pool)")

    @treasury.command(name="status", description="View the current treasury amount")
    async def status(self, ctx: discord.ApplicationContext):
        if not self._in_treasury_channel(ctx):
            return await ctx.respond(f"Use this command in <#{TREASURY_CHANNEL_ID}>.", ephemeral=True)

        amount, updated_by, updated_at = await self.db.get_treasury_meta()

        embed = discord.Embed(
            title="🏦 TREASURY STATUS",
            description=f"**Current Treasury:** `{amount:,} aUEC`",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )

        if updated_by:
            embed.add_field(name="Last Updated By", value=f"<@{updated_by}>", inline=True)
        else:
            embed.add_field(name="Last Updated By", value="—", inline=True)

        embed.add_field(name="Last Updated At", value=f"`{updated_at}`" if updated_at else "—", inline=True)
        embed.set_footer(text="Treasury is manual (no Star Citizen API). Used for cash-out safety checks.")

        await ctx.respond(embed=embed, ephemeral=True)

    @treasury.command(name="set", description="(Finance/Admin) Set the treasury amount (aUEC)")
    async def set(self, ctx: discord.ApplicationContext, amount: int):
        if not self._in_treasury_channel(ctx):
            return await ctx.respond(f"Use this command in <#{TREASURY_CHANNEL_ID}>.", ephemeral=True)

        if not isinstance(ctx.author, discord.Member) or not is_finance_or_admin(ctx.author):
            return await ctx.respond("Only Finance/Admin can set treasury.", ephemeral=True)

        if amount < 0:
            return await ctx.respond("Treasury amount cannot be negative.", ephemeral=True)

        await self.db.set_treasury(int(amount), updated_by=ctx.author.id)

        embed = discord.Embed(
            title="✅ TREASURY UPDATED",
            description=f"Treasury is now set to: `{int(amount):,} aUEC`",
            colour=discord.Colour.green(),
        )
        embed.set_footer(text="Remember: this is a manual org pool value.")

        await ctx.respond(embed=embed, ephemeral=True)
