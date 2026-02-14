from pathlib import Path

import discord
from discord.ext import commands

from services.permissions import is_admin_member

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


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
            label="Channel IDs (jobs, treasury, shares)",
            value=",".join(
                [
                    env.get("JOBS_CHANNEL_ID", ""),
                    env.get("TREASURY_CHANNEL_ID", env.get("FINANCE_CHANNEL_ID", "")),
                    env.get("SHARES_SELL_CHANNEL_ID", env.get("FINANCE_CHANNEL_ID", "")),
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
                "Channel IDs must be numeric when provided (jobs, treasury, shares).",
                ephemeral=True,
            )

        jobs_channel_id, treasury_channel_id, shares_sell_channel_id = parts

        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("Guild context required.", ephemeral=True)

        channels = await self.cog._ensure_channels(
            guild,
            jobs_channel_id,
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
            # Keep compatibility with existing env usage in current code.
            "FINANCE_CHANNEL_ID": treasury_channel_id,
        }

        self.cog._write_env(updates)

        await interaction.response.send_message(
            "✅ Setup saved + channels ensured\n"
            f"Jobs: <#{jobs_channel_id}>\n"
            f"Treasury: <#{treasury_channel_id}>\n"
            f"Shares Sell: <#{shares_sell_channel_id}>\n"
            "Run: `sudo systemctl restart starcitizen-orgbot` to apply config updates.",
            ephemeral=True,
        )


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    setup_group = discord.SlashCommandGroup("setup", "Server setup and config helpers")

    async def _ensure_channels(
        self,
        guild: discord.Guild,
        jobs_channel_id: str,
        treasury_channel_id: str,
        shares_sell_channel_id: str,
    ) -> tuple[str, str, str] | None:
        async def ensure_one(channel_id: str, default_name: str) -> str:
            # Name-first policy: if a channel with the expected name exists,
            # prefer it and overwrite env with that ID.
            by_name = discord.utils.get(guild.text_channels, name=default_name)
            if by_name is not None:
                return str(by_name.id)

            # Fallback to env-provided channel ID if valid.
            if channel_id.isdigit():
                ch = guild.get_channel(int(channel_id))
                if ch is not None:
                    return str(ch.id)

            # Otherwise create it.
            created = await guild.create_text_channel(default_name)
            return str(created.id)

        try:
            jobs_id = await ensure_one(jobs_channel_id, "jobs")
            treasury_id = await ensure_one(treasury_channel_id, "treasury")
            shares_id = await ensure_one(shares_sell_channel_id, "share-sell-confirm")
            return jobs_id, treasury_id, shares_id
        except Exception:
            return None

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
            "JOBS_CHANNEL_ID",
            "TREASURY_CHANNEL_ID",
            "SHARES_SELL_CHANNEL_ID",
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

    @setup_group.command(name="start", description="Auto-setup from env + create missing channels")
    async def setup_start(self, ctx: discord.ApplicationContext):
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not member or not is_admin_member(member):
            return await ctx.respond("Admin only.", ephemeral=True)

        guild = ctx.guild
        if guild is None:
            return await ctx.respond("Guild context required.", ephemeral=True)

        env = self._read_env()

        ensured = await self._ensure_channels(
            guild,
            env.get("JOBS_CHANNEL_ID", ""),
            env.get("TREASURY_CHANNEL_ID", env.get("FINANCE_CHANNEL_ID", "")),
            env.get("SHARES_SELL_CHANNEL_ID", ""),
        )
        if ensured is None:
            return await ctx.respond(
                "Failed creating/validating channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        jobs_id, treasury_id, shares_id = ensured

        updates = {
            "GUILD_ID": env.get("GUILD_ID", "") or str(guild.id),
            "JOBS_CHANNEL_ID": str(jobs_id),
            "TREASURY_CHANNEL_ID": str(treasury_id),
            "SHARES_SELL_CHANNEL_ID": str(shares_id),
            "FINANCE_CHANNEL_ID": str(treasury_id),
        }
        self._write_env(updates)

        missing_roles = [
            k for k in ("FINANCE_ROLE_ID", "JOBS_ADMIN_ROLE_ID") if not env.get(k)
        ]

        msg = (
            "✅ Setup synced from .env and guild context\n"
            f"Guild: `{updates['GUILD_ID']}`\n"
            f"Jobs: <#{jobs_id}>\n"
            f"Treasury: <#{treasury_id}>\n"
            f"Shares Sell: <#{shares_id}>\n"
            "(Token remains managed in `.env` as DISCORD_TOKEN.)"
        )
        if missing_roles:
            msg += "\n\n⚠️ Missing role IDs in .env: " + ", ".join(missing_roles)

        msg += "\n\nRun: `sudo systemctl restart starcitizen-orgbot` to apply config changes."
        await ctx.respond(msg, ephemeral=True)

    @setup_group.command(name="status", description="Show current setup values")
    async def setup_status(self, ctx: discord.ApplicationContext):
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not member or not is_admin_member(member):
            return await ctx.respond("Admin only.", ephemeral=True)

        env = self._read_env()
        required = [
            "DISCORD_TOKEN",
            "GUILD_ID",
            "FINANCE_ROLE_ID",
            "JOBS_ADMIN_ROLE_ID",
            "JOBS_CHANNEL_ID",
            "TREASURY_CHANNEL_ID",
            "SHARES_SELL_CHANNEL_ID",
        ]
        missing = [k for k in required if not env.get(k)]

        token_set = "set" if env.get("DISCORD_TOKEN") else "missing"
        text = (
            f"Token: **{token_set}**\n"
            f"Guild: `{env.get('GUILD_ID', 'missing')}`\n"
            f"Finance Role: `{env.get('FINANCE_ROLE_ID', 'missing')}`\n"
            f"Jobs Admin Role: `{env.get('JOBS_ADMIN_ROLE_ID', 'missing')}`\n"
            f"Jobs Channel: `{env.get('JOBS_CHANNEL_ID', 'missing')}`\n"
            f"Treasury Channel: `{env.get('TREASURY_CHANNEL_ID', env.get('FINANCE_CHANNEL_ID', 'missing'))}`\n"
            f"Shares Sell Channel: `{env.get('SHARES_SELL_CHANNEL_ID', 'missing')}`\n"
        )
        if missing:
            text += "\n⚠️ Missing: " + ", ".join(missing)
        else:
            text += "\n✅ Core setup fields present"

        await ctx.respond(text, ephemeral=True)

    @setup_group.command(name="createchannels", description="Create missing jobs/treasury/shares channels")
    async def setup_create_channels(self, ctx: discord.ApplicationContext):
        member = ctx.author if isinstance(ctx.author, discord.Member) else None
        if not member or not is_admin_member(member):
            return await ctx.respond("Admin only.", ephemeral=True)

        guild = ctx.guild
        if guild is None:
            return await ctx.respond("Guild context required.", ephemeral=True)

        env = self._read_env()

        ensured = await self._ensure_channels(
            guild,
            env.get("JOBS_CHANNEL_ID", ""),
            env.get("TREASURY_CHANNEL_ID", env.get("FINANCE_CHANNEL_ID", "")),
            env.get("SHARES_SELL_CHANNEL_ID", ""),
        )
        if ensured is None:
            return await ctx.respond(
                "Failed creating channels. Ensure bot has Manage Channels permission.",
                ephemeral=True,
            )

        jobs_id, treasury_id, shares_id = ensured

        updates = {
            "JOBS_CHANNEL_ID": str(jobs_id),
            "TREASURY_CHANNEL_ID": str(treasury_id),
            "SHARES_SELL_CHANNEL_ID": str(shares_id),
            "FINANCE_CHANNEL_ID": str(treasury_id),
        }
        self._write_env(updates)

        await ctx.respond(
            "✅ Channels ready\n"
            f"Jobs: <#{jobs_id}>\n"
            f"Treasury: <#{treasury_id}>\n"
            f"Shares Sell: <#{shares_id}>\n"
            "Run: `sudo systemctl restart starcitizen-orgbot` to apply.",
            ephemeral=True,
        )


def setup(bot: commands.Bot):
    bot.add_cog(SetupCog(bot))
