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

    def _target_channel(self, ctx: discord.ApplicationContext):
        if TREASURY_CHANNEL_ID and ctx.guild:
            ch = ctx.guild.get_channel(TREASURY_CHANNEL_ID)
            if ch is not None:
                return ch
        return ctx.channel

    treasury = discord.SlashCommandGroup("treasury", "Treasury commands (org aUEC pool)")

    @treasury.command(name="status", description="View the current treasury amount")
    async def status(self, ctx: discord.ApplicationContext):
        gid = (ctx.guild.id if ctx.guild else None)
        amount, updated_by, updated_at = await self.db.get_treasury_meta(guild_id=gid)
        outstanding_bonds = await self.db.get_total_outstanding_bonds(guild_id=gid)
        net_available = int(amount) - int(outstanding_bonds)

        embed = discord.Embed(
            title="🏦 TREASURY STATUS",
            description=f"**Current Treasury:** `{amount:,} aUEC`",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.add_field(name="Outstanding Bonds (Liability)", value=f"`{int(outstanding_bonds):,} aUEC`", inline=True)
        embed.add_field(name="Net Available (after bonds)", value=f"`{int(net_available):,} aUEC`", inline=True)

        if updated_by:
            embed.add_field(name="Last Updated By", value=f"<@{updated_by}>", inline=True)
        else:
            embed.add_field(name="Last Updated By", value="—", inline=True)

        embed.add_field(name="Last Updated At", value=f"`{updated_at}`" if updated_at else "—", inline=True)
        embed.set_footer(text="Treasury is manual (no Star Citizen API). Bond IOUs are outstanding payout liabilities.")

        post_channel = self._target_channel(ctx)
        if post_channel is not None:
            await post_channel.send(embed=embed)
            if ctx.channel and post_channel.id != ctx.channel.id:
                return await ctx.respond(f"Posted treasury status in <#{post_channel.id}>.", ephemeral=True)

        await ctx.respond(embed=embed, ephemeral=True)

    @treasury.command(name="set", description="(Finance/Admin) Set the treasury amount (aUEC)")
    async def set(self, ctx: discord.ApplicationContext, amount: int):
        if not isinstance(ctx.author, discord.Member) or not is_finance_or_admin(ctx.author):
            return await ctx.respond("Only Finance/Admin can set treasury.", ephemeral=True)

        if amount < 0:
            return await ctx.respond("Treasury amount cannot be negative.", ephemeral=True)

        await self.db.set_treasury(
            int(amount),
            updated_by=ctx.author.id,
            guild_id=(ctx.guild.id if ctx.guild else None),
        )

        embed = discord.Embed(
            title="✅ TREASURY UPDATED",
            description=f"Treasury is now set to: `{int(amount):,} aUEC`",
            colour=discord.Colour.green(),
        )
        embed.set_footer(text="Remember: this is a manual org pool value.")

        post_channel = self._target_channel(ctx)
        if post_channel is not None:
            await post_channel.send(embed=embed)
            if ctx.channel and post_channel.id != ctx.channel.id:
                return await ctx.respond(f"Posted treasury update in <#{post_channel.id}>.", ephemeral=True)

        await ctx.respond(embed=embed, ephemeral=True)
