import os
import re
import logging
from datetime import timedelta
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
EVENT_HANDLER_ROLE_ID = int(os.getenv("EVENT_HANDLER_ROLE_ID", "0") or "0")
JOB_CATEGORY_CHANNEL_MAP_RAW = os.getenv("JOB_CATEGORY_CHANNEL_MAP", "")


def _parse_job_category_channel_map(raw: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in (raw or "").split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        k, v = part.split(":", 1)
        k = k.strip().lower()
        v = v.strip()
        if k and v.isdigit():
            out[k] = int(v)
    return out


JOB_CATEGORY_CHANNEL_MAP = _parse_job_category_channel_map(JOB_CATEGORY_CHANNEL_MAP_RAW)

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
    is_event: bool = False,
    attendee_ids: list[int] | None = None,
    attendance_locked: bool = False,
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
    if is_event:
        attendees = [int(x) for x in (attendee_ids or [])]
        total = len(attendees)
        preview = "\n".join(f"<@{uid}>" for uid in attendees[:8]) if attendees else "—"
        if total > 8:
            preview += f"\n… +{total - 8} more"
        lock_tag = "🔒 Locked" if attendance_locked else "🟢 Live"
        e.add_field(name=f"Participants ({total})", value=preview, inline=True)
        e.add_field(name="Attendance", value=f"RSVP via linked event\n{lock_tag}", inline=True)
    else:
        e.add_field(name="Claimed by", value=f"<@{claimed_by}>" if claimed_by else "—", inline=True)
        e.add_field(name="\u200b", value="\u200b", inline=True)

    if is_event:
        e.set_footer(text="Event job: participation is RSVP-based. No claim required.")
    else:
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


class JobAreaSelectView(discord.ui.View):
    def __init__(self, cog: "JobsCog"):
        super().__init__(timeout=120)
        self.cog = cog

        options = [
            discord.SelectOption(label="General", value="general", description="Miscellaneous jobs"),
            discord.SelectOption(label="Salvage", value="salvage", description="Salvage-focused jobs"),
            discord.SelectOption(label="Mining", value="mining", description="Mining-focused jobs"),
            discord.SelectOption(label="Hauling", value="hauling", description="Hauling-focused jobs"),
            discord.SelectOption(label="Event", value="event", description="Event jobs (scheduled event link)"),
        ]

        self.select = discord.ui.Select(
            placeholder="Choose job area…",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.select.callback = self._on_select  # type: ignore
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        area = str(self.select.values[0]).strip().lower()
        self.select.disabled = True
        self.select.placeholder = f"Area selected ✅ ({area.title()})"

        tier_view = JobTierSelectView(self.cog, category=area)
        await interaction.response.edit_message(
            content=f"Area selected: **{area.title()}**. Now choose the job tier:",
            view=tier_view,
        )


class JobTierSelectView(discord.ui.View):
    def __init__(self, cog: "JobsCog", category: str = "general"):
        super().__init__(timeout=120)
        self.cog = cog
        self.category = str(category).strip().lower() or "general"

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
            JobPostModal(
                self.cog,
                min_level=level,
                source_message=interaction.message,
                source_view=self,
                category=self.category,
            )
        )


class JobPostModal(discord.ui.Modal):
    def __init__(
        self,
        cog: "JobsCog",
        min_level: int,
        source_message: discord.Message | None = None,
        source_view: discord.ui.View | None = None,
        prefill_title: str | None = None,
        prefill_description: str | None = None,
        prefill_reward: int | None = None,
        category: str | None = None,
        template_id: int | None = None,
    ):
        super().__init__(title="Create Job")
        self.cog = cog
        self.min_level = int(min_level)
        self.source_message = source_message
        self.source_view = source_view
        self.category = category
        self.template_id = template_id

        self.job_title = discord.ui.InputText(
            label="Title",
            placeholder="e.g. Shred and Earn",
            value=(prefill_title or "")[:80] if prefill_title else None,
            max_length=80,
        )
        self.job_description = discord.ui.InputText(
            label="Description",
            placeholder="Explain what needs doing, where, requirements, etc.",
            value=(prefill_description or "")[:1000] if prefill_description else None,
            style=discord.InputTextStyle.long,
            max_length=1000,
        )
        self.job_reward = discord.ui.InputText(
            label="Reward (Org Credits)",
            placeholder="e.g. 1000000",
            value=(str(int(prefill_reward)) if prefill_reward is not None else None),
            max_length=12,
        )

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
            if not interaction.guild:
                return await interaction.followup.send("Guild context missing for jobs channel routing.", ephemeral=True)

            category_key = str(self.category or "general").strip().lower()
            routed_id = JOB_CATEGORY_CHANNEL_MAP.get(category_key)
            if routed_id:
                ch = interaction.guild.get_channel(int(routed_id))
                if ch is not None:
                    channel = ch
                elif JOBS_CHANNEL_ID:
                    fallback = interaction.guild.get_channel(JOBS_CHANNEL_ID)
                    if fallback is not None:
                        channel = fallback
            elif JOBS_CHANNEL_ID:
                ch = interaction.guild.get_channel(JOBS_CHANNEL_ID)
                if ch is not None:
                    channel = ch

            if channel is None:
                return await interaction.followup.send("Could not find the channel to post the job in.", ephemeral=True)

            msg = await channel.send(embed=placeholder)

            try:
                job_id = await self.cog.db.create_job(
                    channel_id=channel.id,
                    message_id=msg.id,
                    title=title,
                    description=desc,
                    reward=reward,
                    created_by=interaction.user.id,
                    category=self.category,
                    template_id=self.template_id,
                )
            except ValueError as e:
                await msg.delete()
                return await interaction.followup.send(str(e), ephemeral=True)

            is_event_job = str(self.category or "").strip().lower() == "event"
            embed = _job_embed(
                job_id,
                title,
                desc,
                reward,
                "open",
                interaction.user.id,
                None,
                min_level=self.min_level,
                is_event=is_event_job,
            )

            files = _logo_files()
            await msg.edit(
                embed=embed,
                view=JobWorkflowView(self.cog.db, status="open", is_event=is_event_job),
                files=files if files else None,
            )

            event_note = ""
            if (self.category or "").strip().lower() == "event" and interaction.guild:
                try:
                    start_time = discord.utils.utcnow() + timedelta(minutes=15)
                    end_time = start_time + timedelta(hours=2)
                    sched = await interaction.guild.create_scheduled_event(
                        name=f"Job #{job_id}: {title[:80]}",
                        description=(desc[:1000] if desc else "Org event job"),
                        start_time=start_time,
                        end_time=end_time,
                        location="See linked job post",
                    )
                    if sched is not None:
                        await self.cog.db.link_event_job(int(sched.id), int(job_id))
                        event_note = f"\nEvent created: <https://discord.com/events/{interaction.guild.id}/{sched.id}>"
                except Exception:
                    logger.debug("Failed creating scheduled event for event-category job", exc_info=True)

            posted_in = f" in <#{channel.id}>" if getattr(channel, "id", None) else ""
            await interaction.followup.send(
                f"Job #{job_id} posted{posted_in}. Tier: {_tier_display(self.min_level)}{event_note}",
                ephemeral=True,
            )

            if self.source_message and self.source_view:
                try:
                    await self.source_message.edit(
                        content=(
                            f"Area/Tier selected ✅ ({(self.category or 'general').title()} / {_tier_display(self.min_level)}). "
                            f"Job #{job_id} created."
                        ),
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


class JobTemplateModal(discord.ui.Modal):
    def __init__(
        self,
        cog: "JobsCog",
        existing: tuple | None = None,
        force_category: str | None = None,
    ):
        title = "Update Job Template" if existing else "Create Job Template"
        super().__init__(title=title)
        self.cog = cog
        self.force_category = str(force_category).strip().lower() if force_category else None

        existing_name = str(existing[1]) if existing else ""
        existing_title = str(existing[2]) if existing else ""
        existing_desc = str(existing[3]) if existing else ""
        existing_rmin = str(int(existing[4])) if existing else "0"
        existing_rmax = str(int(existing[5])) if existing else "0"
        existing_tier = str(int(existing[6])) if existing else "0"
        existing_category = str(existing[7] or "general") if existing else "general"

        self.template_name = discord.ui.InputText(label="Template Name", value=existing_name[:80] if existing_name else None, max_length=80)
        self.template_title = discord.ui.InputText(label="Default Job Title", value=existing_title[:80] if existing_title else None, max_length=80)
        self.template_description = discord.ui.InputText(
            label="Default Description",
            value=existing_desc[:1000] if existing_desc else None,
            style=discord.InputTextStyle.long,
            max_length=1000,
        )
        self.template_reward_range = discord.ui.InputText(
            label="Reward Range (min,max)",
            value=f"{existing_rmin},{existing_rmax}",
            placeholder="e.g. 500000,1000000",
            max_length=40,
        )
        self.template_tier_category = discord.ui.InputText(
            label="Tier,Category",
            value=f"{existing_tier},{existing_category}"[:100],
            placeholder="e.g. 5,event",
            max_length=100,
        )

        self.add_item(self.template_name)
        self.add_item(self.template_title)
        self.add_item(self.template_description)
        self.add_item(self.template_reward_range)
        self.add_item(self.template_tier_category)

    async def callback(self, interaction: discord.Interaction):
        name = (self.template_name.value or "").strip()
        title = (self.template_title.value or "").strip()
        description = (self.template_description.value or "").strip()
        reward_range_raw = (self.template_reward_range.value or "").strip()
        tier_category_raw = (self.template_tier_category.value or "").strip()

        rr_parts = [p.strip().replace(",", "") for p in reward_range_raw.split(",")]
        if len(rr_parts) != 2:
            return await interaction.response.send_message("Reward range must be `min,max`.", ephemeral=True)
        reward_min_raw, reward_max_raw = rr_parts

        tc_parts = [p.strip() for p in tier_category_raw.split(",", 1)]
        if len(tc_parts) != 2:
            return await interaction.response.send_message("Tier/category must be `tier,category`.", ephemeral=True)
        tier_raw, category = tc_parts
        category = category or "general"
        if self.force_category:
            category = self.force_category

        if not name:
            return await interaction.response.send_message("Template name is required.", ephemeral=True)
        if not title:
            return await interaction.response.send_message("Default title is required.", ephemeral=True)
        if not description:
            return await interaction.response.send_message("Default description is required.", ephemeral=True)
        if not reward_min_raw.isdigit() or not reward_max_raw.isdigit() or not tier_raw.isdigit():
            return await interaction.response.send_message("Reward min/max and tier must be whole numbers.", ephemeral=True)

        reward_min = int(reward_min_raw)
        reward_max = int(reward_max_raw)
        tier_required = int(tier_raw)

        if reward_min < 0 or reward_max < 0 or reward_max < reward_min:
            return await interaction.response.send_message("Invalid reward range.", ephemeral=True)

        template_id = await self.cog.db.upsert_job_template(
            name=name,
            default_title=title,
            default_description=description,
            default_reward_min=reward_min,
            default_reward_max=reward_max,
            default_tier_required=tier_required,
            category=category,
            active=True,
        )
        await interaction.response.send_message(f"Template `{name}` saved (id `{template_id}`).", ephemeral=True)


class JobWorkflowView(discord.ui.View):
    """Three-stage job workflow via buttons: Accept -> Complete -> Confirm."""

    def __init__(self, db: Database, status: str = "open", is_event: bool = False):
        super().__init__(timeout=None)
        self.db = db
        self.is_event = bool(is_event)

        if self.is_event:
            self.remove_item(self.accept_btn)

        if status == "open":
            self.complete_btn.disabled = True
            self.confirm_btn.disabled = True
            if self.is_event:
                self.remove_item(self.complete_btn)
                self.remove_item(self.confirm_btn)
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

        category = await self.db.get_job_category(int(job_id_db))
        if str(category or "").strip().lower() == "event":
            return await interaction.followup.send(
                "Event jobs use RSVP attendance. Please mark Interested/Going on the linked event instead of claiming.",
                ephemeral=True,
            )

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
        category = await self.db.get_job_category(int(job_id_db))
        is_event_job = str(category or "").strip().lower() == "event"
        updated = _job_embed(
            job_id_db,
            title,
            description,
            int(reward),
            "completed",
            created_by,
            claimed_by,
            min_level=min_level,
            is_event=is_event_job,
        )

        files = _logo_files()
        await interaction.message.edit(
            embed=updated,
            view=JobWorkflowView(self.db, status="completed", is_event=is_event_job),
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

        category = await self.db.get_job_category(int(job_id_db))
        payout_targets: list[tuple[int, int]] = []

        if category == "event":
            if not await self.db.get_job_attendance_lock(int(job_id_db)):
                attendees_live = await self.db.list_event_attendees(int(job_id_db))
                attendee_ids_live = [int(a[0]) for a in attendees_live]
                await self.db.set_job_attendance_snapshot(int(job_id_db), attendee_ids_live)
                await self.db.set_job_attendance_lock(int(job_id_db), True)

            attendee_ids = await self.db.get_job_attendance_snapshot(int(job_id_db))
            if not attendee_ids:
                return await interaction.followup.send(
                    "Attendance snapshot is empty. Run `/jobs attendance_sync` (or unlock/re-lock) before confirming.",
                    ephemeral=True,
                )

            base = int(reward) // len(attendee_ids)
            remainder = int(reward) % len(attendee_ids)
            for i, uid in enumerate(attendee_ids):
                amt = int(base) + (1 if i < remainder else 0)
                if amt > 0:
                    payout_targets.append((uid, amt))
            if not payout_targets:
                return await interaction.followup.send("Event reward is too low to distribute.", ephemeral=True)
        else:
            if not claimed_by:
                return await interaction.followup.send("No claimer to reward.", ephemeral=True)
            payout_targets.append((int(claimed_by), int(reward)))

        try:
            ok = await self.db.mark_paid(job_id_db)
        except ValueError as e:
            return await interaction.followup.send(f"Cannot confirm job: {e}", ephemeral=True)

        if not ok:
            return await interaction.followup.send("Could not mark as rewarded (maybe already rewarded).", ephemeral=True)

        rep_added_total = 0
        payout_note_parts: list[str] = []
        for uid, amount in payout_targets:
            await self.db.add_balance(
                discord_id=int(uid),
                amount=int(amount),
                tx_type="payout",
                reference=f"job:{job_id_db}|by:{interaction.user.id}",
            )
            payout_note_parts.append(f"{uid}:{int(amount)}")

            before_level = await self.db.get_level(int(uid), per_level=LEVEL_PER_REP)
            if int(REP_PER_JOB_PAYOUT) > 0:
                try:
                    await self.db.add_rep(
                        discord_id=int(uid),
                        amount=int(REP_PER_JOB_PAYOUT),
                        reference=f"job:{job_id_db}|confirm_by:{interaction.user.id}",
                    )
                    rep_added_total += int(REP_PER_JOB_PAYOUT)
                except Exception:
                    logger.debug("Failed adding rep for job confirm", exc_info=True)

            if interaction.guild:
                member_obj = interaction.guild.get_member(int(uid))
                if member_obj is None:
                    try:
                        member_obj = await interaction.guild.fetch_member(int(uid))
                    except Exception:
                        member_obj = None
                if member_obj is not None:
                    await _sync_member_tier_roles(self.db, member_obj, notify_dm=True, before_level=int(before_level))

        if category == "event":
            await self.db.add_ledger_entry(
                entry_type="event_payout_snapshot",
                amount=int(reward),
                from_account=f"job:{int(job_id_db)}",
                to_account=f"attendees:{len(payout_targets)}",
                reference_type="job",
                reference_id=str(int(job_id_db)),
                notes=";".join(payout_note_parts),
            )
            await self.db.conn.commit()

        min_level = _extract_min_level_from_embed(interaction.message.embeds[0]) if interaction.message.embeds else 0
        is_event_job = str(category or "").strip().lower() == "event"
        updated = _job_embed(
            job_id_db,
            title,
            description,
            int(reward),
            "paid",
            created_by,
            claimed_by,
            min_level=min_level,
            is_event=is_event_job,
        )

        files = _logo_files()
        await interaction.message.edit(
            embed=updated,
            view=JobWorkflowView(self.db, status="paid", is_event=is_event_job),
            files=files if files else None,
        )

        if thread_id and interaction.guild:
            try:
                thread = interaction.guild.get_thread(thread_id) or await interaction.guild.fetch_channel(thread_id)
                if category == "event":
                    extra = f"\n+`{rep_added_total}` Reputation total" if rep_added_total else ""
                    await thread.send(
                        f"💰 Event payout complete: `{reward:,}` split across `{len(payout_targets)}` attendees."
                        f" Status: **ORG POINTS REWARDED**.{extra}"
                    )
                else:
                    target_uid = int(payout_targets[0][0])
                    extra = f"\n+`{rep_added_total}` Reputation" if rep_added_total else ""
                    await thread.send(f"💰 Org Points rewarded: `{reward:,}` to <@{target_uid}>. Status: **ORG POINTS REWARDED**.{extra}")
            except Exception:
                logger.debug("Failed sending reward thread update", exc_info=True)

        await interaction.followup.send(f"Job #{job_id_db} confirmed. Org Points rewarded.", ephemeral=True)


class JobsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db
        self._startup_event_refresh_done = False

    async def _refresh_event_job_card(self, job_id: int) -> None:
        row = await self.db.get_job(int(job_id))
        if not row:
            return

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

        category = await self.db.get_job_category(int(jid))
        if str(category or "").strip().lower() != "event":
            return

        guild = self.bot.guilds[0] if self.bot.guilds else None
        if guild is None:
            return

        channel = guild.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await guild.fetch_channel(int(channel_id))
            except Exception:
                return

        try:
            msg = await channel.fetch_message(int(message_id))
        except Exception:
            return

        min_level = _extract_min_level_from_embed(msg.embeds[0]) if msg.embeds else 0
        locked = await self.db.get_job_attendance_lock(int(jid))
        attendee_ids = await self.db.get_job_attendance_snapshot(int(jid)) if locked else [int(a[0]) for a in await self.db.list_event_attendees(int(jid))]

        updated = _job_embed(
            int(jid),
            str(title),
            str(description),
            int(reward),
            str(status),
            int(created_by),
            int(claimed_by) if claimed_by else None,
            min_level=int(min_level),
            is_event=True,
            attendee_ids=attendee_ids,
            attendance_locked=bool(locked),
        )

        files = _logo_files()
        await msg.edit(
            embed=updated,
            view=JobWorkflowView(self.db, status=str(status), is_event=True) if str(status) != "cancelled" else None,
            files=files if files else None,
        )

    async def _refresh_all_event_job_cards(self, limit: int = 250) -> int:
        cur = await self.db.conn.execute(
            "SELECT job_id FROM jobs WHERE status != 'cancelled' ORDER BY job_id DESC LIMIT ?",
            (int(limit),),
        )
        rows = await cur.fetchall()
        refreshed = 0
        for r in rows:
            jid = int(r[0])
            try:
                category = await self.db.get_job_category(int(jid))
                if str(category or "").strip().lower() != "event":
                    continue
                await self._refresh_event_job_card(int(jid))
                refreshed += 1
            except Exception:
                logger.debug("Failed refreshing event job card for %s", jid, exc_info=True)
        return refreshed

    @commands.Cog.listener()
    async def on_ready(self):
        if self._startup_event_refresh_done:
            return
        self._startup_event_refresh_done = True
        try:
            count = await self._refresh_all_event_job_cards(limit=250)
            logger.info("Startup event job card refresh complete: %s cards", count)
        except Exception:
            logger.debug("Startup event job card refresh failed", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_scheduled_event_user_add(self, payload: discord.RawScheduledEventSubscription):
        try:
            job_id = await self.db.get_job_id_by_event(int(payload.event_id))
            if not job_id:
                return
            await self.db.add_event_attendee(int(job_id), int(payload.user_id))
            await self._refresh_event_job_card(int(job_id))
        except Exception:
            logger.debug("Failed syncing scheduled event RSVP add", exc_info=True)

    @commands.Cog.listener()
    async def on_raw_scheduled_event_user_remove(self, payload: discord.RawScheduledEventSubscription):
        try:
            job_id = await self.db.get_job_id_by_event(int(payload.event_id))
            if not job_id:
                return
            await self.db.remove_event_attendee(int(job_id), int(payload.user_id))
            await self._refresh_event_job_card(int(job_id))
        except Exception:
            logger.debug("Failed syncing scheduled event RSVP remove", exc_info=True)

    async def _sync_attendance_from_event(self, job_id: int) -> int:
        cur = await self.db.conn.execute("SELECT event_id FROM job_event_links WHERE job_id=?", (int(job_id),))
        row = await cur.fetchone()
        if not row:
            raise ValueError("No linked scheduled event found for this job.")

        event_id = int(row[0])
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if guild is None:
            raise ValueError("Guild context unavailable for event sync.")

        event = guild.get_scheduled_event(event_id)
        if event is None:
            try:
                event = await guild.fetch_scheduled_event(event_id)
            except Exception as e:
                raise ValueError(f"Could not fetch scheduled event {event_id}: {e}")

        existing = await self.db.list_event_attendees(int(job_id))
        existing_ids = {int(a[0]) for a in existing}

        seen_ids: set[int] = set()
        async for u in event.subscribers(limit=None, as_member=True):
            uid = int(u.id)
            seen_ids.add(uid)
            if uid not in existing_ids:
                await self.db.add_event_attendee(int(job_id), uid)

        for uid in existing_ids:
            if uid not in seen_ids:
                await self.db.remove_event_attendee(int(job_id), int(uid))

        return len(seen_ids)

    jobs = discord.SlashCommandGroup("jobs", "Job board commands")
    eventjob = discord.SlashCommandGroup("eventjob", "Event job posting commands")
    eventtemplate = discord.SlashCommandGroup("eventtemplate", "Event template admin commands")
    jobtest = discord.SlashCommandGroup("jobtest", "Job event self-test/admin tools")

    async def _open_template_post_modal(self, ctx: discord.ApplicationContext, template_name: str, require_event: bool = False):
        row = await self.db.get_job_template_by_name(str(template_name))
        if not row:
            return await ctx.respond(f"Template `{template_name}` not found.", ephemeral=True)

        (
            template_id,
            resolved_name,
            default_title,
            default_description,
            default_reward_min,
            default_reward_max,
            default_tier_required,
            category,
            active,
        ) = row

        category_norm = str(category or "").strip().lower()
        if require_event and category_norm != "event":
            return await ctx.respond(f"Template `{resolved_name}` is not an event template.", ephemeral=True)

        if int(active) != 1:
            return await ctx.respond(f"Template `{resolved_name}` is inactive.", ephemeral=True)

        if category_norm == "event" and EVENT_HANDLER_ROLE_ID:
            member = ctx.author if isinstance(ctx.author, discord.Member) else None
            has_event_handler = bool(member and any(int(r.id) == int(EVENT_HANDLER_ROLE_ID) for r in member.roles))
            if not has_event_handler and not (member and is_admin_member(member)):
                return await ctx.respond("Only Event Handlers (or admins) can post event templates.", ephemeral=True)

        default_reward = int(default_reward_min or 0) or int(default_reward_max or 0) or 1000
        await ctx.send_modal(
            JobPostModal(
                self,
                min_level=int(default_tier_required or 0),
                prefill_title=str(default_title),
                prefill_description=str(default_description),
                prefill_reward=int(default_reward),
                category=(str(category) if category else None),
                template_id=int(template_id),
            )
        )

    @jobs.command(name="post", description="Create a job (area -> tier -> form)")
    @jobs_poster_or_admin()
    async def post(self, ctx: discord.ApplicationContext):
        view = JobAreaSelectView(self)
        await ctx.respond("Choose the job area:", view=view, ephemeral=True)

    @eventjob.command(name="post", description="Post an event job from an event template")
    @jobs_poster_or_admin()
    async def event_post(self, ctx: discord.ApplicationContext, template: str):
        return await self._open_template_post_modal(ctx, template, require_event=True)

    @eventjob.command(name="attendee_add", description="(Finance/Admin) Manually add attendee to event job")
    @finance_or_admin()
    async def event_attendee_add(self, ctx: discord.ApplicationContext, job_id: int, member: discord.Member):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        category = await self.db.get_job_category(int(job_id))
        if str(category or "").strip().lower() != "event":
            return await ctx.respond("This command is only for event jobs.", ephemeral=True)

        ok = await self.db.add_event_attendee_force(int(job_id), int(member.id))
        if not ok:
            return await ctx.respond(f"<@{member.id}> is already on attendance for Job #{int(job_id)}.", ephemeral=True)
        await self._refresh_event_job_card(int(job_id))
        await ctx.respond(f"Added <@{member.id}> to attendance for Job #{int(job_id)}.", ephemeral=True)

    @eventjob.command(name="attendee_remove", description="(Finance/Admin) Manually remove attendee from event job")
    @finance_or_admin()
    async def event_attendee_remove(self, ctx: discord.ApplicationContext, job_id: int, member: discord.Member):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        category = await self.db.get_job_category(int(job_id))
        if str(category or "").strip().lower() != "event":
            return await ctx.respond("This command is only for event jobs.", ephemeral=True)

        ok = await self.db.remove_event_attendee_force(int(job_id), int(member.id))
        if not ok:
            return await ctx.respond(f"<@{member.id}> was not on attendance for Job #{int(job_id)}.", ephemeral=True)
        await self._refresh_event_job_card(int(job_id))
        await ctx.respond(f"Removed <@{member.id}> from attendance for Job #{int(job_id)}.", ephemeral=True)

    @eventjob.command(name="attendee_list", description="List attendees for an event job")
    async def event_attendee_list(self, ctx: discord.ApplicationContext, job_id: int):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        category = await self.db.get_job_category(int(job_id))
        if str(category or "").strip().lower() != "event":
            return await ctx.respond("This command is only for event jobs.", ephemeral=True)

        attendees = await self.db.list_event_attendees(int(job_id))
        if not attendees:
            return await ctx.respond(f"No attendees tracked for Job #{int(job_id)}.", ephemeral=True)

        mentions = [f"<@{int(a[0])}>" for a in attendees[:75]]
        await ctx.respond(f"Event attendees for Job #{int(job_id)}:\n" + "\n".join(mentions), ephemeral=True)

    @eventtemplate.command(name="add", description="(Admin) Create an event template (modal)")
    @admin_only()
    async def event_template_add(self, ctx: discord.ApplicationContext):
        await ctx.send_modal(JobTemplateModal(self, force_category="event"))

    @eventtemplate.command(name="update", description="(Admin) Update an event template (modal)")
    @admin_only()
    async def event_template_update(self, ctx: discord.ApplicationContext, name: str):
        row = await self.db.get_job_template_by_name(str(name))
        if not row:
            return await ctx.respond(f"Template `{name}` not found.", ephemeral=True)
        if str(row[7] or "").strip().lower() != "event":
            return await ctx.respond(f"Template `{name}` is not an event template.", ephemeral=True)
        await ctx.send_modal(JobTemplateModal(self, existing=row, force_category="event"))

    @eventtemplate.command(name="list", description="List event templates")
    async def event_template_list(self, ctx: discord.ApplicationContext, include_inactive: bool = True):
        rows = await self.db.list_job_templates(include_inactive=bool(include_inactive), limit=100)
        event_rows = [r for r in rows if str(r[7] or "").strip().lower() == "event"]
        if not event_rows:
            return await ctx.respond("No event templates found.", ephemeral=True)

        lines = []
        for r in event_rows[:25]:
            template_id, name, default_title, default_description, rmin, rmax, tier_required, category, active = r
            state = "active" if int(active) == 1 else "inactive"
            lines.append(
                f"• `{name}` ({state}) — reward `{int(rmin):,}`-`{int(rmax):,}`, tier `{int(tier_required)}+`"
            )
        await ctx.respond("\n".join(lines), ephemeral=True)

    @eventtemplate.command(name="view", description="View one event template")
    async def event_template_view(self, ctx: discord.ApplicationContext, name: str):
        row = await self.db.get_job_template_by_name(str(name))
        if not row:
            return await ctx.respond(f"Template `{name}` not found.", ephemeral=True)
        if str(row[7] or "").strip().lower() != "event":
            return await ctx.respond(f"Template `{name}` is not an event template.", ephemeral=True)

        template_id, tname, title, description, rmin, rmax, tier_required, category, active = row
        state = "active" if int(active) == 1 else "inactive"
        await ctx.respond(
            f"Event Template `{tname}` (id `{template_id}`, {state})\n"
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Reward range: `{int(rmin):,}`-`{int(rmax):,}`\n"
            f"Tier required: `{int(tier_required)}`",
            ephemeral=True,
        )

    @eventtemplate.command(name="clone", description="(Admin) Clone an event template")
    @admin_only()
    async def event_template_clone(self, ctx: discord.ApplicationContext, source_name: str, new_name: str):
        row = await self.db.get_job_template_by_name(str(source_name))
        if not row:
            return await ctx.respond(f"Template `{source_name}` not found.", ephemeral=True)
        if str(row[7] or "").strip().lower() != "event":
            return await ctx.respond(f"Template `{source_name}` is not an event template.", ephemeral=True)

        _, _, title, description, rmin, rmax, tier_required, category, active = row
        template_id = await self.db.upsert_job_template(
            name=str(new_name).strip(),
            default_title=str(title),
            default_description=str(description),
            default_reward_min=int(rmin),
            default_reward_max=int(rmax),
            default_tier_required=int(tier_required),
            category="event",
            active=bool(int(active) == 1),
        )
        await ctx.respond(f"Event template cloned: `{source_name}` -> `{new_name}` (id `{template_id}`).", ephemeral=True)

    @eventtemplate.command(name="disable", description="(Admin) Disable an event template")
    @admin_only()
    async def event_template_disable(self, ctx: discord.ApplicationContext, name: str):
        row = await self.db.get_job_template_by_name(str(name))
        if not row or str(row[7] or "").strip().lower() != "event":
            return await ctx.respond(f"Event template `{name}` not found.", ephemeral=True)
        ok = await self.db.set_job_template_active(name=name, active=False)
        if not ok:
            return await ctx.respond(f"Event template `{name}` not found.", ephemeral=True)
        await ctx.respond(f"Event template `{name}` disabled.", ephemeral=True)

    @eventtemplate.command(name="enable", description="(Admin) Enable an event template")
    @admin_only()
    async def event_template_enable(self, ctx: discord.ApplicationContext, name: str):
        row = await self.db.get_job_template_by_name(str(name))
        if not row or str(row[7] or "").strip().lower() != "event":
            return await ctx.respond(f"Event template `{name}` not found.", ephemeral=True)
        ok = await self.db.set_job_template_active(name=name, active=True)
        if not ok:
            return await ctx.respond(f"Event template `{name}` not found.", ephemeral=True)
        await ctx.respond(f"Event template `{name}` enabled.", ephemeral=True)

    @eventtemplate.command(name="delete", description="(Admin) Delete an event template")
    @admin_only()
    async def event_template_delete(self, ctx: discord.ApplicationContext, name: str):
        row = await self.db.get_job_template_by_name(str(name))
        if not row or str(row[7] or "").strip().lower() != "event":
            return await ctx.respond(f"Event template `{name}` not found.", ephemeral=True)
        ok = await self.db.delete_job_template(name=name)
        if not ok:
            return await ctx.respond(f"Event template `{name}` not found.", ephemeral=True)
        await ctx.respond(f"Event template `{name}` deleted.", ephemeral=True)

    @jobs.command(name="attend", description="Join an event job attendance list")
    async def attend(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)

        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)

        status = str(row[6])
        if status in ("paid", "cancelled"):
            return await ctx.respond(f"This event is closed (status: {_status_text(status)}).", ephemeral=True)

        added = await self.db.add_event_attendee(int(job_id), int(ctx.author.id))
        if not added:
            return await ctx.respond(f"You are already on attendance for Job #{int(job_id)}.", ephemeral=True)

        await self._refresh_event_job_card(int(job_id))
        await ctx.respond(f"You are marked as attending Job #{int(job_id)}.", ephemeral=True)

    @jobs.command(name="unattend", description="Leave an event job attendance list")
    async def unattend(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)

        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)

        removed = await self.db.remove_event_attendee(int(job_id), int(ctx.author.id))
        if not removed:
            return await ctx.respond(f"You were not on attendance for Job #{int(job_id)}.", ephemeral=True)

        await self._refresh_event_job_card(int(job_id))
        await ctx.respond(f"You have been removed from attendance for Job #{int(job_id)}.", ephemeral=True)

    @jobs.command(name="attendees", description="Show current event attendees for a job")
    async def attendees(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)

        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)

        attendees = await self.db.list_event_attendees(int(job_id))
        if not attendees:
            return await ctx.respond(f"No attendees tracked yet for Job #{int(job_id)}.", ephemeral=True)

        mentions = [f"<@{int(a[0])}>" for a in attendees[:50]]
        await ctx.respond(f"Event attendees for Job #{int(job_id)}:\n" + "\n".join(mentions), ephemeral=True)

    @jobs.command(name="attendance_lock", description="(Finance/Admin) Lock event attendance list")
    @finance_or_admin()
    async def attendance_lock(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)

        attendees = await self.db.list_event_attendees(int(job_id))
        attendee_ids = [int(a[0]) for a in attendees]
        await self.db.set_job_attendance_snapshot(int(job_id), attendee_ids)
        await self.db.set_job_attendance_lock(int(job_id), True)
        await self._refresh_event_job_card(int(job_id))
        await ctx.respond(f"Attendance locked for Job #{int(job_id)} with `{len(attendee_ids)}` attendees.", ephemeral=True)

    @jobs.command(name="attendance_unlock", description="(Finance/Admin) Unlock event attendance list")
    @finance_or_admin()
    async def attendance_unlock(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)
        await self.db.set_job_attendance_lock(int(job_id), False)
        await self._refresh_event_job_card(int(job_id))
        await ctx.respond(f"Attendance unlocked for Job #{int(job_id)}.", ephemeral=True)

    @jobs.command(name="attendance_sync", description="(Finance/Admin) Force-sync attendance from scheduled event RSVPs")
    @finance_or_admin()
    async def attendance_sync(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        status = str(row[6])
        if status in ("paid", "cancelled"):
            return await ctx.respond(f"This event is closed (status: {_status_text(status)}).", ephemeral=True)
        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)
        if await self.db.get_job_attendance_lock(int(job_id)):
            return await ctx.respond("Attendance is locked for this job. Unlock before sync.", ephemeral=True)
        try:
            count = await self._sync_attendance_from_event(int(job_id))
        except ValueError as e:
            return await ctx.respond(str(e), ephemeral=True)
        await self._refresh_event_job_card(int(job_id))
        await ctx.respond(f"Attendance synced for Job #{int(job_id)}. Tracked attendees: `{int(count)}`.", ephemeral=True)

    # COMPLETE (Claimer OR Admin)
    @jobtest.command(name="event_sync_check", description="(Admin) Check linked event + RSVP counts")
    @admin_only()
    async def event_sync_check(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)

        cur = await self.db.conn.execute("SELECT event_id FROM job_event_links WHERE job_id=?", (int(job_id),))
        link = await cur.fetchone()
        if not link:
            return await ctx.respond("No linked scheduled event found for this job.", ephemeral=True)

        event_id = int(link[0])
        guild = ctx.guild
        if guild is None:
            return await ctx.respond("Guild context required.", ephemeral=True)

        event = guild.get_scheduled_event(event_id)
        if event is None:
            try:
                event = await guild.fetch_scheduled_event(event_id)
            except Exception as e:
                return await ctx.respond(f"Linked event fetch failed: {e}", ephemeral=True)

        subs = 0
        async for _ in event.subscribers(limit=None, as_member=True):
            subs += 1

        tracked = await self.db.list_event_attendees(int(job_id))
        await ctx.respond(
            f"Event sync check for Job #{int(job_id)}\n"
            f"Linked event: `{event_id}`\n"
            f"RSVP subscribers: `{subs}`\n"
            f"Tracked attendees: `{len(tracked)}`",
            ephemeral=True,
        )

    @jobtest.command(name="event_dryrun_payout", description="(Admin) Preview event payout split without paying")
    @admin_only()
    async def event_dryrun_payout(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        reward = int(row[5])
        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)

        locked = await self.db.get_job_attendance_lock(int(job_id))
        attendee_ids = await self.db.get_job_attendance_snapshot(int(job_id)) if locked else [int(a[0]) for a in await self.db.list_event_attendees(int(job_id))]
        if not attendee_ids:
            return await ctx.respond("No attendees available for payout preview.", ephemeral=True)

        base = reward // len(attendee_ids)
        remainder = reward % len(attendee_ids)
        lines = []
        for i, uid in enumerate(attendee_ids[:40]):
            amt = int(base) + (1 if i < remainder else 0)
            lines.append(f"<@{uid}> -> `{amt:,}`")

        await ctx.respond(
            f"Dry-run payout for Job #{int(job_id)} (reward `{reward:,}` over `{len(attendee_ids)}` attendees, locked={locked})\n"
            + "\n".join(lines),
            ephemeral=True,
        )

    @jobtest.command(name="event_force_snapshot", description="(Admin) Sync RSVPs then snapshot+lock attendance")
    @admin_only()
    async def event_force_snapshot(self, ctx: discord.ApplicationContext, job_id: discord.Option(int, min_value=1)):
        row = await self.db.get_job(int(job_id))
        if not row:
            return await ctx.respond("Job not found.", ephemeral=True)
        category = await self.db.get_job_category(int(job_id))
        if category != "event":
            return await ctx.respond("This command is only for event-category jobs.", ephemeral=True)

        await self.db.set_job_attendance_lock(int(job_id), False)
        count = await self._sync_attendance_from_event(int(job_id))
        attendees = await self.db.list_event_attendees(int(job_id))
        attendee_ids = [int(a[0]) for a in attendees]
        await self.db.set_job_attendance_snapshot(int(job_id), attendee_ids)
        await self.db.set_job_attendance_lock(int(job_id), True)
        await self._refresh_event_job_card(int(job_id))

        await ctx.respond(
            f"Snapshot locked for Job #{int(job_id)}. Synced RSVPs: `{int(count)}`, snapshot size: `{len(attendee_ids)}`.",
            ephemeral=True,
        )

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

            category = await self.db.get_job_category(int(jid))
            is_event_job = str(category or "").strip().lower() == "event"
            updated = _job_embed(
                jid,
                title,
                description,
                int(reward),
                "completed",
                created_by,
                claimed_by,
                min_level=min_level,
                is_event=is_event_job,
            )
            files = _logo_files()
            await msg.edit(
                embed=updated,
                view=JobWorkflowView(self.db, status="completed", is_event=is_event_job),
                files=files if files else None,
            )
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

        category = await self.db.get_job_category(int(jid))
        payout_targets: list[tuple[int, int]] = []

        if category == "event":
            if not await self.db.get_job_attendance_lock(int(jid)):
                attendees_live = await self.db.list_event_attendees(int(jid))
                attendee_ids_live = [int(a[0]) for a in attendees_live]
                await self.db.set_job_attendance_snapshot(int(jid), attendee_ids_live)
                await self.db.set_job_attendance_lock(int(jid), True)

            attendee_ids = await self.db.get_job_attendance_snapshot(int(jid))
            if not attendee_ids:
                return await ctx.respond(
                    "Attendance snapshot is empty. Run `/jobs attendance_sync` (or unlock/re-lock) before confirming.",
                    ephemeral=True,
                )

            base = int(reward) // len(attendee_ids)
            remainder = int(reward) % len(attendee_ids)
            for i, uid in enumerate(attendee_ids):
                amt = int(base) + (1 if i < remainder else 0)
                if amt > 0:
                    payout_targets.append((uid, amt))
            if not payout_targets:
                return await ctx.respond("Event reward is too low to distribute.", ephemeral=True)
        else:
            if not claimed_by:
                return await ctx.respond("No claimer to reward.", ephemeral=True)
            payout_targets.append((int(claimed_by), int(reward)))

        try:
            ok = await self.db.mark_paid(jid)
        except ValueError as e:
            return await ctx.respond(f"Cannot confirm job: {e}", ephemeral=True)

        if not ok:
            return await ctx.respond("Could not mark as paid (maybe already paid).", ephemeral=True)

        rep_added_total = 0
        payout_note_parts: list[str] = []
        for uid, amount in payout_targets:
            await self.db.add_balance(
                discord_id=int(uid),
                amount=int(amount),
                tx_type="payout",
                reference=f"job:{jid}|by:{ctx.author.id}",
            )
            payout_note_parts.append(f"{uid}:{int(amount)}")

            member_obj: discord.Member | None = None
            if ctx.guild:
                member_obj = ctx.guild.get_member(int(uid))
                if member_obj is None:
                    try:
                        member_obj = await ctx.guild.fetch_member(int(uid))
                    except Exception:
                        member_obj = None

            before_level = None
            if member_obj:
                before_level = await self.db.get_level(member_obj.id, per_level=LEVEL_PER_REP)

            if int(REP_PER_JOB_PAYOUT) > 0:
                try:
                    await self.db.add_rep(
                        discord_id=int(uid),
                        amount=int(REP_PER_JOB_PAYOUT),
                        reference=f"job:{jid}|payout_by:{ctx.author.id}",
                    )
                    rep_added_total += int(REP_PER_JOB_PAYOUT)
                except Exception:
                    pass

            if member_obj and before_level is not None:
                await _sync_member_tier_roles(self.db, member_obj, notify_dm=True, before_level=int(before_level))

        if category == "event":
            await self.db.add_ledger_entry(
                entry_type="event_payout_snapshot",
                amount=int(reward),
                from_account=f"job:{int(jid)}",
                to_account=f"attendees:{len(payout_targets)}",
                reference_type="job",
                reference_id=str(int(jid)),
                notes=";".join(payout_note_parts),
            )
            await self.db.conn.commit()

        # Update original job message
        try:
            channel = ctx.guild.get_channel(channel_id)
            msg = await channel.fetch_message(message_id)

            min_level = 0
            if msg.embeds:
                min_level = _extract_min_level_from_embed(msg.embeds[0])

            is_event_job = str(category or "").strip().lower() == "event"
            updated = _job_embed(
                jid,
                title,
                description,
                int(reward),
                "paid",
                created_by,
                claimed_by,
                min_level=min_level,
                is_event=is_event_job,
            )
            files = _logo_files()
            await msg.edit(
                embed=updated,
                view=JobWorkflowView(self.db, status="paid", is_event=is_event_job),
                files=files if files else None,
            )
        except Exception:
            pass

        # Notify in thread
        if thread_id:
            try:
                thread = ctx.guild.get_thread(thread_id) or await ctx.guild.fetch_channel(thread_id)
                if category == "event":
                    extra = f"\n+`{rep_added_total}` Reputation total" if rep_added_total else ""
                    await thread.send(
                        f"💰 Event payout complete: `{reward:,}` split across `{len(payout_targets)}` attendees."
                        f" Status: **ORG POINTS REWARDED**.{extra}"
                    )
                else:
                    target_uid = int(payout_targets[0][0])
                    extra = f"\n+`{rep_added_total}` Reputation" if rep_added_total else ""
                    await thread.send(f"💰 Org Points rewarded: `{reward:,}` to <@{target_uid}>. Status: **ORG POINTS REWARDED**.{extra}")
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

            category = await self.db.get_job_category(int(jid))
            is_event_job = str(category or "").strip().lower() == "event"
            updated = _job_embed(
                jid,
                title,
                description,
                int(reward),
                "cancelled",
                created_by,
                claimed_by,
                min_level=min_level,
                is_event=is_event_job,
            )
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

            category = await self.db.get_job_category(int(jid))
            is_event_job = str(category or "").strip().lower() == "event"
            updated = _job_embed(
                jid,
                title,
                description,
                int(reward),
                "open",
                created_by,
                None,
                min_level=min_level,
                is_event=is_event_job,
            )

            files = _logo_files()
            await msg.edit(
                embed=updated,
                view=JobWorkflowView(self.db, status="open", is_event=is_event_job),
                files=files if files else None,
            )
        except Exception:
            pass

        await ctx.respond(f"Job #{jid} reopened and set back to OPEN.", ephemeral=True)


def setup(bot: commands.Bot):
    db: Database = bot.db  # type: ignore

    bot.add_cog(JobsCog(bot, db))

    # Register persistent workflow view callbacks (Accept/Complete/Confirm).
    bot.add_view(JobWorkflowView(db, status="open"))  # type: ignore
