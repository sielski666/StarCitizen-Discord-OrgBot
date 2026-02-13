import os
import re
import discord
from discord.ext import commands

from services.db import Database
from services.permissions import is_finance_or_admin

ASSET_ORG_LOGO_PNG = "assets/org_logo.png"
SHARE_PRICE = 100_000
SHARE_CASHOUT_AUEC_PER_SHARE = int(os.getenv("SHARE_CASHOUT_AUEC_PER_SHARE", str(SHARE_PRICE)) or SHARE_PRICE)


def _logo_files():
    try:
        if os.path.exists(ASSET_ORG_LOGO_PNG):
            return [discord.File(ASSET_ORG_LOGO_PNG, filename="org_logo.png")]
    except Exception:
        pass
    return []


def finance_or_admin():
    async def predicate(ctx: discord.ApplicationContext):
        return isinstance(ctx.author, discord.Member) and is_finance_or_admin(ctx.author)
    return commands.check(predicate)


async def _mention_or_fallback(guild: discord.Guild | None, user_id: int) -> str:
    """
    Prefer a mention, but if we can't resolve the member, fall back to a readable label.
    """
    if not guild:
        return f"<@{user_id}>"

    m = guild.get_member(user_id)
    if not m:
        try:
            m = await guild.fetch_member(user_id)
        except Exception:
            m = None

    if m:
        return m.mention

    # Fallback (still clickable mention in most cases)
    return f"<@{user_id}>"


def _extract_paid_by_id(reference: str | None) -> int | None:
    if not reference:
        return None
    m = re.search(r"(?:\bby:|\bpayout_by:|\brep_by:)(\d+)", reference)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


class FinanceCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    finance = discord.SlashCommandGroup("finance", "Finance dashboard commands")

    @finance.command(name="pending_cashouts", description="List pending/approved cash-out requests")
    @finance_or_admin()
    async def pending_cashouts(
        self,
        ctx: discord.ApplicationContext,
        statuses: str = "pending,approved",
        limit: int = 10,
    ):
        await ctx.defer(ephemeral=True)

        st = [s.strip().lower() for s in (statuses or "").split(",") if s.strip()]
        if not st:
            st = ["pending", "approved"]

        rows = await self.db.list_cashout_requests(statuses=st, limit=int(limit))

        embed = discord.Embed(
            title="🏦 Pending Cash-out Requests",
            description=f"Showing `{len(rows)}` request(s).",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")

        if not rows:
            embed.add_field(name="None", value="No matching requests.", inline=False)
            return await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)

        for row in rows[:25]:
            (
                rid, guild_id, channel_id, message_id, requester_id, shares, status,
                created_at, updated_at, thread_id, handled_by, handled_note
            ) = row

            payout = int(shares) * int(SHARE_CASHOUT_AUEC_PER_SHARE)
            embed.add_field(
                name=f"#{rid} • {status.upper()} • {int(shares):,} share(s)",
                value=(
                    f"Requester: <@{int(requester_id)}>\n"
                    f"Est payout: `{payout:,} aUEC`\n"
                    f"Created: `{created_at}`"
                ),
                inline=False,
            )

        await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)

    @finance.command(name="recent_payouts", description="Shows recent payout + rep transactions")
    @finance_or_admin()
    async def recent_payouts(self, ctx: discord.ApplicationContext, limit: int = 10):
        await ctx.defer(ephemeral=True)

        rows = await self.db.list_transactions(types=["payout", "rep"], limit=int(limit))

        embed = discord.Embed(
            title="🧾 Recent Payout Activity",
            description=f"Showing `{len(rows)}` transaction(s).",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")

        if not rows:
            embed.add_field(name="Latest", value="No recent transactions.", inline=False)
            return await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)

        lines: list[str] = []
        for (tx_id, discord_id, tx_type, amount, shares_delta, rep_delta, reference, created_at) in rows:
            target = f"<@{int(discord_id)}>"

            paid_by_id = _extract_paid_by_id(reference)
            paid_by_text = ""
            if paid_by_id:
                paid_by = await _mention_or_fallback(ctx.guild, int(paid_by_id))
                paid_by_text = f" • paid by {paid_by}"

            if str(tx_type) == "payout":
                action = f"received `{int(amount):,} Org Credits`"
            elif str(tx_type) == "rep":
                action = f"gained `{int(rep_delta):,} Rep`"
            else:
                action = f"`{tx_type}`"

            ref = reference or "—"
            # Clean, single-line bullet (like your old look)
            lines.append(f"• {target} {action} — `{created_at}`\n  `{ref}`{paid_by_text}")

        embed.add_field(
            name="Latest",
            value="\n".join(lines[:10])[:1024],  # embed field value limit safety
            inline=False,
        )

        await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)

    @finance.command(name="cashout_lookup", description="Look up a cash-out request by ID")
    @finance_or_admin()
    async def cashout_lookup(self, ctx: discord.ApplicationContext, request_id: int):
        await ctx.defer(ephemeral=True)

        row = await self.db.get_cashout_request(int(request_id))
        if not row:
            return await ctx.followup.send("Request not found.", ephemeral=True)

        (
            rid, guild_id, channel_id, message_id, requester_id, shares, status,
            created_at, updated_at, thread_id, handled_by, handled_note
        ) = row

        payout = int(shares) * int(SHARE_CASHOUT_AUEC_PER_SHARE)

        embed = discord.Embed(
            title=f"🔎 Cash-out Lookup • #{int(rid)}",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")

        embed.add_field(name="Requester", value=f"<@{int(requester_id)}>", inline=True)
        embed.add_field(name="Shares", value=f"`{int(shares):,}`", inline=True)
        embed.add_field(name="Est payout", value=f"`{payout:,} aUEC`", inline=True)

        embed.add_field(name="Status", value=f"`{str(status).upper()}`", inline=True)
        embed.add_field(name="Created", value=f"`{created_at}`", inline=True)
        embed.add_field(name="Updated", value=f"`{updated_at}`", inline=True)

        if handled_by:
            embed.add_field(name="Handled by", value=f"<@{int(handled_by)}>", inline=True)
        if handled_note:
            embed.add_field(name="Note", value=str(handled_note)[:1000], inline=False)

        await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)

    @finance.command(name="user_audit", description="Audit a user's recent transactions")
    @finance_or_admin()
    async def user_audit(self, ctx: discord.ApplicationContext, member: discord.Member, limit: int = 15):
        await ctx.defer(ephemeral=True)

        rows = await self.db.list_transactions(types=None, limit=int(limit), discord_id=int(member.id))

        embed = discord.Embed(
            title="🧾 User Audit",
            description=f"Member: {member.mention}\nShowing `{len(rows)}` transaction(s).",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")

        if not rows:
            embed.add_field(name="Latest", value="No transactions for this user.", inline=False)
            return await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)

        lines: list[str] = []
        for (tx_id, discord_id, tx_type, amount, shares_delta, rep_delta, reference, created_at) in rows:
            bits = [f"`{created_at}`", f"`{tx_type}`"]
            if int(amount) != 0:
                bits.append(f"amt `{int(amount):,}`")
            if int(shares_delta) != 0:
                bits.append(f"shares `{int(shares_delta):,}`")
            if int(rep_delta) != 0:
                bits.append(f"rep `{int(rep_delta):,}`")

            ref = reference or "—"
            lines.append(f"• TX `{tx_id}` — " + " • ".join(bits) + f"\n  `{ref}`")

        embed.add_field(name="Latest", value="\n".join(lines[:10])[:1024], inline=False)
        await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)

    @finance.command(name="cashout_stats", description="Quick cash-out status counts + treasury")
    @finance_or_admin()
    async def cashout_stats(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        pending = await self.db.count_cashout_requests(["pending"])
        approved = await self.db.count_cashout_requests(["approved"])
        paid = await self.db.count_cashout_requests(["paid"])
        rejected = await self.db.count_cashout_requests(["rejected"])
        treasury = await self.db.get_treasury()

        embed = discord.Embed(
            title="📊 Cash-out Stats",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")
        embed.add_field(name="Pending", value=f"`{pending}`", inline=True)
        embed.add_field(name="Approved", value=f"`{approved}`", inline=True)
        embed.add_field(name="Paid", value=f"`{paid}`", inline=True)
        embed.add_field(name="Rejected", value=f"`{rejected}`", inline=True)
        embed.add_field(name="Treasury", value=f"`{treasury:,} aUEC`", inline=False)

        await ctx.followup.send(embed=embed, files=_logo_files(), ephemeral=True)


def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore
    bot.add_cog(FinanceCog(bot, db))
