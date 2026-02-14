import os
import re
import logging
import discord
from discord.ext import commands

from services.db import Database
from services.permissions import is_admin_member, is_finance, is_jobs_admin
from services.tiers import (
    JOB_TIERS,
    LEVEL_ROLE_MAP,
    expected_tier_role_id_for_level,
    required_min_level_for_tier,
    tier_display_for_level,
)

ASSET_ORG_LOGO_PNG = "assets/org_logo.png"

REP_PER_JOB_PAYOUT = int(os.getenv("REP_PER_JOB_PAYOUT", "10") or "10")
LEVEL_PER_REP = int(os.getenv("LEVEL_PER_REP", "100") or "100")
JOBS_CHANNEL_ID = int(os.getenv("JOBS_CHANNEL_ID", "0") or "0")

logger = logging.getLogger(__name__)


def _tier_display_for_level(level: int) -> str:
    return tier_display_for_level(int(level))


def _expected_tier_role_id(level: int) -> int | None:
    return expected_tier_role_id_for_level(int(level))


def jobs_poster_or_admin():
    async def predicate(ctx: discord.ApplicationContext):
        # Allow all guild members to post jobs.
        # Admin/JOBS_ADMIN restrictions still apply to admin actions (cancel/reopen/etc).
        return isinstance(ctx.author, discord.Member)
    return commands.check(predicate)


def finance_or_admin():
    async def predicate(ctx: discord.ApplicationContext):
        author = ctx.author
        if not isinstance(author, discord.Member):
            return False
        return is_admin_member(author) or is_finance(author)
    return commands.check(predicate)


def admin_only():
    async def predicate(ctx: discord.ApplicationContext):
        author = ctx.author
        if not isinstance(author, discord.Member):
            return False
        return is_admin_member(author)
    return commands.check(predicate)


def _status_text(status: str) -> str:
    return {
        "open": "Open",
        "claimed": "Claimed",
        "completed": "Completed",
        "paid": "Org Points Rewarded",
        "cancelled": "Cancelled",
    }.get(status, status)


def _status_badge(status: str) -> str:
    return {
        "open": "🟦 OPEN",
        "claimed": "🟨 CLAIMED",
        "completed": "🟧 COMPLETED",
        "paid": "🟩 ORG POINTS REWARDED",
        "cancelled": "🟥 CANCELLED",
    }.get(status, status.upper())


def _logo_files() -> list[discord.File]:
    if os.path.exists(ASSET_ORG_LOGO_PNG):
        return [discord.File(ASSET_ORG_LOGO_PNG, filename="org_logo.png")]
    return []


def _extract_job_id_from_message(message: discord.Message) -> int | None:
    try:
        if not message.embeds:
            return None
        title = message.embeds[0].title or ""
        m = re.search(r"#(\d+)", title)
        if not m:
            return None
        return int(m.group(1))
    except Exception:
        logger.debug("Failed to extract job id from message embed", exc_info=True)
        return None


def _extract_min_level_from_embed(embed: discord.Embed) -> int:
    try:
        for f in embed.fields:
            if (f.name or "").strip().lower() == "minimum level":
                v = (f.value or "").strip().replace("`", "").replace("+", "").strip()
                if v.isdigit():
                    return int(v)
    except Exception:
        logger.debug("Failed to extract minimum level from job embed", exc_info=True)
    return 0


def _tier_display(min_level: int) -> str:
    return required_min_level_for_tier(int(min_level))


def _job_embed(
    job_id: int,
    title: str,
    description: str,
    reward: int,
    status: str,
    created_by: int,
    claimed_by: int | None,
    min_level: int = 0,
) -> discord.Embed:
    e = discord.Embed(
        title=f"📌 CONTRACT • Job #{job_id}",
        description=f"**{title}**\n{description}",
        colour=discord.Colour.from_rgb(32, 41, 74),
    )
    e.set_thumbnail(url="attachment://org_logo.png")

    e.add_field(name="Status", value=_status_badge(status), inline=True)
    e.add_field(name="Reward", value=f"`{reward:,}` **Org Points**", inline=True)
    e.add_field(name="Tier", value=_tier_display(int(min_level)), inline=True)

    e.add_field(name="Minimum Level", value=f"`{int(min_level)}+`", inline=True)
    e.add_field(name="\u200b", value="\u200b", inline=True)
    e.add_field(name="\u200b", value="\u200b", inline=True)

    e.add_field(name="\u200b", value="━━━━━━━━━━━━━━━━━━━━", inline=False)
    e.add_field(name="Posted by", value=f"<@{created_by}>", inline=True)
    e.add_field(name="Claimed by", value=f"<@{claimed_by}>" if claimed_by else "—", inline=True)
    e.add_field(name="\u200b", value="\u200b", inline=True)

    e.set_footer(text="Click Accept to claim. A thread is created automatically.")
    return e


async def _sync_member_tier_roles(
    db: Database,
    member: discord.Member,
    *,
    notify_dm: bool = False,
    before_level: int | None = None,
):
    """
    Option A: single tier role only (highest threshold they qualify for).
    """
    if not LEVEL_ROLE_MAP:
        return {"changed": False, "reason": "LEVEL_ROLE_MAP not configured"}

    lvl_now = await db.get_level(member.id, per_level=LEVEL_PER_REP)
    expected_role_id = _expected_tier_role_id(int(lvl_now))
    tier_role_ids = set(int(x) for x in LEVEL_ROLE_MAP.values())

    current_tier_roles = [r for r in member.roles if int(r.id) in tier_role_ids]

    changed = False
    removed = []
    added = None

    expected_role = member.guild.get_role(int(expected_role_id)) if expected_role_id else None

    # remove all tier roles except expected
    for r in current_tier_roles:
        if expected_role_id is None or int(r.id) != int(expected_role_id):
            try:
                await member.remove_roles(r, reason="Tier role sync (single-tier policy)")
                removed.append(int(r.id))
                changed = True
            except Exception:
                logger.debug("Failed removing tier role id=%s for member=%s", r.id, member.id, exc_info=True)

    # add expected if missing
    if expected_role:
        has_expected = any(int(r.id) == int(expected_role.id) for r in member.roles)
        if not has_expected:
            try:
                await member.add_roles(expected_role, reason="Tier role sync (single-tier policy)")
                added = int(expected_role.id)
                changed = True
            except Exception:
                logger.debug("Failed adding tier role id=%s for member=%s", expected_role.id, member.id, exc_info=True)

    # optional DM
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
                logger.debug("Failed sending rank-up DM to member=%s", member.id, exc_info=True)

    return {
        "changed": changed,
        "level": int(lvl_now),
        "expected_role_id": int(expected_role_id) if expected_role_id else None,
        "removed_role_ids": removed,
        "added_role_id": added,
    }


class JobTierSelectView(discord.ui.View):
    def __init__(self, cog: "JobsCog"):
        super().__init__(timeout=120)
        self.cog = cog

        options = []
        for t in JOB_TIERS[:25]:
            level = int(t["level"])
            emoji = t["emoji"]
            name = t["name"]

            desc = "No requirement" if level <= 0 else f"Requires Level {level}+"
            options.append(
                discord.SelectOption(
                    label=name[:100],
                    description=desc[:100],
                    value=str(level),
                    emoji=emoji if emoji else None,
                )
            )

        self.select = discord.ui.Select(
            placeholder="Choose a job tier…",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.select.callback = self._on_select  # type: ignore
        self.add_item(self.select)

    def mark_selected(self, level: int):
        try:
            self.select.disabled = True
            self.select.placeholder = f"Tier selected ✅ ({_tier_display(int(level))})"
        except Exception:
            logger.debug("Failed to update tier select placeholder", exc_info=True)

    async def _on_select(self, interaction: discord.Interaction):
        try:
            level = int(self.select.values[0])
        except Exception:
            level = 0

        self.mark_selected(level)
        await interaction.response.send_modal(
            JobPostModal(self.cog, min_level=level, source_message=interaction.message, source_view=self)
        )


class JobPostModal(discord.ui.Modal):
    def __init__(
        self,
        cog: "JobsCog",
        min_level: int,
        source_message: discord.Message | None = None,
        source_view: JobTierSelectView | None = None,
    ):
        super().__init__(title="Create Job")
        self.cog = cog
        self.min_level = int(min_level)
        self.source_message = source_message
        self.source_view = source_view

        self.job_title = discord.ui.InputText(label="Title", placeholder="e.g. Shred and Earn", max_length=80)
        self.job_description = discord.ui.InputText(
            label="Description",
            placeholder="Explain what needs doing, where, requirements, etc.",
            style=discord.InputTextStyle.long,
            max_length=1000,
        )
        self.job_reward = discord.ui.InputText(label="Reward (Org Credits)", placeholder="e.g. 1000000", max_length=12)

        self.add_item(self.job_title)
        self.add_item(self.job_description)
        self.add_item(self.job_reward)

    async def callback(self, interaction: discord.Interaction):
        reward_raw = (self.job_reward.value or "").replace(",", "").strip()
        if not reward_raw.isdigit():
            return await interaction.response.send_message("Reward must be a whole number.", ephemeral=True)
        reward = int(reward_raw)
        if reward <= 0:
            return await interaction.response.send_message("Reward must be greater than 0.", ephemeral=True)

        title = self.job_title.value.strip()
        desc = self.job_description.value.strip()

        await interaction.response.defer(ephemeral=True)

        try:
            placeholder = discord.Embed(title="Creating job…", description="Please wait.", colour=discord.Colour.from_rgb(32, 41, 74))

            channel = interaction.channel
            if JOBS_CHANNEL_ID:
                if not interaction.guild:
                    return await interaction.followup.send("Guild context missing for jobs channel routing.", ephemeral=True)
                ch = interaction.guild.get_channel(JOBS_CHANNEL_ID)
                if ch is None:
                    return await interaction.followup.send(
                        f"Configured JOBS_CHANNEL_ID (<#{JOBS_CHANNEL_ID}>) was not found. Run `/setup start`.",
                        ephemeral=True,
                    )
                channel = ch

            if channel is None:
                return await interaction.followup.send("Could not find the channel to post the job in.", ephemeral=True)

            msg = await channel.send(embed=placeholder)

            job_id = await self.cog.db.create_job(
                channel_id=channel.id,
                message_id=msg.id,
                title=title,
                description=desc,
                reward=reward,
                created_by=interaction.user.id,
            )

            embed = _job_embed(job_id, title, desc, reward, "open", interaction.user.id, None, min_level=self.min_level)

            files = _logo_files()
            await msg.edit(embed=embed, view=JobWorkflowView(self.cog.db, status="open"), files=files if files else None)

            posted_in = f" in <#{channel.id}>" if getattr(channel, "id", None) else ""
            await interaction.followup.send(
                f"Job #{job_id} posted{posted_in}. Tier: {_tier_display(self.min_level)}",
                ephemeral=True,
            )

            if self.source_message and self.source_view:
                try:
                    await self.source_message.edit(
                        content=f"Tier selected ✅ ({_tier_display(self.min_level)}). Job #{job_id} created.",
                        view=self.source_view,
                    )
                except Exception:
                    logger.debug("Failed to update tier selection ephemeral message", exc_info=True)

        except Exception:
            logger.exception("Job post modal callback failed")
            try:
                await interaction.followup.send("Job creation failed due to an internal error. Check the bot console.", ephemeral=True)
            except Exception:
                logger.debug("Could not send modal failure followup", exc_info=True)


class JobWorkflowView(discord.ui.View):
    """Three-stage job workflow via buttons: Accept -> Complete -> Confirm."""

    def __init__(self, db: Database, status: str = "open"):
        super().__init__(timeout=None)
        self.db = db

        if status == "open":
            self.complete_btn.disabled = True
            self.confirm_btn.disabled = True
        elif status == "claimed":
            self.accept_btn.disabled = True
            self.confirm_btn.disabled = True
        elif status == "completed":
            self.accept_btn.disabled = True
            self.complete_btn.disabled = True
        else:  # paid/cancelled/other terminal
            self.accept_btn.disabled = True
            self.complete_btn.disabled = True
            self.confirm_btn.disabled = True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="job_accept")
    async def accept_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.message or not interaction.message.embeds:
            return await interaction.followup.send("Missing job embed context.", ephemeral=True)

        jid = _extract_job_id_from_message(interaction.message)
        if not jid:
            return await interaction.followup.send("Could not read Job ID from message.", ephemeral=True)

        embed = interaction.message.embeds[0]
        min_level = _extract_min_level_from_embed(embed)

        if int(min_level) > 0:
            lvl = await self.db.get_level(interaction.user.id, per_level=LEVEL_PER_REP)
            if int(lvl) < int(min_level):
                return await interaction.followup.send(
                    f"You need **Level {int(min_level)}** to accept this job.\nYou are **Level {int(lvl)}**.",
                    ephemeral=True,
                )

        row = await self.db.get_job(int(jid))
        if not row:
            return await interaction.followup.send("Job not found.", ephemeral=True)

        (
            job_id_db,
            channel_id,
            message_id,
            title,
            description,
            reward,
            status,
            created_by,
            claimed_by,
            thread_id,
            created_at,
            updated_at,
        ) = row

        if status != "open":
            return await interaction.followup.send(f"This job is no longer open (status: {_status_text(status)}).", ephemeral=True)

        claimed = await self.db.claim_job(job_id_db, claimed_by=interaction.user.id)
        if not claimed:
            return await interaction.followup.send("Someone else accepted it first.", ephemeral=True)

        thread = await interaction.message.create_thread(
            name=f"Job #{job_id_db} — {title}",
            auto_archive_duration=1440,
        )
        await self.db.set_job_thread(job_id_db, thread.id)

        updated_embed = _job_embed(job_id_db, title, description, int(reward), "claimed", created_by, interaction.user.id, min_level=min_level)

        files = _logo_files()
        await interaction.message.edit(
            embed=updated_embed,
            view=JobWorkflowView(self.db, status="claimed"),
            files=files if files else None,
        )

        await thread.send(
            f"✅ **Accepted** by {interaction.user.mention}\n"
            f"Tier: {_tier_display(min_level)}\n\n"
            f"When finished: click **Complete** on the job card."
        )

        await interaction.followup.send("Accepted. Thread created.", ephemeral=True)

    @discord.ui.button(label="Complete", style=discord.ButtonStyle.primary, custom_id="job_complete")
    async def complete_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.message or not interaction.message.embeds:
            return await interaction.followup.send("Missing job embed context.", ephemeral=True)

        jid = _extract_job_id_from_message(interaction.message)
        if not jid:
            return await interaction.followup.send("Could not read Job ID from message.", ephemeral=True)

        row = await self.db.get_job(int(jid))
        if not row:
            return await interaction.followup.send("Job not found.", ephemeral=True)

        (
            job_id_db,
            channel_id,
            message_id,
            title,
            description,
            reward,
            status,
            created_by,
            claimed_by,
            thread_id,
            created_at,
            updated_at,
        ) = row

        is_owner = claimed_by == interaction.user.id
        is_admin_user = isinstance(interaction.user, discord.Member) and is_admin_member(interaction.user)
        if not (is_owner or is_admin_user):
            return await interaction.followup.send("Only the claimer or an admin can complete this job.", ephemeral=True)

        ok = await self.db.complete_job(job_id_db)
        if not ok:
            return await interaction.followup.send(f"Cannot complete Job #{job_id_db} (status: {_status_text(status)}).", ephemeral=True)

        min_level = _extract_min_level_from_embed(interaction.message.embeds[0]) if interaction.message.embeds else 0
        updated = _job_embed(job_id_db, title, description, int(reward), "completed", created_by, claimed_by, min_level=min_level)

        files = _logo_files()
        await interaction.message.edit(
            embed=updated,
            view=JobWorkflowView(self.db, status="completed"),
            files=files if files else None,
        )

        if thread_id and interaction.guild:
            try:
                thread = interaction.guild.get_thread(thread_id) or await interaction.guild.fetch_channel(thread_id)
                await thread.send("🧾 Job marked **COMPLETED**. Awaiting admin confirmation.")
            except Exception:
                logger.debug("Failed sending completion thread update", exc_info=True)

        await interaction.followup.send(f"Job #{job_id_db} marked completed.", ephemeral=True)

    @discord.ui.button(label="Confirm Reward", style=discord.ButtonStyle.secondary, custom_id="job_confirm")
    async def confirm_btn(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or not (is_admin_member(member) or is_finance(member)):
            return await interaction.followup.send("Only finance/admin can confirm rewards.", ephemeral=True)

        if not interaction.message or not interaction.message.embeds:
            return await interaction.followup.send("Missing job embed context.", ephemeral=True)

        jid = _extract_job_id_from_message(interaction.message)
        if not jid:
            return await interaction.followup.send("Could not read Job ID from message.", ephemeral=True)

        row = await self.db.get_job(int(jid))
        if not row:
            return await interaction.followup.send("Job not found.", ephemeral=True)

        (
            job_id_db,
            channel_id,
            message_id,
            title,
            description,
            reward,
            status,
            created_by,
            claimed_by,
            thread_id,
            created_at,
            updated_at,
        ) = row

        if status != "completed":
            return await interaction.followup.send(f"Job must be COMPLETED before confirmation (status: {_status_text(status)}).", ephemeral=True)
        if not claimed_by:
            return await interaction.followup.send("No claimer to reward.", ephemeral=True)

        await self.db.add_balance(
            discord_id=int(claimed_by),
            amount=int(reward),
            tx_type="payout",
            reference=f"job:{job_id_db}|by:{interaction.user.id}",
        )

        before_level = await self.db.get_level(int(claimed_by), per_level=LEVEL_PER_REP)

        rep_added = 0
        if int(REP_PER_JOB_PAYOUT) > 0:
            try:
                await self.db.add_rep(
                    discord_id=int(claimed_by),
                    amount=int(REP_PER_JOB_PAYOUT),
                    reference=f"job:{job_id_db}|confirm_by:{interaction.user.id}",
                )
                rep_added = int(REP_PER_JOB_PAYOUT)
            except Exception:
                logger.debug("Failed adding rep for job confirm", exc_info=True)

        if interaction.guild:
            member_obj = interaction.guild.get_member(int(claimed_by))
            if member_obj is None:
                try:
                    member_obj = await interaction.guild.fetch_member(int(claimed_by))
                except Exception:
                    member_obj = None
            if member_obj is not None:
                await _sync_member_tier_roles(self.db, member_obj, notify_dm=True, before_level=int(before_level))

        ok = await self.db.mark_paid(job_id_db)
        if not ok:
            return await interaction.followup.send("Could not mark as rewarded (maybe already rewarded).", ephemeral=True)

        min_level = _extract_min_level_from_embed(interaction.message.embeds[0]) if interaction.message.embeds else 0
        updated = _job_embed(job_id_db, title, description, int(reward), "paid", created_by, claimed_by, min_level=min_level)

        files = _logo_files()
        await interaction.message.edit(
            embed=updated,
            view=JobWorkflowView(self.db, status="paid"),
            files=files if files else None,
        )

        if thread_id and interaction.guild:
            try:
                thread = interaction.guild.get_thread(thread_id) or await interaction.guild.fetch_channel(thread_id)
                extra = f"\n+`{rep_added}` Reputation" if rep_added else ""
                await thread.send(f"💰 Org Points rewarded: `{reward:,}` to <@{claimed_by}>. Status: **ORG POINTS REWARDED**.{extra}")
            except Exception:
                logger.debug("Failed sending reward thread update", exc_info=True)

        await interaction.followup.send(f"Job #{job_id_db} confirmed. Org Points rewarded.", ephemeral=True)


class JobsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db

    jobs = discord.SlashCommandGroup("jobs", "Job board commands")

    @jobs.command(name="post", description="Create a job (tier dropdown + form)")
    @jobs_poster_or_admin()
    async def post(self, ctx: discord.ApplicationContext):
        view = JobTierSelectView(self)
        await ctx.respond("Choose the job tier:", view=view, ephemeral=True)

    # COMPLETE (Claimer OR Admin)
    @jobs.command(name="complete", description="Mark a job as completed (claimer or admin)")
    async def complete(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)

        (
            jid,
            channel_id,
            message_id,
            title,
            description,
            reward,
            status,
            created_by,
            claimed_by,
            thread_id,
            created_at,
            updated_at,
        ) = row

        is_owner = claimed_by == ctx.author.id
        is_admin_user = isinstance(ctx.author, discord.Member) and is_admin_member(ctx.author)

        if not (is_owner or is_admin_user):
            return await ctx.respond("Only the claimer or an admin can complete this job.", ephemeral=True)

        ok = await self.db.complete_job(jid)
        if not ok:
            return await ctx.respond(f"Cannot complete Job #{jid} (status: {_status_text(status)}).", ephemeral=True)

        try:
            channel = ctx.guild.get_channel(channel_id)
            msg = await channel.fetch_message(message_id)

            min_level = 0
            if msg.embeds:
                min_level = _extract_min_level_from_embed(msg.embeds[0])

            updated = _job_embed(jid, title, description, int(reward), "completed", created_by, claimed_by, min_level=min_level)
            files = _logo_files()
            await msg.edit(embed=updated, view=JobWorkflowView(self.db, status="completed"), files=files if files else None)
        except Exception:
            pass

        if thread_id:
            try:
                thread = ctx.guild.get_thread(thread_id) or await ctx.guild.fetch_channel(thread_id)
                await thread.send("🧾 Job marked **COMPLETED**. Awaiting finance confirmation.")
            except Exception:
                pass

        await ctx.respond(f"Job #{jid} marked completed.", ephemeral=True)

    # JOBCONFIRM (Finance OR Admin)
    @jobs.command(name="confirm", description="(Finance/Admin) Confirm completed job and reward Org Points")
    @finance_or_admin()
    async def confirm(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)

        (
            jid,
            channel_id,
            message_id,
            title,
            description,
            reward,
            status,
            created_by,
            claimed_by,
            thread_id,
            created_at,
            updated_at,
        ) = row

        if status != "completed":
            return await ctx.respond(f"Job must be COMPLETED before confirmation (status: {_status_text(status)}).", ephemeral=True)
        if not claimed_by:
            return await ctx.respond("No claimer to reward.", ephemeral=True)

        # Reward Org Points
        await self.db.add_balance(
            discord_id=int(claimed_by),
            amount=int(reward),
            tx_type="payout",
            reference=f"job:{jid}|by:{ctx.author.id}",
        )

        # Rep -> level -> role pipeline (with optional DM rank-up)
        member_obj: discord.Member | None = None
        if ctx.guild:
            member_obj = ctx.guild.get_member(int(claimed_by))
            if member_obj is None:
                try:
                    member_obj = await ctx.guild.fetch_member(int(claimed_by))
                except Exception:
                    member_obj = None

        before_level = None
        if member_obj:
            before_level = await self.db.get_level(member_obj.id, per_level=LEVEL_PER_REP)

        rep_added = 0
        if int(REP_PER_JOB_PAYOUT) > 0:
            try:
                await self.db.add_rep(
                    discord_id=int(claimed_by),
                    amount=int(REP_PER_JOB_PAYOUT),
                    reference=f"job:{jid}|payout_by:{ctx.author.id}",
                )
                rep_added = int(REP_PER_JOB_PAYOUT)
            except Exception:
                rep_added = 0

        # Sync tier roles + DM if rank-up
        if member_obj and before_level is not None:
            await _sync_member_tier_roles(self.db, member_obj, notify_dm=True, before_level=int(before_level))

        ok = await self.db.mark_paid(jid)
        if not ok:
            return await ctx.respond("Could not mark as paid (maybe already paid).", ephemeral=True)

        # Update original job message
        try:
            channel = ctx.guild.get_channel(channel_id)
            msg = await channel.fetch_message(message_id)

            min_level = 0
            if msg.embeds:
                min_level = _extract_min_level_from_embed(msg.embeds[0])

            updated = _job_embed(jid, title, description, int(reward), "paid", created_by, claimed_by, min_level=min_level)
            files = _logo_files()
            await msg.edit(embed=updated, view=JobWorkflowView(self.db, status="paid"), files=files if files else None)
        except Exception:
            pass

        # Notify in thread
        if thread_id:
            try:
                thread = ctx.guild.get_thread(thread_id) or await ctx.guild.fetch_channel(thread_id)
                extra = f"\n+`{rep_added}` Reputation" if rep_added else ""
                await thread.send(f"💰 Org Points rewarded: `{reward:,}` to <@{claimed_by}>. Status: **ORG POINTS REWARDED**.{extra}")
            except Exception:
                pass

        await ctx.respond(f"Job #{jid} confirmed. Org Points rewarded.", ephemeral=True)

    # CANCEL (Admin ONLY)
    @jobs.command(name="cancel", description="(Admin) Cancel a job (locks/archives its thread)")
    @admin_only()
    async def cancel(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)

        (
            jid,
            channel_id,
            message_id,
            title,
            description,
            reward,
            status,
            created_by,
            claimed_by,
            thread_id,
            created_at,
            updated_at,
        ) = row

        if status in ("paid", "cancelled"):
            return await ctx.respond(f"Job #{jid} is already {status}.", ephemeral=True)

        ok = await self.db.cancel_job(jid)
        if not ok:
            return await ctx.respond(f"Could not cancel Job #{jid} (status: {_status_text(status)}).", ephemeral=True)

        try:
            channel = ctx.guild.get_channel(channel_id)
            msg = await channel.fetch_message(message_id)

            min_level = 0
            if msg.embeds:
                min_level = _extract_min_level_from_embed(msg.embeds[0])

            updated = _job_embed(jid, title, description, int(reward), "cancelled", created_by, claimed_by, min_level=min_level)
            files = _logo_files()
            await msg.edit(embed=updated, view=None, files=files if files else None)
        except Exception:
            pass

        if thread_id:
            try:
                thread = ctx.guild.get_thread(thread_id) or await ctx.guild.fetch_channel(thread_id)
                await thread.send("🛑 This job has been **CANCELLED** by an admin.")
                await thread.edit(archived=True, locked=True)
            except Exception:
                pass

        await ctx.respond(f"Job #{jid} cancelled.", ephemeral=True)

    # REOPEN (Admin ONLY)
    @jobs.command(name="reopen", description="(Admin) Reopen a cancelled job (sets back to OPEN)")
    @admin_only()
    async def reopen(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)

        (
            jid,
            channel_id,
            message_id,
            title,
            description,
            reward,
            status,
            created_by,
            claimed_by,
            thread_id,
            created_at,
            updated_at,
        ) = row

        if status != "cancelled":
            return await ctx.respond(f"Only cancelled jobs can be reopened (status: {_status_text(status)}).", ephemeral=True)

        try:
            await self.db.conn.execute(
                """
                UPDATE jobs
                SET status='open', claimed_by=NULL, thread_id=NULL, updated_at=datetime('now')
                WHERE job_id=?
                """,
                (int(jid),),
            )
            await self.db.conn.commit()
        except Exception:
            return await ctx.respond("Failed to reopen job (DB error).", ephemeral=True)

        try:
            channel = ctx.guild.get_channel(channel_id)
            msg = await channel.fetch_message(message_id)

            min_level = 0
            if msg.embeds:
                min_level = _extract_min_level_from_embed(msg.embeds[0])

            updated = _job_embed(jid, title, description, int(reward), "open", created_by, None, min_level=min_level)

            files = _logo_files()
            await msg.edit(embed=updated, view=JobWorkflowView(self.db, status="open"), files=files if files else None)
        except Exception:
            pass

        await ctx.respond(f"Job #{jid} reopened and set back to OPEN.", ephemeral=True)


def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore

    bot.add_cog(JobsCog(bot, db))

    # Register persistent workflow view callbacks (Accept/Complete/Confirm).
    bot.add_view(JobWorkflowView(db, status="open"))  # type: ignore
