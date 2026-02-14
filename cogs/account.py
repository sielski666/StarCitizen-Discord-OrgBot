import os
import re
import logging
import discord
from discord.ext import commands

from services.db import Database
from services.permissions import is_admin_member, is_finance
from services.tiers import (
    LEVEL_ROLE_MAP,
    expected_tier_role_id_for_level,
    tier_display_for_level,
)

ASSET_ORG_LOGO_PNG = "assets/org_logo.png"

SHARE_PRICE = 100_000  # Org Credits per share (buy)
SHARE_CASHOUT_AUEC_PER_SHARE = int(os.getenv("SHARE_CASHOUT_AUEC_PER_SHARE", str(SHARE_PRICE)) or SHARE_PRICE)
FINANCE_CHANNEL_ID = int(os.getenv("FINANCE_CHANNEL_ID", "0") or "0")
SHARES_SELL_CHANNEL_ID = int(os.getenv("SHARES_SELL_CHANNEL_ID", "0") or "0")

# Rep / Level / Tier config
LEVEL_PER_REP = int(os.getenv("LEVEL_PER_REP", "100") or "100")

logger = logging.getLogger(__name__)


def is_finance_or_admin(member: discord.Member) -> bool:
    return is_admin_member(member) or is_finance(member)


def is_admin():
    async def predicate(ctx: discord.ApplicationContext):
        return isinstance(ctx.author, discord.Member) and is_admin_member(ctx.author)
    return commands.check(predicate)


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


def _tier_display_for_level(level: int) -> str:
    return tier_display_for_level(int(level))


def _expected_tier_role_id(level: int) -> int | None:
    return expected_tier_role_id_for_level(int(level))


async def _get_thread(guild: discord.Guild | None, thread_id: int | None):
    if not guild or not thread_id:
        return None
    th = guild.get_thread(thread_id)
    if th:
        return th
    try:
        return await guild.fetch_channel(thread_id)
    except Exception:
        logger.debug("Could not fetch thread/channel id=%s", thread_id, exc_info=True)
        return None


def _extract_request_id_from_message(message: discord.Message) -> int | None:
    """
    We embed request_id in the embed title like:
      "🏦 CASH-OUT REQUEST • #123"
    This lets our persistent buttons stay constant across restarts.
    """
    try:
        if not message.embeds:
            return None
        title = message.embeds[0].title or ""
        m = re.search(r"#(\d+)", title)
        if not m:
            return None
        return int(m.group(1))
    except Exception:
        logger.debug("Failed to extract cashout request id from message", exc_info=True)
        return None


class CashoutPersistentView(discord.ui.View):
    """
    Persistent view (survives restarts):
      - timeout=None
      - constant custom_ids
      - registered once via bot.add_view(...)
    """

    def __init__(self, db: Database):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="cashout_approve")
    async def approve_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not isinstance(interaction.user, discord.Member) or not is_finance_or_admin(interaction.user):
            return await interaction.followup.send("Only Finance/Admin can do that.", ephemeral=True)

        if not interaction.message:
            return await interaction.followup.send("Missing message context.", ephemeral=True)

        request_id = _extract_request_id_from_message(interaction.message)
        if not request_id:
            return await interaction.followup.send("Could not read request ID from message.", ephemeral=True)

        row = await self.db.get_cashout_request(request_id)
        if not row:
            return await interaction.followup.send("Request not found in database.", ephemeral=True)

        (
            rid, guild_id, channel_id, message_id, requester_id, shares, status,
            created_at, updated_at, thread_id, handled_by, handled_note
        ) = row

        if status != "pending":
            return await interaction.followup.send(f"Request is not pending (status: {status}).", ephemeral=True)

        await self.db.set_cashout_status(
            request_id=rid,
            status="approved",
            handled_by=interaction.user.id,
            note=f"Approved by {interaction.user.id}",
        )

        new_embed = AccountCog._static_cashout_embed(rid, requester_id, shares, "approved")
        files = _logo_files()
        await interaction.message.edit(embed=new_embed, view=self, files=files if files else None)

        th = await _get_thread(interaction.guild, thread_id)
        if th:
            try:
                await th.send(
                    f"✅ Approved by {interaction.user.mention}.\n"
                    "Next: transfer aUEC manually in-game, then click **Mark Paid**."
                )
            except Exception:
                logger.debug("Failed to send approval update to cashout thread request_id=%s", rid, exc_info=True)

        await interaction.followup.send("Approved.", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="cashout_reject")
    async def reject_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not isinstance(interaction.user, discord.Member) or not is_finance_or_admin(interaction.user):
            return await interaction.followup.send("Only Finance/Admin can do that.", ephemeral=True)

        if not interaction.message:
            return await interaction.followup.send("Missing message context.", ephemeral=True)

        request_id = _extract_request_id_from_message(interaction.message)
        if not request_id:
            return await interaction.followup.send("Could not read request ID from message.", ephemeral=True)

        row = await self.db.get_cashout_request(request_id)
        if not row:
            return await interaction.followup.send("Request not found in database.", ephemeral=True)

        (
            rid, guild_id, channel_id, message_id, requester_id, shares, status,
            created_at, updated_at, thread_id, handled_by, handled_note
        ) = row

        if status not in ("pending", "approved"):
            return await interaction.followup.send(f"Request cannot be rejected (status: {status}).", ephemeral=True)

        # Unlock shares back
        try:
            await self.db.unlock_shares(requester_id, int(shares))
        except Exception:
            logger.exception("Failed to unlock shares for requester_id=%s request_id=%s", requester_id, rid)

        await self.db.set_cashout_status(
            request_id=rid,
            status="rejected",
            handled_by=interaction.user.id,
            note=f"Rejected by {interaction.user.id}",
        )

        new_embed = AccountCog._static_cashout_embed(rid, requester_id, shares, "rejected")
        files = _logo_files()
        await interaction.message.edit(embed=new_embed, view=None, files=files if files else None)

        th = await _get_thread(interaction.guild, thread_id)
        if th:
            try:
                await th.send(f"🟥 Rejected by {interaction.user.mention}. Shares unlocked for <@{requester_id}>.")
                await th.edit(archived=True, locked=True)
            except Exception:
                logger.debug("Failed to update rejection thread state request_id=%s", rid, exc_info=True)

        await interaction.followup.send("Rejected and unlocked shares.", ephemeral=True)

    @discord.ui.button(label="Mark Paid", style=discord.ButtonStyle.primary, custom_id="cashout_paid")
    async def paid_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not isinstance(interaction.user, discord.Member) or not is_finance_or_admin(interaction.user):
            return await interaction.followup.send("Only Finance/Admin can do that.", ephemeral=True)

        if not interaction.message:
            return await interaction.followup.send("Missing message context.", ephemeral=True)

        request_id = _extract_request_id_from_message(interaction.message)
        if not request_id:
            return await interaction.followup.send("Could not read request ID from message.", ephemeral=True)

        row = await self.db.get_cashout_request(request_id)
        if not row:
            return await interaction.followup.send("Request not found in database.", ephemeral=True)

        (
            rid, guild_id, channel_id, message_id, requester_id, shares, status,
            created_at, updated_at, thread_id, handled_by, handled_note
        ) = row

        if status != "approved":
            return await interaction.followup.send(f"Request must be approved first (status: {status}).", ephemeral=True)

        payout_amount = int(shares) * int(SHARE_CASHOUT_AUEC_PER_SHARE)

        try:
            await self.db.finalize_cashout_paid(
                request_id=rid,
                payout_amount=payout_amount,
                handled_by=interaction.user.id,
                note=f"Marked paid ({payout_amount:,} aUEC) and removed shares",
            )
        except ValueError as e:
            if "Treasury too low" in str(e):
                current_treasury = await self.db.get_treasury()
                return await interaction.followup.send(
                    f"Cannot mark paid: {e}\nCurrent treasury: `{current_treasury:,} aUEC`\nRequired: `{payout_amount:,} aUEC`",
                    ephemeral=True,
                )
            return await interaction.followup.send(f"Cannot mark paid: {e}", ephemeral=True)

        treasury_left = await self.db.get_treasury()

        new_embed = AccountCog._static_cashout_embed(rid, requester_id, shares, "paid")
        files = _logo_files()
        await interaction.message.edit(embed=new_embed, view=None, files=files if files else None)

        th = await _get_thread(interaction.guild, thread_id)
        if th:
            try:
                await th.send(
                    f"🔔 <@{requester_id}>\n"
                    f"💰 Cash-out **#{rid}** marked **PAID** by {interaction.user.mention}.\n\n"
                    f"Payout: `{payout_amount:,} aUEC`\n"
                    f"Treasury remaining: `{treasury_left:,} aUEC`"
                )
                await th.edit(archived=True, locked=True)
            except Exception:
                logger.debug("Failed to update paid thread state request_id=%s", rid, exc_info=True)

        await interaction.followup.send("Marked paid and finalized shares.", ephemeral=True)


class AccountCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    account = discord.SlashCommandGroup("account", "Account / shares / cash-out")

    @staticmethod
    def _static_cashout_embed(request_id: int, requester_id: int, shares: int, status: str) -> discord.Embed:
        e = discord.Embed(
            title=f"🏦 CASH-OUT REQUEST • #{request_id}",
            description=(
                f"**Requester:** <@{requester_id}>\n"
                f"**Shares to sell:** `{shares:,}`\n"
                f"**Estimated payout:** `{shares * SHARE_CASHOUT_AUEC_PER_SHARE:,} aUEC`\n"
                f"**Status:** `{status.upper()}`\n\n"
                "Finance/Admin: use the buttons below.\n"
                "Member: wait for approval, then org aUEC transfer is handled manually."
            ),
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        e.set_thumbnail(url="attachment://org_logo.png")
        e.set_footer(text="Escrow enabled: shares are locked until approved/rejected.")
        return e

    async def _sync_member_tier_roles(
        self,
        member: discord.Member,
        *,
        notify_dm: bool = False,
        before_level: int | None = None,
    ) -> dict:
        """
        Single-tier role system (Option A):
          - member should have exactly one tier role (highest they qualify for)
          - lower tier roles are removed
        """
        if not LEVEL_ROLE_MAP:
            return {"changed": False, "reason": "LEVEL_ROLE_MAP not configured"}

        lvl_now = await self.db.get_level(member.id, per_level=LEVEL_PER_REP)
        expected_role_id = _expected_tier_role_id(int(lvl_now))

        tier_role_ids = set(int(x) for x in LEVEL_ROLE_MAP.values())

        has_ids = set(int(r.id) for r in member.roles)
        current_tier_roles = [r for r in member.roles if int(r.id) in tier_role_ids]

        expected_role = member.guild.get_role(int(expected_role_id)) if expected_role_id else None

        changed = False
        removed = []
        added = None

        # Remove all tier roles except expected
        for r in current_tier_roles:
            if expected_role_id is None or int(r.id) != int(expected_role_id):
                try:
                    await member.remove_roles(r, reason="Tier role sync (single-tier policy)")
                    removed.append(int(r.id))
                    changed = True
                except Exception:
                    pass

        # Add expected if missing
        if expected_role and int(expected_role.id) not in has_ids:
            try:
                await member.add_roles(expected_role, reason="Tier role sync (single-tier policy)")
                added = int(expected_role.id)
                changed = True
            except Exception:
                pass

        # Optional DM notification if tier changed
        if notify_dm and before_level is not None:
            before_expected = _expected_tier_role_id(int(before_level))
            after_expected = expected_role_id
            if before_expected != after_expected and after_expected is not None:
                try:
                    before_disp = _tier_display_for_level(int(before_level))
                    after_disp = _tier_display_for_level(int(lvl_now))

                    em = discord.Embed(
                        title="🏅 Rank Up!",
                        description=(
                            f"You just ranked up!\n\n"
                            f"**Before:** {before_disp}\n"
                            f"**Now:** {after_disp}\n\n"
                            f"Level: `{int(before_level)}` → `{int(lvl_now)}`"
                        ),
                        colour=discord.Colour.gold(),
                    )
                    em.set_thumbnail(url="attachment://org_logo.png")
                    em.set_footer(text="Your tier role was updated automatically.")
                    await member.send(embed=em, files=_logo_files())
                except Exception:
                    pass

        return {
            "changed": changed,
            "level": int(lvl_now),
            "expected_role_id": int(expected_role_id) if expected_role_id else None,
            "removed_role_ids": removed,
            "added_role_id": added,
        }

    # =======================
    # OVERVIEW
    # =======================
    @account.command(name="overview", description="View your Org Credits, Shares, Reputation, Level, and Tier")
    async def overview(self, ctx: discord.ApplicationContext):
        bal = await self.db.get_balance(ctx.author.id)
        shares_total = await self.db.get_shares(ctx.author.id)
        shares_locked = await self.db.get_shares_locked(ctx.author.id)
        shares_available = await self.db.get_shares_available(ctx.author.id)
        rep = await self.db.get_rep(ctx.author.id)
        level = await self.db.get_level(ctx.author.id, per_level=LEVEL_PER_REP)

        tier_text = _tier_display_for_level(int(level))
        expected_role_id = _expected_tier_role_id(int(level))
        expected_role_txt = "—"
        if expected_role_id and ctx.guild:
            role = ctx.guild.get_role(int(expected_role_id))
            expected_role_txt = role.mention if role else f"`{expected_role_id}`"

        embed = discord.Embed(
            title="📒 ACCOUNT OVERVIEW",
            description=f"**Member:** {ctx.author.mention}",
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")

        embed.add_field(name="Org Credits", value=f"`{bal:,}`", inline=True)
        embed.add_field(name="Shares (Total)", value=f"`{shares_total:,}`", inline=True)
        embed.add_field(name="Shares (Available)", value=f"`{shares_available:,}`", inline=True)
        embed.add_field(name="Shares (Locked)", value=f"`{shares_locked:,}`", inline=True)
        embed.add_field(name="Reputation", value=f"`{rep:,}`", inline=True)
        embed.add_field(name="Level", value=f"`{level:,}`", inline=True)

        embed.add_field(name="Tier", value=tier_text, inline=False)
        embed.add_field(name="Tier Role (Expected)", value=expected_role_txt, inline=False)

        await ctx.respond(embed=embed, files=_logo_files(), ephemeral=True)

    # =======================
    # FINANCE/ADMIN: DEBUG TIERS
    # =======================
    @account.command(name="debugtiers", description="(Finance/Admin) Audit a member's level/tier role mapping")
    @finance_or_admin()
    async def debugtiers(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member | None = None,
        fix: bool = False,
    ):
        await ctx.defer(ephemeral=True)

        if not ctx.guild:
            return await ctx.followup.send("This command must be used in a server.", ephemeral=True)

        target = member or (ctx.author if isinstance(ctx.author, discord.Member) else None)
        if not target:
            return await ctx.followup.send("Could not resolve a target member.", ephemeral=True)

        rep = await self.db.get_rep(target.id)
        level = await self.db.get_level(target.id, per_level=LEVEL_PER_REP)

        tier_disp = _tier_display_for_level(int(level))
        expected_role_id = _expected_tier_role_id(int(level))

        tier_role_ids = set(int(x) for x in LEVEL_ROLE_MAP.values()) if LEVEL_ROLE_MAP else set()
        current_tier_roles = [r for r in target.roles if int(r.id) in tier_role_ids]

        expected_role = ctx.guild.get_role(int(expected_role_id)) if expected_role_id else None

        status = "✅ OK"
        mismatch_reason = ""
        if LEVEL_ROLE_MAP:
            if expected_role_id is None:
                # Below first threshold: should have no tier roles
                if current_tier_roles:
                    status = "❌ MISMATCH"
                    mismatch_reason = "Member is below tier thresholds but still has tier role(s)."
            else:
                has_expected = any(int(r.id) == int(expected_role_id) for r in current_tier_roles)
                extra = [r for r in current_tier_roles if int(r.id) != int(expected_role_id)]
                if not has_expected or extra:
                    status = "❌ MISMATCH"
                    mismatch_reason = "Missing expected tier role and/or has extra tier roles."

        sync_result = None
        if fix and isinstance(target, discord.Member):
            sync_result = await self._sync_member_tier_roles(target, notify_dm=False)

        embed = discord.Embed(
            title="🧪 TIER AUDIT",
            description=f"**Member:** {target.mention}\n**Status:** {status}",
            colour=discord.Colour.green() if status == "✅ OK" else discord.Colour.red(),
        )

        embed.add_field(name="Reputation", value=f"`{rep}`", inline=True)
        embed.add_field(name="Level", value=f"`{level}`", inline=True)
        embed.add_field(name="Tier", value=tier_disp, inline=False)

        exp_txt = "—"
        if expected_role_id:
            exp_txt = expected_role.mention if expected_role else f"`{expected_role_id}`"
        embed.add_field(name="Expected Tier Role", value=exp_txt, inline=False)

        cur_txt = "—"
        if current_tier_roles:
            cur_txt = ", ".join(r.mention for r in current_tier_roles[:10])
        embed.add_field(name="Current Tier Role(s)", value=cur_txt, inline=False)

        if mismatch_reason:
            embed.add_field(name="Why mismatch?", value=mismatch_reason, inline=False)

        if sync_result is not None:
            embed.add_field(
                name="Fix Result",
                value=(
                    f"Changed: `{sync_result.get('changed')}`\n"
                    f"Added: `{sync_result.get('added_role_id')}`\n"
                    f"Removed: `{sync_result.get('removed_role_ids')}`"
                ),
                inline=False,
            )

        await ctx.followup.send(embed=embed, ephemeral=True)

    # =======================
    # FINANCE/ADMIN: ROLE SYNC
    # =======================
    @account.command(name="rolesync", description="(Finance/Admin) Sync tier roles based on current levels")
    @finance_or_admin()
    async def rolesync(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member | None = None,
        dry_run: bool = False,
    ):
        await ctx.defer(ephemeral=True)

        if not ctx.guild:
            return await ctx.followup.send("This command must be used in a server.", ephemeral=True)

        if not LEVEL_ROLE_MAP:
            return await ctx.followup.send(
                "LEVEL_ROLE_MAP is not set. Add it to your .env like:\n"
                "LEVEL_ROLE_MAP=5:ROLEID,10:ROLEID,20:ROLEID",
                ephemeral=True,
            )

        targets: list[discord.Member] = []
        if member:
            targets = [member]
        else:
            # Use cached members (members intent enabled in bot.py)
            targets = [m for m in ctx.guild.members if not m.bot]

            # If cache is empty for some reason, try fetching (Pycord supports fetch_members)
            if not targets:
                try:
                    fetched = []
                    async for m in ctx.guild.fetch_members(limit=None):
                        if not m.bot:
                            fetched.append(m)
                    targets = fetched
                except Exception:
                    pass

        changed = 0
        scanned = 0

        for m in targets:
            scanned += 1
            if dry_run:
                lvl_now = await self.db.get_level(m.id, per_level=LEVEL_PER_REP)
                expected_role_id = _expected_tier_role_id(int(lvl_now))
                tier_role_ids = set(int(x) for x in LEVEL_ROLE_MAP.values())
                current_tier_roles = [r for r in m.roles if int(r.id) in tier_role_ids]
                needs_change = False
                if expected_role_id is None:
                    needs_change = bool(current_tier_roles)
                else:
                    has_expected = any(int(r.id) == int(expected_role_id) for r in current_tier_roles)
                    extras = [r for r in current_tier_roles if int(r.id) != int(expected_role_id)]
                    needs_change = (not has_expected) or bool(extras)
                if needs_change:
                    changed += 1
            else:
                res = await self._sync_member_tier_roles(m, notify_dm=False)
                if res.get("changed"):
                    changed += 1

        mode = "DRY RUN" if dry_run else "APPLIED"
        await ctx.followup.send(
            f"🛠 Tier role sync complete.\nMode: **{mode}**\nScanned: `{scanned}` | Members needing/with changes: `{changed}`",
            ephemeral=True,
        )

    # =======================
    # ADMIN: RECONCILE ESCROW
    # =======================
    @account.command(
        name="reconcile",
        description="Admin: rebuild escrow locks (optionally force-clear all pending/approved cash-outs)"
    )
    @is_admin()
    async def reconcile(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Member | None = None,
        dry_run: bool = True,
        force_clear_active: bool = False,
    ):
        await ctx.defer(ephemeral=True)

        target_id = member.id if member else None

        data = await self.db.reconcile_escrow(
            discord_id=target_id,
            dry_run=bool(dry_run),
            force_clear_active=bool(force_clear_active),
            handled_by=ctx.author.id,
        )

        results = data.get("users", [])
        rejected_requests = data.get("requests_rejected", [])

        changed = [r for r in results if r.get("changed")]
        total_scanned = len(results)
        total_changed = len(changed)

        lines = []
        for r in changed[:20]:
            uid = r["discord_id"]
            before = r["locked_before"]
            after = r["locked_after"]
            total = r["total_shares"]
            expected = r["expected_locked"]
            lines.append(f"<@{uid}> — locked `{before}` → `{after}` (expected `{expected}`, total `{total}`)")

        extra = ""
        if total_changed > 20:
            extra = f"\n…and `{total_changed - 20}` more."

        mode = "DRY RUN (no changes saved)" if dry_run else "APPLIED (changes saved)"
        scope = f"Member: {member.mention}" if member else "Scope: ALL members"
        forced = "YES" if force_clear_active else "NO"

        embed = discord.Embed(
            title="🧰 ESCROW RECONCILE",
            description=(
                f"**{mode}**\n{scope}\n\n"
                f"Force-clear pending/approved requests: `{forced}`\n"
                f"Requests rejected: `{len(rejected_requests)}`\n"
                f"Scanned: `{total_scanned}` | Lock changes: `{total_changed}`"
            ),
            colour=discord.Colour.orange() if dry_run else discord.Colour.green(),
        )

        if rejected_requests:
            show = ", ".join(str(x) for x in rejected_requests[:20])
            more = ""
            if len(rejected_requests) > 20:
                more = f" (+{len(rejected_requests) - 20} more)"
            embed.add_field(name="Rejected request IDs", value=f"`{show}`{more}", inline=False)

        if lines:
            embed.add_field(name="Lock changes", value="\n".join(lines) + extra, inline=False)
        else:
            embed.add_field(name="Lock changes", value="No lock changes required.", inline=False)

        await ctx.followup.send(embed=embed, ephemeral=True)

    # =======================
    # BUY SHARES
    # =======================
    @account.command(name="buyshares", description="Buy shares with Org Credits")
    async def buyshares(self, ctx: discord.ApplicationContext, shares: int):
        if shares < 1:
            return await ctx.respond("Shares must be at least 1.", ephemeral=True)

        cost = int(shares) * int(SHARE_PRICE)

        try:
            await self.db.buy_shares(
                ctx.author.id,
                shares_delta=int(shares),
                cost=int(cost),
                reference=f"buy {shares}",
            )
        except ValueError as e:
            return await ctx.respond(str(e), ephemeral=True)

        embed = discord.Embed(
            title="✅ SHARES PURCHASED",
            description=(
                f"Purchased `{int(shares):,}` shares for `{int(cost):,}` Org Credits.\n"
                f"Price per share: `{int(SHARE_PRICE):,}` Org Credits."
            ),
            colour=discord.Colour.green(),
        )
        embed.set_thumbnail(url="attachment://org_logo.png")

        await ctx.respond(embed=embed, files=_logo_files(), ephemeral=True)

    # =======================
    # SELL SHARES (CREATE CASHOUT REQUEST)
    # =======================
    @account.command(name="sellshares", description="Request to cash-out by selling shares (locks shares until handled)")
    async def sellshares(self, ctx: discord.ApplicationContext, shares: int):
        await ctx.defer(ephemeral=True)

        if shares < 1:
            return await ctx.followup.send("Shares must be at least 1.", ephemeral=True)

        available = await self.db.get_shares_available(ctx.author.id)
        if available < int(shares):
            locked = await self.db.get_shares_locked(ctx.author.id)
            total = await self.db.get_shares(ctx.author.id)
            return await ctx.followup.send(
                f"Not enough **available** shares.\nTotal: `{total:,}` | Locked: `{locked:,}` | Available: `{available:,}`",
                ephemeral=True,
            )

        try:
            await self.db.lock_shares(ctx.author.id, int(shares))
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
            shares=int(shares),
        )

        thread = await msg.create_thread(
            name=f"Cash-out #{request_id} — {ctx.author.display_name}",
            auto_archive_duration=1440,
        )
        await self.db.set_cashout_thread(request_id, thread.id)

        embed = self._static_cashout_embed(request_id, ctx.author.id, int(shares), "pending")

        # IMPORTANT: use the persistent view instance already registered on the bot
        view = getattr(self.bot, "cashout_view", None)
        if view is None:
            await msg.edit(embed=embed, view=None, files=_logo_files())
        else:
            await msg.edit(embed=embed, view=view, files=_logo_files())

        await thread.send(
            f"🧾 Cash-out request created by {ctx.author.mention}\n"
            f"Shares locked: `{int(shares):,}`\n\n"
            "Finance/Admin: **Approve** → transfer aUEC manually → **Mark Paid**.\n"
            "Reject will unlock shares automatically."
        )

        payout_amount = int(shares) * int(SHARE_CASHOUT_AUEC_PER_SHARE)
        treasury_amount = await self.db.get_treasury()
        warn = ""
        if treasury_amount < payout_amount:
            warn = f"\n\n⚠️ Treasury currently: `{treasury_amount:,} aUEC` (below estimated payout `{payout_amount:,} aUEC`)."

        await ctx.followup.send(
            f"Cash-out request **#{request_id}** created. Your `{int(shares):,}` shares are now **locked** until handled.\n"
            f"Estimated payout: `{payout_amount:,} aUEC`{warn}",
            ephemeral=True,
        )


def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore

    bot.add_cog(AccountCog(bot, db))

    # Register ONE persistent view that survives restarts
    bot.cashout_view = CashoutPersistentView(db)  # type: ignore
    bot.add_view(bot.cashout_view)  # type: ignore

