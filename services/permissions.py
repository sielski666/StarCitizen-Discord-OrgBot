import os
import discord


def _get_role_id(env_name: str) -> int:
    """
    Reads role ID from environment each time (lazy),
    so load_dotenv order won't break imports.
    """
    raw = (os.getenv(env_name) or "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def is_admin_member(member: discord.Member) -> bool:
    try:
        return bool(member.guild_permissions.administrator)
    except Exception:
        return False


def has_role_id(member: discord.Member, role_id: int) -> bool:
    if not role_id:
        return False
    try:
        return any(getattr(r, "id", 0) == role_id for r in member.roles)
    except Exception:
        return False


def is_finance(member: discord.Member) -> bool:
    finance_role_id = _get_role_id("FINANCE_ROLE_ID")
    return has_role_id(member, finance_role_id)


def is_jobs_admin(member: discord.Member) -> bool:
    jobs_admin_role_id = _get_role_id("JOBS_ADMIN_ROLE_ID")
    return has_role_id(member, jobs_admin_role_id)


# ==========================
# NEW HELPERS (V2.3)
# ==========================
def is_finance_or_admin(member: discord.Member) -> bool:
    """
    Used for cash-out approvals / marking paid.
    """
    return is_admin_member(member) or is_finance(member)


def is_jobs_admin_or_admin(member: discord.Member) -> bool:
    """
    Used for job admin actions if you want jobs-admin role to have powers
    without being a full Discord admin.
    """
    return is_admin_member(member) or is_jobs_admin(member)
