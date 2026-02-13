import os

# Format: "0:🟩:Open,5:🟦:Contractor,10:🟪:Specialist,20:🟥:Elite"
JOB_TIERS_RAW = os.getenv("JOB_TIERS", "0:🟩:Open,5:🟦:Contractor,10:🟪:Specialist,20:🟥:Elite") or ""

# Format: "5:ROLEID,10:ROLEID,20:ROLEID"
LEVEL_ROLE_MAP_RAW = os.getenv("LEVEL_ROLE_MAP", "") or ""


def parse_job_tiers(raw: str) -> list[dict]:
    tiers: list[dict] = []
    raw = (raw or "").strip()
    if not raw:
        return [{"level": 0, "emoji": "🟩", "name": "Open"}]

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for p in parts:
        bits = p.split(":", 2)
        if len(bits) != 3:
            continue
        level_s, emoji_s, name_s = bits
        level_s = level_s.strip()
        emoji_s = (emoji_s or "").strip()
        name_s = (name_s or "").strip()
        if not level_s.isdigit():
            continue

        tiers.append(
            {
                "level": int(level_s),
                "emoji": emoji_s if emoji_s else "🟦",
                "name": name_s if name_s else f"Level {level_s}+",
            }
        )

    if not any(int(t["level"]) == 0 for t in tiers):
        tiers.insert(0, {"level": 0, "emoji": "🟩", "name": "Open"})

    tiers.sort(key=lambda t: int(t["level"]))
    return tiers


def parse_level_role_map(raw: str) -> dict[int, int]:
    """
    LEVEL_ROLE_MAP=5:ROLEID,10:ROLEID,20:ROLEID
    -> {5: 123..., 10: 456..., 20: 789...}
    """
    out: dict[int, int] = {}
    raw = (raw or "").strip()
    if not raw:
        return out

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for p in parts:
        if ":" not in p:
            continue
        a, b = p.split(":", 1)
        a = a.strip()
        b = b.strip()
        if not a.isdigit():
            continue
        try:
            rid = int(b)
        except Exception:
            continue
        out[int(a)] = rid

    return dict(sorted(out.items(), key=lambda kv: kv[0]))


JOB_TIERS = parse_job_tiers(JOB_TIERS_RAW)
LEVEL_ROLE_MAP = parse_level_role_map(LEVEL_ROLE_MAP_RAW)


def tier_display_for_level(level: int) -> str:
    """
    Returns best matching tier text for a level (highest tier <= level).
    """
    level = int(level)
    chosen = None
    for t in JOB_TIERS:
        if int(t["level"]) <= level:
            chosen = t
        else:
            break

    if not chosen:
        return "🟩 Open (No requirement)"

    req = int(chosen["level"])
    if req <= 0:
        return f"{chosen['emoji']} {chosen['name']} (No requirement)"
    return f"{chosen['emoji']} {chosen['name']} (Level {req}+)"


def required_min_level_for_tier(min_level: int) -> str:
    """
    For job embeds: show tier label that corresponds exactly to min_level.
    """
    min_level = int(min_level)
    match = None
    for t in JOB_TIERS:
        if int(t["level"]) == min_level:
            match = t
            break

    if not match:
        if min_level <= 0:
            return "🟩 Open (No requirement)"
        return f"⭐ Level {min_level}+"

    if int(match["level"]) <= 0:
        return f"{match['emoji']} {match['name']} (No requirement)"
    return f"{match['emoji']} {match['name']} (Level {int(match['level'])}+)"
