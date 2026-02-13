import discord
from discord.ext import commands

from services.db import Database
from services.permissions import is_finance_or_admin


class TreasuryCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    treasury = discord.SlashCommandGroup("treasury", "Treasury commands (org aUEC pool)")

    @treasury.command(name="status", description="View the current treasury amount")
    async def status(self, ctx: discord.ApplicationContext):
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
