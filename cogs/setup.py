from pathlib import Path

import discord
from discord.ext import commands

from services.permissions import is_admin_member

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class JobsBoardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Post Job", style=discord.ButtonStyle.primary, custom_id="board_jobs_post")
    async def post_job(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Use `/jobs post` (UI flow: area -> tier -> modal).", ephemeral=True)

    @discord.ui.button(label="Crew", style=discord.ButtonStyle.secondary, custom_id="board_jobs_crew")
    async def crew_help(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Crew actions: `/jobs crew_add`, `/jobs crew_remove`, `/jobs crew_list`.", ephemeral=True)


class StockBoardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Buy", style=discord.ButtonStyle.success, custom_id="board_stock_buy")
    async def buy(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Use `/stock buy`.", ephemeral=True)

    @discord.ui.button(label="Sell", style=discord.ButtonStyle.primary, custom_id="board_stock_sell")
    async def sell(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Use `/stock sell`.", ephemeral=True)

    @discord.ui.button(label="Market", style=discord.ButtonStyle.secondary, custom_id="board_stock_market")
    async def market(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Use `/stock market`.", ephemeral=True)


class FinanceBoardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cashout Stats", style=discord.ButtonStyle.secondary, custom_id="board_fin_cashout_stats")
    async def cashout_stats(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Use `/finance cashout_stats`.", ephemeral=True)

    @discord.ui.button(label="Stock Stats", style=discord.ButtonStyle.secondary, custom_id="board_fin_stock_stats")
    async def stock_stats(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Use `/finance stock_stats`.", ephemeral=True)



class SetupModal(discord.ui.Modal):
    def __init__(self, cog: "SetupCog"):
        super().__init__(title="Org Bot Setup")
        self.cog = cog

        env = cog._read_env()

        self.guild_id = discord.ui.InputText(
            label="GUILD_ID",
            value=env.get("GUILD_ID", ""),
            placeholder="Discord guild/server id",
            max_length=24,
        )
        self.finance_role_id = discord.ui.InputText(
            label="FINANCE_ROLE_ID",
            value=env.get("FINANCE_ROLE_ID", ""),
            placeholder="Role id for finance/admin confirmations",
            max_length=24,
        )
        self.jobs_admin_role_id = discord.ui.InputText(
            label="JOBS_ADMIN_ROLE_ID",
            value=env.get("JOBS_ADMIN_ROLE_ID", ""),
            placeholder="Role id for jobs admin",
            max_length=24,
        )
        self.channel_ids = discord.ui.InputText(
            label="Channel IDs (jobs, treasury, stocks)",
            value=",".join(
                [
                    env.get("JOBS_CHANNEL_ID", ""),
                    env.get("TREASURY_CHANNEL_ID", env.get("FINANCE_CHANNEL_ID", "")),
                    env.get("STOCK_SELL_CHANNEL_ID", env.get("SHARES_SELL_CHANNEL_ID", env.get("FINANCE_CHANNEL_ID", ""))),
                ]
            ).strip(","),
            placeholder="Optional: leave blank to auto-create channels",
            style=discord.InputTextStyle.long,
            required=False,
            max_length=200,
        )

        self.add_item(self.guild_id)
        self.add_item(self.finance_role_id)
        self.add_item(self.jobs_admin_role_id)
        self.add_item(self.channel_ids)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or not is_admin_member(member):
            return await interaction.response.send_message("Admin only.", ephemeral=True)

        guild_id = (self.guild_id.value or "").strip()
        finance_role_id = (self.finance_role_id.value or "").strip()
        jobs_admin_role_id = (self.jobs_admin_role_id.value or "").strip()

        numeric_fields = {
            "GUILD_ID": guild_id,
            "FINANCE_ROLE_ID": finance_role_id,
            "JOBS_ADMIN_ROLE_ID": jobs_admin_role_id,
        }
        for key, value in numeric_fields.items():
            if not value.isdigit():
                return await interaction.response.send_message(f"{key} must be numeric.", ephemeral=True)

        raw_channels = (self.channel_ids.value or "").strip()
        if raw_channels == "":
            parts = ["", "", ""]
        else:
            parts = [p.strip() for p in raw_channels.split(",")]
            if len(parts) < 3:
                parts.extend([""] * (3 - len(parts)))
            elif len(parts) > 3:
                parts = parts[:3]

        if not all((x == "" or x.isdigit()) for x in parts):
            return await interaction.response.send_message(
                "Channel IDs must be numeric when provided (jobs, treasury, stocks).",
                ephemeral=True,
            )

        jobs_channel_id, treasury_channel_id, shares_sell_channel_id = parts

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("Guild context required.", ephemeral=True)

        channels = await self.cog._ensure_channels(
            guild,
            treasury_channel_id,
            shares_sell_channel_id,
        )
        if channels is None:
            return await interaction.response.send_message(
                "Failed creating/validating channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        jobs_channel_id, treasury_channel_id, shares_sell_channel_id = channels

        updates = {
            "GUILD_ID": guild_id,
            "FINANCE_ROLE_ID": finance_role_id,
            "JOBS_ADMIN_ROLE_ID": jobs_admin_role_id,
            "JOBS_CHANNEL_ID": jobs_channel_id,
            "TREASURY_CHANNEL_ID": treasury_channel_id,
            "SHARES_SELL_CHANNEL_ID": shares_sell_channel_id,
            "STOCK_SELL_CHANNEL_ID": shares_sell_channel_id,
            # Keep compatibility with existing env usage in current code.
            "FINANCE_CHANNEL_ID": treasury_channel_id,
        }

        self.cog._write_env(updates)
        await self.cog._persist_guild_updates(guild.id if guild else None, updates)

        await interaction.response.send_message(
            "✅ Setup saved + channels ensured\n"
            f"Jobs: <#{jobs_channel_id}>\n"
            f"Treasury: <#{treasury_channel_id}>\n"
            f"Stocks Sell: <#{shares_sell_channel_id}>\n"
            "If self-hosting: restart the bot only after `.env` or deployment changes. If hosted by the bot operator, no restart action is needed in your server.",
            ephemeral=True,
        )


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = getattr(bot, "db", None)

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent board views only when an event loop is active.
        if not hasattr(self.bot, "jobs_board_view"):
            self.bot.jobs_board_view = JobsBoardView()  # type: ignore
            self.bot.add_view(self.bot.jobs_board_view)  # type: ignore
        if not hasattr(self.bot, "stock_board_view"):
            self.bot.stock_board_view = StockBoardView()  # type: ignore
            self.bot.add_view(self.bot.stock_board_view)  # type: ignore
        if not hasattr(self.bot, "finance_board_view"):
            self.bot.finance_board_view = FinanceBoardView()  # type: ignore
            self.bot.add_view(self.bot.finance_board_view)  # type: ignore

    setup_group = discord.SlashCommandGroup("setup", "Server setup and config helpers")

    async def _ensure_channels(
        self,
        guild: discord.Guild,
        treasury_channel_id: str,
        shares_sell_channel_id: str,
    ) -> tuple[str, str] | None:
        async def ensure_one(channel_id: str, default_name: str) -> str:
            by_name = discord.utils.get(guild.text_channels, name=default_name)
            if by_name is not None:
                return str(by_name.id)

            if channel_id.isdigit():
                ch = guild.get_channel(int(channel_id))
                if ch is not None:
                    return str(ch.id)

            created = await guild.create_text_channel(default_name)
            return str(created.id)

        try:
            treasury_id = await ensure_one(treasury_channel_id, "treasury")
            shares_id = await ensure_one(shares_sell_channel_id, "stock-sell-confirm")
            return treasury_id, shares_id
        except Exception:
            return None

    async def _ensure_role(self, guild: discord.Guild, role_id: str, default_name: str) -> str | None:
        try:
            by_name = discord.utils.get(guild.roles, name=default_name)
            if by_name is not None:
                return str(by_name.id)

            if role_id.isdigit():
                role = guild.get_role(int(role_id))
                if role is not None:
                    return str(role.id)

            created = await guild.create_role(name=default_name, mentionable=True, reason="Org bot setup")
            return str(created.id)
        except Exception:
            return None

    async def _ensure_job_area_channels(self, guild: discord.Guild) -> dict[str, str] | None:
        try:
            cat_name = "Jobs"
            jobs_category = discord.utils.get(guild.categories, name=cat_name)
            if jobs_category is None:
                jobs_category = await guild.create_category(cat_name)

            area_to_name = {
                "general": "jobs-general",
                "salvage": "jobs-salvage",
                "mining": "jobs-mining",
                "hauling": "jobs-hauling",
                "event": "jobs-event",
            }

            out: dict[str, str] = {}
            for area, ch_name in area_to_name.items():
                ch = discord.utils.get(guild.text_channels, name=ch_name)
                if ch is None:
                    ch = await guild.create_text_channel(ch_name, category=jobs_category)
                elif ch.category_id != jobs_category.id:
                    try:
                        await ch.edit(category=jobs_category)
                    except Exception:
                        pass
                out[area] = str(ch.id)

            return out
        except Exception:
            return None

    async def _ensure_stock_channels(self, guild: discord.Guild, stock_market_channel_id: str) -> str | None:
        try:
            by_name = discord.utils.get(guild.text_channels, name="stock-market")
            if by_name is not None:
                return str(by_name.id)

            if stock_market_channel_id.isdigit():
                ch = guild.get_channel(int(stock_market_channel_id))
                if ch is not None:
                    return str(ch.id)

            created = await guild.create_text_channel("stock-market")
            return str(created.id)
        except Exception:
            return None

    async def _ensure_board_channels(self, guild: discord.Guild, jobs_board_channel_id: str, stock_board_channel_id: str, finance_board_channel_id: str) -> dict[str, str] | None:
        async def ensure_one(channel_id: str, default_name: str) -> str:
            by_name = discord.utils.get(guild.text_channels, name=default_name)
            if by_name is not None:
                return str(by_name.id)
            if channel_id.isdigit():
                ch = guild.get_channel(int(channel_id))
                if ch is not None:
                    return str(ch.id)
            created = await guild.create_text_channel(default_name)
            return str(created.id)

        try:
            return {
                "jobs_board": await ensure_one(jobs_board_channel_id, "jobs-board"),
                "stock_board": await ensure_one(stock_board_channel_id, "stock-board"),
                "finance_board": await ensure_one(finance_board_channel_id, "finance-board"),
            }
        except Exception:
            return None

    def _board_embed(self, kind: str) -> discord.Embed:
        title_map = {
            "jobs": "🧭 Jobs Board",
            "stock": "📈 Stock Board",
            "finance": "🏦 Finance Board",
        }
        desc_map = {
            "jobs": "Use buttons to start job-related actions.",
            "stock": "Use buttons to access stock flows quickly.",
            "finance": "Finance/admin quick actions and visibility links.",
        }
        e = discord.Embed(
            title=title_map.get(kind, "Board"),
            description=desc_map.get(kind, ""),
            colour=discord.Colour.from_rgb(32, 41, 74),
        )
        return e

    async def _upsert_board_message(self, guild: discord.Guild, channel_id: str, message_id: str, kind: str) -> tuple[str | None, str | None]:
        if not channel_id.isdigit():
            return None, None
        ch = guild.get_channel(int(channel_id))
        if ch is None:
            try:
                ch = await guild.fetch_channel(int(channel_id))
            except Exception:
                return None, None

        view = getattr(self.bot, f"{kind}_board_view", None)
        embed = self._board_embed(kind)

        if message_id.isdigit():
            try:
                msg = await ch.fetch_message(int(message_id))
                await msg.edit(embed=embed, view=view)
                return str(ch.id), str(msg.id)
            except Exception:
                pass

        try:
            msg = await ch.send(embed=embed, view=view)
            return str(ch.id), str(msg.id)
        except Exception:
            return str(ch.id), None

    def _read_env(self) -> dict[str, str]:
        data: dict[str, str] = {}
        if not ENV_PATH.exists():
            return data
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
        return data

    def _write_env(self, updates: dict[str, str]) -> None:
        existing = self._read_env()
        existing.update({k: str(v).strip() for k, v in updates.items()})

        preferred_order = [
            "DISCORD_TOKEN",
            "GUILD_ID",
            "FINANCE_ROLE_ID",
            "JOBS_ADMIN_ROLE_ID",
            "EVENT_HANDLER_ROLE_ID",
            "JOB_CATEGORY_CHANNEL_MAP",
            "JOBS_CHANNEL_ID",
            "TREASURY_CHANNEL_ID",
            "SHARES_SELL_CHANNEL_ID",
            "STOCK_SELL_CHANNEL_ID",
            "STOCK_MARKET_CHANNEL_ID",
            "STOCK_ENABLED",
            "STOCK_BASE_PRICE",
            "STOCK_MIN_PRICE",
            "STOCK_MAX_PRICE",
            "STOCK_DAILY_MOVE_CAP_BPS",
            "STOCK_DEMAND_SENSITIVITY_BPS",
            "JOBS_BOARD_CHANNEL_ID",
            "STOCK_BOARD_CHANNEL_ID",
            "FINANCE_BOARD_CHANNEL_ID",
            "JOBS_BOARD_MESSAGE_ID",
            "STOCK_BOARD_MESSAGE_ID",
            "FINANCE_BOARD_MESSAGE_ID",
            "FINANCE_CHANNEL_ID",
        ]

        lines: list[str] = []
        seen = set()
        for key in preferred_order:
            if key in existing:
                lines.append(f"{key}={existing[key]}")
                seen.add(key)

        for key in sorted(existing.keys()):
            if key not in seen:
                lines.append(f"{key}={existing[key]}")

        ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    async def _get_effective_config(self, guild_id: int | None = None) -> dict[str, str]:
        env = self._read_env()
        if not guild_id or self.db is None:
            return env
        try:
            stored = await self.db.get_guild_settings(int(guild_id))
            merged = dict(env)
            merged.update(stored)
            return merged
        except Exception:
            return env

    async def _persist_guild_updates(self, guild_id: int | None, updates: dict[str, str]) -> None:
        if not guild_id or self.db is None:
            return
        try:
            await self.db.set_guild_settings(int(guild_id), {k: str(v).strip() for k, v in updates.items()})
        except Exception:
            pass

    @setup_group.command(name="start", description="Auto-setup from env + create missing channels")
    async def setup_start(self, ctx: discord.ApplicationContext):
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not member or not is_admin_member(member):
            return await ctx.respond("Admin only.", ephemeral=True)

        guild = ctx.guild
        if guild is None:
            return await ctx.respond("Guild context required.", ephemeral=True)

        await ctx.defer(ephemeral=True)

        env = await self._get_effective_config(guild.id)

        ensured = await self._ensure_channels(
            guild,
            env.get("TREASURY_CHANNEL_ID", env.get("FINANCE_CHANNEL_ID", "")),
            env.get("STOCK_SELL_CHANNEL_ID", env.get("STOCK_SELL_CHANNEL_ID", env.get("SHARES_SELL_CHANNEL_ID", ""))),
        )
        if ensured is None:
            return await ctx.followup.send(
                "Failed creating/validating channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        treasury_id, shares_id = ensured

        stock_market_id = await self._ensure_stock_channels(
            guild,
            env.get("STOCK_MARKET_CHANNEL_ID", ""),
        )
        if stock_market_id is None:
            return await ctx.followup.send(
                "Failed creating/validating stock channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        finance_role_id = await self._ensure_role(
            guild,
            env.get("FINANCE_ROLE_ID", ""),
            "Finance",
        )
        jobs_admin_role_id = await self._ensure_role(
            guild,
            env.get("JOBS_ADMIN_ROLE_ID", ""),
            "Jobs Admin",
        )
        event_handler_role_id = await self._ensure_role(
            guild,
            env.get("EVENT_HANDLER_ROLE_ID", ""),
            "Event Handler",
        )
        if finance_role_id is None or jobs_admin_role_id is None or event_handler_role_id is None:
            return await ctx.followup.send(
                "Failed creating/validating Finance/Jobs Admin/Event Handler roles. Ensure bot has Manage Roles permission.",
                ephemeral=True,
            )

        area_map = await self._ensure_job_area_channels(guild)
        if area_map is None:
            return await ctx.followup.send(
                "Failed creating/validating job area channels/category. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        area_map_value = ",".join(f"{k}:{v}" for k, v in area_map.items())

        board_map = await self._ensure_board_channels(
            guild,
            env.get("JOBS_BOARD_CHANNEL_ID", ""),
            env.get("STOCK_BOARD_CHANNEL_ID", ""),
            env.get("FINANCE_BOARD_CHANNEL_ID", ""),
        )
        if board_map is None:
            return await ctx.followup.send(
                "Failed creating/validating board channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        updates = {
            "GUILD_ID": env.get("GUILD_ID", "") or str(guild.id),
            "FINANCE_ROLE_ID": str(finance_role_id),
            "JOBS_ADMIN_ROLE_ID": str(jobs_admin_role_id),
            "EVENT_HANDLER_ROLE_ID": str(event_handler_role_id),
            "JOBS_CHANNEL_ID": str(area_map["general"]),
            "TREASURY_CHANNEL_ID": str(treasury_id),
            "SHARES_SELL_CHANNEL_ID": str(shares_id),
            "STOCK_SELL_CHANNEL_ID": str(shares_id),
            "STOCK_MARKET_CHANNEL_ID": str(stock_market_id),
            "STOCK_ENABLED": env.get("STOCK_ENABLED", "1") or "1",
            "STOCK_BASE_PRICE": env.get("STOCK_BASE_PRICE", "100000") or "100000",
            "STOCK_MIN_PRICE": env.get("STOCK_MIN_PRICE", "50000") or "50000",
            "STOCK_MAX_PRICE": env.get("STOCK_MAX_PRICE", "250000") or "250000",
            "STOCK_DAILY_MOVE_CAP_BPS": env.get("STOCK_DAILY_MOVE_CAP_BPS", "500") or "500",
            "STOCK_DEMAND_SENSITIVITY_BPS": env.get("STOCK_DEMAND_SENSITIVITY_BPS", "50") or "50",
            "JOBS_BOARD_CHANNEL_ID": str(board_map["jobs_board"]),
            "STOCK_BOARD_CHANNEL_ID": str(board_map["stock_board"]),
            "FINANCE_BOARD_CHANNEL_ID": str(board_map["finance_board"]),
            "JOBS_BOARD_MESSAGE_ID": env.get("JOBS_BOARD_MESSAGE_ID", "") or "",
            "STOCK_BOARD_MESSAGE_ID": env.get("STOCK_BOARD_MESSAGE_ID", "") or "",
            "FINANCE_BOARD_MESSAGE_ID": env.get("FINANCE_BOARD_MESSAGE_ID", "") or "",
            "FINANCE_CHANNEL_ID": str(treasury_id),
            "JOB_CATEGORY_CHANNEL_MAP": area_map_value,
        }
        self._write_env(updates)
        await self._persist_guild_updates(guild.id, updates)

        msg = (
            "✅ Setup synced from .env and guild context\n"
            f"Guild: `{updates['GUILD_ID']}`\n"
            f"Treasury: <#{treasury_id}>\n"
            f"Stocks Sell: <#{shares_id}>\n"
            f"Stock Market: <#{stock_market_id}>\n"
            f"Event Handler Role: <@&{event_handler_role_id}>\n"
            f"Area Channels: general <#{area_map['general']}>, salvage <#{area_map['salvage']}>, mining <#{area_map['mining']}>, hauling <#{area_map['hauling']}>, event <#{area_map['event']}>\n"
            "(Token remains managed in `.env` as DISCORD_TOKEN.)"
        )
        msg += "\n\nIf self-hosting: restart only after `.env`/deployment changes. If hosted for you by the bot operator, no restart action is required in your server."
        await ctx.followup.send(msg, ephemeral=True)

    @setup_group.command(name="status", description="Show current setup values")
    async def setup_status(self, ctx: discord.ApplicationContext):
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not member or not is_admin_member(member):
            return await ctx.respond("Admin only.", ephemeral=True)

        guild = ctx.guild
        env = await self._get_effective_config(guild.id if guild else None)
        guild_id_live = str(guild.id) if guild else "unknown"
        required = [
            "DISCORD_TOKEN",
            "GUILD_ID",
            "FINANCE_ROLE_ID",
            "JOBS_ADMIN_ROLE_ID",
            "EVENT_HANDLER_ROLE_ID",
            "JOB_CATEGORY_CHANNEL_MAP",
            "JOBS_CHANNEL_ID",
            "TREASURY_CHANNEL_ID",
            "SHARES_SELL_CHANNEL_ID",
            "STOCK_SELL_CHANNEL_ID",
            "STOCK_MARKET_CHANNEL_ID",
            "STOCK_ENABLED",
            "STOCK_BASE_PRICE",
            "STOCK_MIN_PRICE",
            "STOCK_MAX_PRICE",
            "STOCK_DAILY_MOVE_CAP_BPS",
            "STOCK_DEMAND_SENSITIVITY_BPS",
            "JOBS_BOARD_CHANNEL_ID",
            "STOCK_BOARD_CHANNEL_ID",
            "FINANCE_BOARD_CHANNEL_ID",
        ]
        missing = [k for k in required if not env.get(k)]

        token_set = "set" if env.get("DISCORD_TOKEN") else "missing"
        text = (
            f"Token: **{token_set}**\n"
            f"Guild (live): `{guild_id_live}`\n"
            f"Guild (config): `{env.get('GUILD_ID', 'missing')}`\n"
            f"Finance Role: `{env.get('FINANCE_ROLE_ID', 'missing')}`\n"
            f"Jobs Admin Role: `{env.get('JOBS_ADMIN_ROLE_ID', 'missing')}`\n"
            f"Event Handler Role: `{env.get('EVENT_HANDLER_ROLE_ID', 'missing')}`\n"
            f"Job Category Map: `{env.get('JOB_CATEGORY_CHANNEL_MAP', 'missing')}`\n"
            f"Jobs Channel: `{env.get('JOBS_CHANNEL_ID', 'missing')}`\n"
            f"Treasury Channel: `{env.get('TREASURY_CHANNEL_ID', env.get('FINANCE_CHANNEL_ID', 'missing'))}`\n"
            f"Stocks Sell Channel: `{env.get('STOCK_SELL_CHANNEL_ID', env.get('SHARES_SELL_CHANNEL_ID', 'missing'))}`\n"
        )
        if missing:
            text += "\n⚠️ Missing: " + ", ".join(missing)
        else:
            text += "\n✅ Core setup fields present"

        configured_gid = env.get("GUILD_ID", "")
        if guild and configured_gid.isdigit() and int(configured_gid) != int(guild.id):
            text += "\n⚠️ Config guild differs from current guild. Run `/setup start` in this server to sync guild-scoped settings."

        await ctx.respond(text, ephemeral=True)

    @setup_group.command(name="doctor", description="Diagnose setup/permission issues in this server")
    async def setup_doctor(self, ctx: discord.ApplicationContext):
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not member or not is_admin_member(member):
            return await ctx.respond("Admin only.", ephemeral=True)

        guild = ctx.guild
        if guild is None:
            return await ctx.respond("Guild context required.", ephemeral=True)

        env = await self._get_effective_config(guild.id)
        me = guild.me

        checks_ok: list[str] = []
        checks_warn: list[str] = []

        if me is None:
            checks_warn.append("Bot member not found in guild cache. Re-invite bot and retry.")
        else:
            gp = me.guild_permissions
            must_have = {
                "manage_channels": "Manage Channels",
                "manage_roles": "Manage Roles",
                "send_messages": "Send Messages",
                "embed_links": "Embed Links",
                "use_application_commands": "Use Application Commands",
            }
            missing = [label for key, label in must_have.items() if not getattr(gp, key, False)]
            if missing:
                checks_warn.append("Bot missing guild permissions: " + ", ".join(missing))
            else:
                checks_ok.append("Core bot guild permissions look good")

        for role_key in ("FINANCE_ROLE_ID", "JOBS_ADMIN_ROLE_ID", "EVENT_HANDLER_ROLE_ID"):
            rv = env.get(role_key, "")
            if not rv or not rv.isdigit() or guild.get_role(int(rv)) is None:
                checks_warn.append(f"{role_key} missing/invalid in this guild")
            else:
                checks_ok.append(f"{role_key} valid")

        channel_keys = ["JOBS_CHANNEL_ID", "TREASURY_CHANNEL_ID", "SHARES_SELL_CHANNEL_ID", "STOCK_SELL_CHANNEL_ID", "STOCK_MARKET_CHANNEL_ID", "JOBS_BOARD_CHANNEL_ID", "STOCK_BOARD_CHANNEL_ID", "FINANCE_BOARD_CHANNEL_ID"]
        for ck in channel_keys:
            cv = env.get(ck, "")
            if not cv or not cv.isdigit():
                checks_warn.append(f"{ck} missing/invalid")
                continue
            ch = guild.get_channel(int(cv))
            if ch is None:
                checks_warn.append(f"{ck} points to missing channel id {cv}")
                continue
            if me is not None and isinstance(ch, discord.abc.GuildChannel):
                perms = ch.permissions_for(me)
                needed = []
                if not perms.view_channel:
                    needed.append("View Channel")
                if not perms.send_messages:
                    needed.append("Send Messages")
                if not perms.embed_links:
                    needed.append("Embed Links")
                if needed:
                    checks_warn.append(f"{ck} <#{ch.id}> missing bot perms: " + ", ".join(needed))
                else:
                    checks_ok.append(f"{ck} <#{ch.id}> permission check passed")

        map_raw = env.get("JOB_CATEGORY_CHANNEL_MAP", "")
        area_map = {}
        if map_raw:
            for part in map_raw.split(","):
                part = part.strip()
                if not part or ":" not in part:
                    continue
                k, v = part.split(":", 1)
                if v.strip().isdigit():
                    area_map[k.strip().lower()] = int(v.strip())

        expected_areas = ["general", "salvage", "mining", "hauling", "event"]
        for area in expected_areas:
            cid = area_map.get(area)
            if not cid or guild.get_channel(int(cid)) is None:
                checks_warn.append(f"JOB_CATEGORY_CHANNEL_MAP missing/invalid entry for `{area}`")

        text = "🩺 Setup Doctor\n"
        if checks_ok:
            text += "\n✅ OK:\n- " + "\n- ".join(checks_ok[:12])
        if checks_warn:
            text += "\n\n⚠️ Issues:\n- " + "\n- ".join(checks_warn[:12])
            if len(checks_warn) > 12:
                text += f"\n- … +{len(checks_warn) - 12} more"
            text += "\n\nRecommended fix: run `/setup start` in this server, then `/setup status`."
        else:
            text += "\n\n🎉 No issues found. Setup looks healthy."

        await ctx.respond(text, ephemeral=True)

    @setup_group.command(name="deployboards", description="Create or refresh board messages in board channels")
    async def setup_deploy_boards(self, ctx: discord.ApplicationContext):
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not member or not is_admin_member(member):
            return await ctx.respond("Admin only.", ephemeral=True)

        guild = ctx.guild
        if guild is None:
            return await ctx.respond("Guild context required.", ephemeral=True)

        await ctx.defer(ephemeral=True)
        env = await self._get_effective_config(guild.id)

        jobs_ch, jobs_msg = await self._upsert_board_message(
            guild,
            env.get("JOBS_BOARD_CHANNEL_ID", ""),
            env.get("JOBS_BOARD_MESSAGE_ID", ""),
            "jobs",
        )
        stock_ch, stock_msg = await self._upsert_board_message(
            guild,
            env.get("STOCK_BOARD_CHANNEL_ID", ""),
            env.get("STOCK_BOARD_MESSAGE_ID", ""),
            "stock",
        )
        fin_ch, fin_msg = await self._upsert_board_message(
            guild,
            env.get("FINANCE_BOARD_CHANNEL_ID", ""),
            env.get("FINANCE_BOARD_MESSAGE_ID", ""),
            "finance",
        )

        updates = {
            "JOBS_BOARD_CHANNEL_ID": jobs_ch or env.get("JOBS_BOARD_CHANNEL_ID", ""),
            "STOCK_BOARD_CHANNEL_ID": stock_ch or env.get("STOCK_BOARD_CHANNEL_ID", ""),
            "FINANCE_BOARD_CHANNEL_ID": fin_ch or env.get("FINANCE_BOARD_CHANNEL_ID", ""),
            "JOBS_BOARD_MESSAGE_ID": jobs_msg or env.get("JOBS_BOARD_MESSAGE_ID", ""),
            "STOCK_BOARD_MESSAGE_ID": stock_msg or env.get("STOCK_BOARD_MESSAGE_ID", ""),
            "FINANCE_BOARD_MESSAGE_ID": fin_msg or env.get("FINANCE_BOARD_MESSAGE_ID", ""),
        }
        self._write_env(updates)
        await self._persist_guild_updates(guild.id, updates)

        await ctx.followup.send(
            "✅ Board messages deployed/refreshed\n"
            f"Jobs Board: <#{updates['JOBS_BOARD_CHANNEL_ID']}> (msg `{updates['JOBS_BOARD_MESSAGE_ID'] or 'missing'}`)\n"
            f"Stock Board: <#{updates['STOCK_BOARD_CHANNEL_ID']}> (msg `{updates['STOCK_BOARD_MESSAGE_ID'] or 'missing'}`)\n"
            f"Finance Board: <#{updates['FINANCE_BOARD_CHANNEL_ID']}> (msg `{updates['FINANCE_BOARD_MESSAGE_ID'] or 'missing'}`)",
            ephemeral=True,
        )

    @setup_group.command(name="createchannels", description="Create missing treasury/stocks + job-area channels")
    async def setup_create_channels(self, ctx: discord.ApplicationContext):
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not member or not is_admin_member(member):
            return await ctx.respond("Admin only.", ephemeral=True)

        guild = ctx.guild
        if guild is None:
            return await ctx.respond("Guild context required.", ephemeral=True)

        env = await self._get_effective_config(guild.id)

        ensured = await self._ensure_channels(
            guild,
            env.get("TREASURY_CHANNEL_ID", env.get("FINANCE_CHANNEL_ID", "")),
            env.get("STOCK_SELL_CHANNEL_ID", env.get("STOCK_SELL_CHANNEL_ID", env.get("SHARES_SELL_CHANNEL_ID", ""))),
        )
        if ensured is None:
            return await ctx.respond(
                "Failed creating channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        treasury_id, shares_id = ensured

        stock_market_id = await self._ensure_stock_channels(
            guild,
            env.get("STOCK_MARKET_CHANNEL_ID", ""),
        )
        if stock_market_id is None:
            return await ctx.respond(
                "Failed creating stock channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        area_map = await self._ensure_job_area_channels(guild)
        if area_map is None:
            return await ctx.respond(
                "Failed creating area channels/category. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        board_map = await self._ensure_board_channels(
            guild,
            env.get("JOBS_BOARD_CHANNEL_ID", ""),
            env.get("STOCK_BOARD_CHANNEL_ID", ""),
            env.get("FINANCE_BOARD_CHANNEL_ID", ""),
        )
        if board_map is None:
            return await ctx.respond(
                "Failed creating board channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        updates = {
            "JOBS_CHANNEL_ID": str(area_map["general"]),
            "TREASURY_CHANNEL_ID": str(treasury_id),
            "SHARES_SELL_CHANNEL_ID": str(shares_id),
            "STOCK_SELL_CHANNEL_ID": str(shares_id),
            "STOCK_MARKET_CHANNEL_ID": str(stock_market_id),
            "JOBS_BOARD_CHANNEL_ID": str(board_map["jobs_board"]),
            "STOCK_BOARD_CHANNEL_ID": str(board_map["stock_board"]),
            "FINANCE_BOARD_CHANNEL_ID": str(board_map["finance_board"]),
            "JOBS_BOARD_MESSAGE_ID": env.get("JOBS_BOARD_MESSAGE_ID", "") or "",
            "STOCK_BOARD_MESSAGE_ID": env.get("STOCK_BOARD_MESSAGE_ID", "") or "",
            "FINANCE_BOARD_MESSAGE_ID": env.get("FINANCE_BOARD_MESSAGE_ID", "") or "",
            "FINANCE_CHANNEL_ID": str(treasury_id),
            "JOB_CATEGORY_CHANNEL_MAP": ",".join(f"{k}:{v}" for k, v in area_map.items()),
        }
        self._write_env(updates)
        await self._persist_guild_updates(guild.id, updates)

        await ctx.respond(
            "✅ Channels ready\n"
            f"Treasury: <#{treasury_id}>\n"
            f"Stocks Sell: <#{shares_id}>\n"
            f"Stock Market: <#{stock_market_id}>\n"
            f"Area Channels: general <#{area_map['general']}>, salvage <#{area_map['salvage']}>, mining <#{area_map['mining']}>, hauling <#{area_map['hauling']}>, event <#{area_map['event']}>\n"
            "Self-host only: restart after `.env` or deployment changes. Hosted users do not need to restart anything.",
            ephemeral=True,
        )


def setup(bot: commands.Bot):
    bot.add_cog(SetupCog(bot))
