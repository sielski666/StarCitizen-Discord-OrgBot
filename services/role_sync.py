import discord
from services.tiers import LEVEL_ROLE_MAP


def _target_role_id_for_level(level: int) -> int | None:
    """
    Pick the highest mapped role whose required level <= user's level.
    """
    if not LEVEL_ROLE_MAP:
        return None

    level = int(level)
    target = None
    for req_level, role_id in LEVEL_ROLE_MAP.items():
        if int(req_level) <= level:
            target = int(role_id)
        else:
            break
    return target


async def sync_single_tier_role(
    guild: discord.Guild,
    member: discord.Member,
    level: int,
    reason: str = "Tier role sync",
) -> tuple[bool, str]:
    """
    Option A behavior:
      - member has ONLY ONE tier role at a time (highest they qualify for)
      - remove any other tier roles
      - add the target role if applicable
    Returns: (changed, message)
    """
    if not LEVEL_ROLE_MAP:
        return False, "LEVEL_ROLE_MAP not configured."

    tier_role_ids = {int(rid) for rid in LEVEL_ROLE_MAP.values()}
    target_role_id = _target_role_id_for_level(int(level))

    # Determine roles to remove
    to_remove: list[discord.Role] = []
    has_target = False

    for r in member.roles:
        if int(r.id) in tier_role_ids:
            if target_role_id is not None and int(r.id) == int(target_role_id):
                has_target = True
            else:
                to_remove.append(r)

    changed = False

    # Remove lower/other tier roles
    if to_remove:
        try:
            await member.remove_roles(*to_remove, reason=reason)
            changed = True
        except discord.Forbidden:
            return False, "Missing permissions to remove roles."
        except Exception as e:
            return False, f"Failed removing roles: {e}"

    # Add the target role (if any)
    if target_role_id is not None and not has_target:
        role = guild.get_role(int(target_role_id))
        if not role:
            return changed, f"Target role missing in guild: {target_role_id}"
        try:
            await member.add_roles(role, reason=reason)
            changed = True
        except discord.Forbidden:
            return False, "Missing permissions to add roles."
        except Exception as e:
            return False, f"Failed adding role: {e}"

    if target_role_id is None:
        return changed, "No tier role applies at this level."

    return changed, f"Synced tier role for level {int(level)}."
