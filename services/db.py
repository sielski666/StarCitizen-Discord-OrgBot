import os
import aiosqlite

DB_PATH = "bot.db"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0") or ("1" if default else "0")).strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off", ""):
        return False
    # Unknown values are treated as default (safer for old/non-boolean config values).
    return bool(default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(int(default)))
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


TREASURY_AUTODEDUCT = _env_flag("TREASURY_AUTODEDUCT", default=True)
STRICT_TREASURY = _env_flag("STRICT_TREASURY", default=False)
SHARE_CASHOUT_AUEC_PER_SHARE = _env_int("SHARE_CASHOUT_AUEC_PER_SHARE", 100000)

# Bond config scaffolding (future use)
BOND_AUTO_REDEEM = _env_flag("BOND_AUTO_REDEEM", default=False)
MIN_IMMEDIATE_PAYOUT_PERCENT = max(0, min(100, _env_int("MIN_IMMEDIATE_PAYOUT_PERCENT", 0)))

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS wallets (
  discord_id INTEGER PRIMARY KEY,
  balance INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS wallets_by_guild (
  guild_id INTEGER NOT NULL,
  discord_id INTEGER NOT NULL,
  balance INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, discord_id)
);

CREATE TABLE IF NOT EXISTS shareholdings (
  discord_id INTEGER PRIMARY KEY,
  shares INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shareholdings_by_guild (
  guild_id INTEGER NOT NULL,
  discord_id INTEGER NOT NULL,
  shares INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, discord_id)
);

CREATE TABLE IF NOT EXISTS reputation (
  discord_id INTEGER PRIMARY KEY,
  rep INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reputation_by_guild (
  guild_id INTEGER NOT NULL,
  discord_id INTEGER NOT NULL,
  rep INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, discord_id)
);

CREATE TABLE IF NOT EXISTS shares_escrow (
  discord_id INTEGER PRIMARY KEY,
  locked_shares INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shares_escrow_by_guild (
  guild_id INTEGER NOT NULL,
  discord_id INTEGER NOT NULL,
  locked_shares INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (guild_id, discord_id)
);

-- Treasury is a single-row table (id=1)
CREATE TABLE IF NOT EXISTS treasury (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  amount INTEGER NOT NULL DEFAULT 0,
  updated_by INTEGER,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS treasury_by_guild (
  guild_id INTEGER PRIMARY KEY,
  amount INTEGER NOT NULL DEFAULT 0,
  updated_by INTEGER,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
  job_id INTEGER PRIMARY KEY AUTOINCREMENT,
  channel_id INTEGER NOT NULL,
  message_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  reward INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'open', -- open, claimed, completed, paid, cancelled
  created_by INTEGER NOT NULL,
  claimed_by INTEGER,
  thread_id INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Cash-out requests (sell shares)
CREATE TABLE IF NOT EXISTS cashout_requests (
  request_id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id INTEGER NOT NULL,
  channel_id INTEGER NOT NULL,
  message_id INTEGER NOT NULL,
  requester_id INTEGER NOT NULL,
  shares INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected, paid
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  thread_id INTEGER,
  handled_by INTEGER,
  handled_note TEXT
);

-- Outstanding payout bonds created when treasury cannot fully pay rewards.
CREATE TABLE IF NOT EXISTS payout_bonds (
  bond_id INTEGER PRIMARY KEY AUTOINCREMENT,
  guild_id INTEGER NOT NULL DEFAULT 0,
  org_id TEXT,
  user_id INTEGER NOT NULL,
  amount_owed INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', -- pending, redeemed
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  redeemed_at TEXT,
  job_reference TEXT
);
CREATE INDEX IF NOT EXISTS idx_payout_bonds_guild_status_created ON payout_bonds(guild_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_payout_bonds_user_status_created ON payout_bonds(user_id, status, created_at);

-- Simple transaction log (for balance + shares + rep deltas)
CREATE TABLE IF NOT EXISTS transactions (
  tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
  discord_id INTEGER NOT NULL,
  type TEXT NOT NULL,
  amount INTEGER NOT NULL DEFAULT 0,
  shares_delta INTEGER NOT NULL DEFAULT 0,
  rep_delta INTEGER NOT NULL DEFAULT 0,
  reference TEXT,
  guild_id INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ledger_entries (
  entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL DEFAULT (datetime('now')),
  entry_type TEXT NOT NULL,
  amount INTEGER NOT NULL DEFAULT 0,
  from_account TEXT,
  to_account TEXT,
  reference_type TEXT,
  reference_id TEXT,
  notes TEXT,
  guild_id INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS job_templates (
  template_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  default_title TEXT NOT NULL,
  default_description TEXT NOT NULL,
  default_reward_min INTEGER NOT NULL DEFAULT 0,
  default_reward_max INTEGER NOT NULL DEFAULT 0,
  default_tier_required INTEGER NOT NULL DEFAULT 0,
  category TEXT,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS job_event_attendance (
  job_id INTEGER NOT NULL,
  discord_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'joined',
  joined_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (job_id, discord_id)
);

CREATE TABLE IF NOT EXISTS job_event_links (
  event_id INTEGER PRIMARY KEY,
  job_id INTEGER NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (guild_id, key)
);
"""


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.executescript(SCHEMA)
        await self.conn.execute("INSERT OR IGNORE INTO treasury(id, amount) VALUES(1, 0)")
        await self._ensure_jobs_columns()
        await self._ensure_ledger_columns()
        await self._ensure_transactions_columns()
        await self._backfill_legacy_account_data()
        await self.conn.commit()

    async def _ensure_jobs_columns(self):
        cur = await self.conn.execute("PRAGMA table_info(jobs)")
        rows = await cur.fetchall()
        existing = {str(r[1]) for r in rows}

        if "escrow_amount" not in existing:
            await self.conn.execute("ALTER TABLE jobs ADD COLUMN escrow_amount INTEGER NOT NULL DEFAULT 0")
        if "escrow_status" not in existing:
            await self.conn.execute("ALTER TABLE jobs ADD COLUMN escrow_status TEXT NOT NULL DEFAULT 'none'")
        if "funded" not in existing:
            await self.conn.execute("ALTER TABLE jobs ADD COLUMN funded INTEGER NOT NULL DEFAULT 0")
        if "category" not in existing:
            await self.conn.execute("ALTER TABLE jobs ADD COLUMN category TEXT")
        if "template_id" not in existing:
            await self.conn.execute("ALTER TABLE jobs ADD COLUMN template_id INTEGER")
        if "attendance_locked" not in existing:
            await self.conn.execute("ALTER TABLE jobs ADD COLUMN attendance_locked INTEGER NOT NULL DEFAULT 0")
        if "attendance_snapshot" not in existing:
            await self.conn.execute("ALTER TABLE jobs ADD COLUMN attendance_snapshot TEXT")
        if "guild_id" not in existing:
            await self.conn.execute("ALTER TABLE jobs ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")
            try:
                legacy_gid = int(os.getenv("GUILD_ID", "0") or "0")
            except Exception:
                legacy_gid = 0
            if legacy_gid > 0:
                await self.conn.execute("UPDATE jobs SET guild_id=? WHERE guild_id=0", (int(legacy_gid),))

    async def _ensure_ledger_columns(self):
        cur = await self.conn.execute("PRAGMA table_info(ledger_entries)")
        rows = await cur.fetchall()
        existing = {str(r[1]) for r in rows}
        if "guild_id" not in existing:
            await self.conn.execute("ALTER TABLE ledger_entries ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")

    async def _ensure_transactions_columns(self):
        cur = await self.conn.execute("PRAGMA table_info(transactions)")
        rows = await cur.fetchall()
        existing = {str(r[1]) for r in rows}
        if "guild_id" not in existing:
            await self.conn.execute("ALTER TABLE transactions ADD COLUMN guild_id INTEGER NOT NULL DEFAULT 0")

    async def _backfill_legacy_account_data(self):
        try:
            legacy_gid = int(os.getenv("GUILD_ID", "0") or "0")
        except Exception:
            legacy_gid = 0
        if legacy_gid <= 0:
            return

        # One-time migration for single-guild deployments upgrading to guild-scoped tables.
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO wallets_by_guild(guild_id, discord_id, balance)
            SELECT ?, discord_id, balance FROM wallets
            """,
            (int(legacy_gid),),
        )
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO shareholdings_by_guild(guild_id, discord_id, shares)
            SELECT ?, discord_id, shares FROM shareholdings
            """,
            (int(legacy_gid),),
        )
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO shares_escrow_by_guild(guild_id, discord_id, locked_shares)
            SELECT ?, discord_id, locked_shares FROM shares_escrow
            """,
            (int(legacy_gid),),
        )
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO reputation_by_guild(guild_id, discord_id, rep)
            SELECT ?, discord_id, rep FROM reputation
            """,
            (int(legacy_gid),),
        )

        # Preserve historical audit scoping for upgraded single-guild installs.
        await self.conn.execute(
            "UPDATE transactions SET guild_id=? WHERE guild_id=0",
            (int(legacy_gid),),
        )
        await self.conn.execute(
            "UPDATE ledger_entries SET guild_id=? WHERE guild_id=0",
            (int(legacy_gid),),
        )

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def set_guild_setting(self, guild_id: int, key: str, value: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO guild_settings(guild_id, key, value, updated_at)
            VALUES(?,?,?,datetime('now'))
            ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')
            """,
            (int(guild_id), str(key), str(value)),
        )
        await self.conn.commit()

    async def set_guild_settings(self, guild_id: int, updates: dict[str, str]) -> None:
        for k, v in updates.items():
            await self.conn.execute(
                """
                INSERT INTO guild_settings(guild_id, key, value, updated_at)
                VALUES(?,?,?,datetime('now'))
                ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')
                """,
                (int(guild_id), str(k), str(v)),
            )
        await self.conn.commit()

    async def get_guild_setting(self, guild_id: int, key: str) -> str | None:
        cur = await self.conn.execute(
            "SELECT value FROM guild_settings WHERE guild_id=? AND key=?",
            (int(guild_id), str(key)),
        )
        row = await cur.fetchone()
        return str(row[0]) if row and row[0] is not None else None

    async def get_guild_settings(self, guild_id: int) -> dict[str, str]:
        cur = await self.conn.execute(
            "SELECT key, value FROM guild_settings WHERE guild_id=?",
            (int(guild_id),),
        )
        rows = await cur.fetchall()
        return {str(k): str(v) for k, v in rows}

    async def _begin(self):
        await self.conn.execute("BEGIN IMMEDIATE")

    async def _commit(self):
        await self.conn.commit()

    async def _rollback(self):
        try:
            await self.conn.rollback()
        except Exception:
            pass

    async def add_ledger_entry(
        self,
        entry_type: str,
        amount: int,
        from_account: str | None = None,
        to_account: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        notes: str | None = None,
        guild_id: int | None = None,
    ):
        await self.conn.execute(
            """
            INSERT INTO ledger_entries(entry_type, amount, from_account, to_account, reference_type, reference_id, notes, guild_id)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                str(entry_type),
                int(amount),
                str(from_account) if from_account is not None else None,
                str(to_account) if to_account is not None else None,
                str(reference_type) if reference_type is not None else None,
                str(reference_id) if reference_id is not None else None,
                str(notes) if notes is not None else None,
                int(guild_id) if guild_id is not None else 0,
            ),
        )

    async def get_ledger_reconcile(self, guild_id: int | None = None):
        """Return (current_treasury, ledger_treasury, drift, baseline_at)."""
        gid = int(guild_id) if guild_id is not None else 0
        current = await self.get_treasury(guild_id=guild_id)

        cur = await self.conn.execute(
            """
            SELECT timestamp, amount
            FROM ledger_entries
            WHERE entry_type='treasury_set' AND guild_id=?
            ORDER BY entry_id DESC
            LIMIT 1
            """,
            (gid,),
        )
        baseline = await cur.fetchone()

        if baseline:
            baseline_at = str(baseline[0])
            ledger_treasury = int(baseline[1])
            dcur = await self.conn.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN to_account='treasury' THEN amount
                        WHEN from_account='treasury' THEN -amount
                        ELSE 0
                    END
                ), 0)
                FROM ledger_entries
                WHERE timestamp > ? AND entry_type != 'treasury_set' AND guild_id=?
                """,
                (baseline_at, gid),
            )
            delta = await dcur.fetchone()
            ledger_treasury += int(delta[0]) if delta and delta[0] is not None else 0
        else:
            baseline_at = None
            dcur = await self.conn.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN to_account='treasury' THEN amount
                        WHEN from_account='treasury' THEN -amount
                        ELSE 0
                    END
                ), 0)
                FROM ledger_entries
                WHERE entry_type != 'treasury_set' AND guild_id=?
                """,
                (gid,),
            )
            delta = await dcur.fetchone()
            ledger_treasury = int(delta[0]) if delta and delta[0] is not None else 0

        drift = int(current) - int(ledger_treasury)
        return int(current), int(ledger_treasury), int(drift), baseline_at

    async def ensure_member(self, discord_id: int, guild_id: int | None = None):
        if guild_id is None:
            await self.conn.execute(
                "INSERT OR IGNORE INTO wallets(discord_id, balance) VALUES(?, 0)",
                (int(discord_id),),
            )
            await self.conn.execute(
                "INSERT OR IGNORE INTO shareholdings(discord_id, shares) VALUES(?, 0)",
                (int(discord_id),),
            )
            await self.conn.execute(
                "INSERT OR IGNORE INTO shares_escrow(discord_id, locked_shares) VALUES(?, 0)",
                (int(discord_id),),
            )
            await self.conn.execute(
                "INSERT OR IGNORE INTO reputation(discord_id, rep) VALUES(?, 0)",
                (int(discord_id),),
            )
        else:
            await self.conn.execute(
                "INSERT OR IGNORE INTO wallets_by_guild(guild_id, discord_id, balance) VALUES(?,?,0)",
                (int(guild_id), int(discord_id)),
            )
            await self.conn.execute(
                "INSERT OR IGNORE INTO shareholdings_by_guild(guild_id, discord_id, shares) VALUES(?,?,0)",
                (int(guild_id), int(discord_id)),
            )
            await self.conn.execute(
                "INSERT OR IGNORE INTO shares_escrow_by_guild(guild_id, discord_id, locked_shares) VALUES(?,?,0)",
                (int(guild_id), int(discord_id)),
            )
            await self.conn.execute(
                "INSERT OR IGNORE INTO reputation_by_guild(guild_id, discord_id, rep) VALUES(?,?,0)",
                (int(guild_id), int(discord_id)),
            )
        await self.conn.commit()

    # =========================
    # BALANCE / SHARES / REP
    # =========================
    async def get_balance(self, discord_id: int, guild_id: int | None = None) -> int:
        await self.ensure_member(discord_id, guild_id=guild_id)
        if guild_id is None:
            cur = await self.conn.execute("SELECT balance FROM wallets WHERE discord_id=?", (int(discord_id),))
        else:
            cur = await self.conn.execute(
                "SELECT balance FROM wallets_by_guild WHERE guild_id=? AND discord_id=?",
                (int(guild_id), int(discord_id)),
            )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def add_balance(self, discord_id: int, amount: int, tx_type: str, reference: str | None = None, guild_id: int | None = None):
        await self.ensure_member(discord_id, guild_id=guild_id)
        await self._begin()
        try:
            if guild_id is None:
                await self.conn.execute(
                    "UPDATE wallets SET balance = balance + ? WHERE discord_id=?",
                    (int(amount), int(discord_id)),
                )
            else:
                await self.conn.execute(
                    "UPDATE wallets_by_guild SET balance = balance + ? WHERE guild_id=? AND discord_id=?",
                    (int(amount), int(guild_id), int(discord_id)),
                )
            await self.conn.execute(
                "INSERT INTO transactions(discord_id, type, amount, shares_delta, rep_delta, reference, guild_id) VALUES(?,?,?,?,?,?,?)",
                (int(discord_id), str(tx_type), int(amount), 0, 0, reference, int(guild_id) if guild_id is not None else 0),
            )
            if str(tx_type) == "payout" and int(amount) > 0:
                await self.add_ledger_entry(
                    entry_type="job_payout",
                    amount=int(amount),
                    from_account="treasury",
                    to_account=f"wallet:{int(discord_id)}",
                    reference_type="job",
                    reference_id=str(reference or ""),
                    notes="Job payout",
                    guild_id=guild_id,
                )
            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def get_shares(self, discord_id: int, guild_id: int | None = None) -> int:
        await self.ensure_member(discord_id, guild_id=guild_id)
        if guild_id is None:
            cur = await self.conn.execute("SELECT shares FROM shareholdings WHERE discord_id=?", (int(discord_id),))
        else:
            cur = await self.conn.execute(
                "SELECT shares FROM shareholdings_by_guild WHERE guild_id=? AND discord_id=?",
                (int(guild_id), int(discord_id)),
            )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get_shares_locked(self, discord_id: int, guild_id: int | None = None) -> int:
        await self.ensure_member(discord_id, guild_id=guild_id)
        if guild_id is None:
            cur = await self.conn.execute("SELECT locked_shares FROM shares_escrow WHERE discord_id=?", (int(discord_id),))
        else:
            cur = await self.conn.execute(
                "SELECT locked_shares FROM shares_escrow_by_guild WHERE guild_id=? AND discord_id=?",
                (int(guild_id), int(discord_id)),
            )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get_shares_available(self, discord_id: int, guild_id: int | None = None) -> int:
        total = await self.get_shares(discord_id, guild_id=guild_id)
        locked = await self.get_shares_locked(discord_id, guild_id=guild_id)
        return max(0, int(total) - int(locked))

    async def buy_shares(self, discord_id: int, shares_delta: int, cost: int, reference: str | None = None, guild_id: int | None = None):
        await self.ensure_member(discord_id, guild_id=guild_id)
        bal = await self.get_balance(discord_id, guild_id=guild_id)
        if bal < int(cost):
            raise ValueError("Not enough Org Credits to buy shares.")
        await self._begin()
        try:
            if guild_id is None:
                await self.conn.execute(
                    "UPDATE wallets SET balance = balance - ? WHERE discord_id=?",
                    (int(cost), int(discord_id)),
                )
                await self.conn.execute(
                    "UPDATE shareholdings SET shares = shares + ? WHERE discord_id=?",
                    (int(shares_delta), int(discord_id)),
                )
            else:
                await self.conn.execute(
                    "UPDATE wallets_by_guild SET balance = balance - ? WHERE guild_id=? AND discord_id=?",
                    (int(cost), int(guild_id), int(discord_id)),
                )
                await self.conn.execute(
                    "UPDATE shareholdings_by_guild SET shares = shares + ? WHERE guild_id=? AND discord_id=?",
                    (int(shares_delta), int(guild_id), int(discord_id)),
                )
            await self.conn.execute(
                "INSERT INTO transactions(discord_id, type, amount, shares_delta, rep_delta, reference, guild_id) VALUES(?,?,?,?,?,?,?)",
                (int(discord_id), "buy_shares", -int(cost), int(shares_delta), 0, reference, int(guild_id) if guild_id is not None else 0),
            )
            await self.add_ledger_entry(
                entry_type="shares_bought",
                amount=int(cost),
                from_account=f"wallet:{int(discord_id)}",
                to_account="treasury",
                reference_type="shares",
                reference_id=str(reference or ""),
                notes=f"Bought {int(shares_delta)} shares",
                guild_id=guild_id,
            )
            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def get_rep(self, discord_id: int, guild_id: int | None = None) -> int:
        await self.ensure_member(discord_id, guild_id=guild_id)
        if guild_id is None:
            cur = await self.conn.execute("SELECT rep FROM reputation WHERE discord_id=?", (int(discord_id),))
        else:
            cur = await self.conn.execute(
                "SELECT rep FROM reputation_by_guild WHERE guild_id=? AND discord_id=?",
                (int(guild_id), int(discord_id)),
            )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def add_rep(self, discord_id: int, amount: int, reference: str | None = None, guild_id: int | None = None):
        await self.ensure_member(discord_id, guild_id=guild_id)
        await self._begin()
        try:
            if guild_id is None:
                await self.conn.execute(
                    "UPDATE reputation SET rep = rep + ? WHERE discord_id=?",
                    (int(amount), int(discord_id)),
                )
            else:
                await self.conn.execute(
                    "UPDATE reputation_by_guild SET rep = rep + ? WHERE guild_id=? AND discord_id=?",
                    (int(amount), int(guild_id), int(discord_id)),
                )
            await self.conn.execute(
                "INSERT INTO transactions(discord_id, type, amount, shares_delta, rep_delta, reference, guild_id) VALUES(?,?,?,?,?,?,?)",
                (int(discord_id), "rep", 0, 0, int(amount), reference, int(guild_id) if guild_id is not None else 0),
            )
            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def get_level(self, discord_id: int, per_level: int = 100, guild_id: int | None = None) -> int:
        rep = await self.get_rep(discord_id, guild_id=guild_id)
        return int(rep) // int(per_level)

    # =========================
    # TREASURY
    # =========================
    async def get_treasury(self, guild_id: int | None = None) -> int:
        if guild_id is None:
            cur = await self.conn.execute("SELECT amount FROM treasury WHERE id=1")
            row = await cur.fetchone()
            return int(row[0]) if row else 0

        await self.conn.execute(
            "INSERT OR IGNORE INTO treasury_by_guild(guild_id, amount) VALUES(?, 0)",
            (int(guild_id),),
        )
        await self.conn.commit()
        cur = await self.conn.execute("SELECT amount FROM treasury_by_guild WHERE guild_id=?", (int(guild_id),))
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get_treasury_meta(self, guild_id: int | None = None):
        if guild_id is None:
            cur = await self.conn.execute("SELECT amount, updated_by, updated_at FROM treasury WHERE id=1")
        else:
            await self.conn.execute(
                "INSERT OR IGNORE INTO treasury_by_guild(guild_id, amount) VALUES(?, 0)",
                (int(guild_id),),
            )
            await self.conn.commit()
            cur = await self.conn.execute(
                "SELECT amount, updated_by, updated_at FROM treasury_by_guild WHERE guild_id=?",
                (int(guild_id),),
            )
        row = await cur.fetchone()
        if not row:
            return 0, None, None
        amount = int(row[0]) if row[0] is not None else 0
        updated_by = int(row[1]) if row[1] is not None else None
        updated_at = str(row[2]) if row[2] is not None else None
        return amount, updated_by, updated_at

    async def set_treasury(self, amount: int, updated_by: int | None = None, guild_id: int | None = None):
        current = await self.get_treasury(guild_id=guild_id)
        await self._begin()
        try:
            if guild_id is None:
                await self.conn.execute(
                    "UPDATE treasury SET amount=?, updated_by=?, updated_at=datetime('now') WHERE id=1",
                    (int(amount), int(updated_by) if updated_by is not None else None),
                )
            else:
                await self.conn.execute(
                    "INSERT OR IGNORE INTO treasury_by_guild(guild_id, amount) VALUES(?, 0)",
                    (int(guild_id),),
                )
                await self.conn.execute(
                    "UPDATE treasury_by_guild SET amount=?, updated_by=?, updated_at=datetime('now') WHERE guild_id=?",
                    (int(amount), int(updated_by) if updated_by is not None else None, int(guild_id)),
                )

            await self.add_ledger_entry(
                entry_type="treasury_set",
                amount=int(amount),
                from_account=f"actor:{int(updated_by)}" if updated_by is not None else None,
                to_account="treasury",
                reference_type="treasury",
                reference_id="manual-set",
                notes=f"Manual set from {int(current)} to {int(amount)}",
                guild_id=guild_id,
            )
            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def adjust_treasury(self, delta: int, updated_by: int | None = None) -> int:
        cur = await self.conn.execute("SELECT amount FROM treasury WHERE id=1")
        row = await cur.fetchone()
        current = int(row[0]) if row else 0
        new_amount = current + int(delta)
        if new_amount < 0:
            raise ValueError("Treasury cannot go negative.")
        await self._begin()
        try:
            await self.conn.execute(
                "UPDATE treasury SET amount=?, updated_by=?, updated_at=datetime('now') WHERE id=1",
                (int(new_amount), int(updated_by) if updated_by is not None else None),
            )
            await self.add_ledger_entry(
                entry_type="treasury_adjust",
                amount=abs(int(delta)),
                from_account=("treasury" if int(delta) < 0 else f"actor:{int(updated_by)}" if updated_by is not None else "external"),
                to_account=("treasury" if int(delta) > 0 else f"actor:{int(updated_by)}" if updated_by is not None else "external"),
                reference_type="treasury",
                reference_id="manual-adjust",
                notes=f"Treasury adjusted by {int(delta)}",
            )
            await self._commit()
            return int(new_amount)
        except Exception:
            await self._rollback()
            raise

    # =========================
    # JOBS
    # =========================
    async def get_reserved_job_escrow(self, guild_id: int | None = None) -> int:
        if guild_id is None:
            cur = await self.conn.execute(
                "SELECT COALESCE(SUM(escrow_amount), 0) FROM jobs WHERE escrow_status='reserved'"
            )
        else:
            cur = await self.conn.execute(
                "SELECT COALESCE(SUM(escrow_amount), 0) FROM jobs WHERE escrow_status='reserved' AND guild_id=?",
                (int(guild_id),),
            )
        row = await cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    async def create_job(
        self,
        channel_id: int,
        message_id: int,
        title: str,
        description: str,
        reward: int,
        created_by: int,
        category: str | None = None,
        template_id: int | None = None,
        guild_id: int | None = None,
    ) -> int:
        reward_i = int(reward)

        await self._begin()
        try:
            # Job rewards are attributed Org Points/Credits and do not reserve treasury.
            cur = await self.conn.execute(
                """
                INSERT INTO jobs(channel_id, message_id, title, description, reward, status, created_by, escrow_amount, escrow_status, funded, category, template_id, guild_id)
                VALUES(?,?,?,?,?,'open',?,?, 'none', 1, ?, ?, ?)
                """,
                (
                    int(channel_id),
                    int(message_id),
                    str(title),
                    str(description),
                    reward_i,
                    int(created_by),
                    0,
                    (str(category).strip() if category else None),
                    (int(template_id) if template_id is not None else None),
                    (int(guild_id) if guild_id is not None else 0),
                ),
            )
            job_id = int(cur.lastrowid)

            await self._commit()
            return job_id
        except Exception:
            await self._rollback()
            raise

    async def get_job(self, job_id: int, guild_id: int | None = None):
        if guild_id is None:
            cur = await self.conn.execute(
                """
                SELECT job_id, channel_id, message_id, title, description, reward, status,
                       created_by, claimed_by, thread_id, created_at, updated_at
                FROM jobs WHERE job_id=?
                """,
                (int(job_id),),
            )
        else:
            cur = await self.conn.execute(
                """
                SELECT job_id, channel_id, message_id, title, description, reward, status,
                       created_by, claimed_by, thread_id, created_at, updated_at
                FROM jobs WHERE job_id=? AND guild_id=?
                """,
                (int(job_id), int(guild_id)),
            )
        return await cur.fetchone()

    async def get_job_template_by_name(self, name: str):
        cur = await self.conn.execute(
            """
            SELECT template_id, name, default_title, default_description,
                   default_reward_min, default_reward_max, default_tier_required,
                   category, active
            FROM job_templates
            WHERE lower(name)=lower(?)
            LIMIT 1
            """,
            (str(name).strip(),),
        )
        return await cur.fetchone()

    async def get_job_category(self, job_id: int) -> str | None:
        cur = await self.conn.execute("SELECT category FROM jobs WHERE job_id=?", (int(job_id),))
        row = await cur.fetchone()
        if not row:
            return None
        return str(row[0]).strip().lower() if row[0] is not None else None

    async def get_job_attendance_lock(self, job_id: int) -> bool:
        cur = await self.conn.execute("SELECT attendance_locked FROM jobs WHERE job_id=?", (int(job_id),))
        row = await cur.fetchone()
        return bool(int(row[0])) if row else False

    async def set_job_attendance_lock(self, job_id: int, locked: bool) -> bool:
        cur = await self.conn.execute(
            "UPDATE jobs SET attendance_locked=?, updated_at=datetime('now') WHERE job_id=?",
            (1 if locked else 0, int(job_id)),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def set_job_attendance_snapshot(self, job_id: int, discord_ids: list[int]):
        data = ",".join(str(int(x)) for x in discord_ids)
        await self.conn.execute(
            "UPDATE jobs SET attendance_snapshot=?, updated_at=datetime('now') WHERE job_id=?",
            (data, int(job_id)),
        )
        await self.conn.commit()

    async def get_job_attendance_snapshot(self, job_id: int) -> list[int]:
        cur = await self.conn.execute("SELECT attendance_snapshot FROM jobs WHERE job_id=?", (int(job_id),))
        row = await cur.fetchone()
        if not row or not row[0]:
            return []
        out = []
        for part in str(row[0]).split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
        return out

    async def add_event_attendee(self, job_id: int, discord_id: int) -> bool:
        if await self.get_job_attendance_lock(int(job_id)):
            return False
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO job_event_attendance(job_id, discord_id, status) VALUES(?,?, 'joined')",
            (int(job_id), int(discord_id)),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def add_event_attendee_force(self, job_id: int, discord_id: int) -> bool:
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO job_event_attendance(job_id, discord_id, status) VALUES(?,?, 'joined')",
            (int(job_id), int(discord_id)),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def remove_event_attendee(self, job_id: int, discord_id: int) -> bool:
        if await self.get_job_attendance_lock(int(job_id)):
            return False
        cur = await self.conn.execute(
            "DELETE FROM job_event_attendance WHERE job_id=? AND discord_id=?",
            (int(job_id), int(discord_id)),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def remove_event_attendee_force(self, job_id: int, discord_id: int) -> bool:
        cur = await self.conn.execute(
            "DELETE FROM job_event_attendance WHERE job_id=? AND discord_id=?",
            (int(job_id), int(discord_id)),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def list_event_attendees(self, job_id: int):
        cur = await self.conn.execute(
            "SELECT discord_id, status, joined_at FROM job_event_attendance WHERE job_id=? ORDER BY joined_at ASC",
            (int(job_id),),
        )
        return await cur.fetchall()

    async def link_event_job(self, event_id: int, job_id: int):
        await self.conn.execute(
            "INSERT OR REPLACE INTO job_event_links(event_id, job_id) VALUES(?,?)",
            (int(event_id), int(job_id)),
        )
        await self.conn.commit()

    async def get_job_id_by_event(self, event_id: int) -> int | None:
        cur = await self.conn.execute("SELECT job_id FROM job_event_links WHERE event_id=?", (int(event_id),))
        row = await cur.fetchone()
        if not row:
            return None
        return int(row[0])

    async def list_job_templates(self, include_inactive: bool = True, limit: int = 50):
        if include_inactive:
            cur = await self.conn.execute(
                """
                SELECT template_id, name, default_title, default_description,
                       default_reward_min, default_reward_max, default_tier_required,
                       category, active
                FROM job_templates
                ORDER BY name ASC
                LIMIT ?
                """,
                (int(limit),),
            )
        else:
            cur = await self.conn.execute(
                """
                SELECT template_id, name, default_title, default_description,
                       default_reward_min, default_reward_max, default_tier_required,
                       category, active
                FROM job_templates
                WHERE active=1
                ORDER BY name ASC
                LIMIT ?
                """,
                (int(limit),),
            )
        return await cur.fetchall()

    async def upsert_job_template(
        self,
        name: str,
        default_title: str,
        default_description: str,
        default_reward_min: int,
        default_reward_max: int,
        default_tier_required: int,
        category: str | None,
        active: bool = True,
    ):
        await self._begin()
        try:
            existing = await self.get_job_template_by_name(name)
            if existing:
                template_id = int(existing[0])
                await self.conn.execute(
                    """
                    UPDATE job_templates
                    SET default_title=?, default_description=?, default_reward_min=?,
                        default_reward_max=?, default_tier_required=?, category=?, active=?
                    WHERE template_id=?
                    """,
                    (
                        str(default_title),
                        str(default_description),
                        int(default_reward_min),
                        int(default_reward_max),
                        int(default_tier_required),
                        (str(category).strip() if category else None),
                        (1 if active else 0),
                        int(template_id),
                    ),
                )
            else:
                cur = await self.conn.execute(
                    """
                    INSERT INTO job_templates(
                        name, default_title, default_description,
                        default_reward_min, default_reward_max,
                        default_tier_required, category, active
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(name).strip(),
                        str(default_title),
                        str(default_description),
                        int(default_reward_min),
                        int(default_reward_max),
                        int(default_tier_required),
                        (str(category).strip() if category else None),
                        (1 if active else 0),
                    ),
                )
                template_id = int(cur.lastrowid)

            await self._commit()
            return int(template_id)
        except Exception:
            await self._rollback()
            raise

    async def set_job_template_active(self, name: str, active: bool) -> bool:
        cur = await self.conn.execute(
            "UPDATE job_templates SET active=? WHERE lower(name)=lower(?)",
            ((1 if active else 0), str(name).strip()),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def delete_job_template(self, name: str) -> bool:
        cur = await self.conn.execute(
            "DELETE FROM job_templates WHERE lower(name)=lower(?)",
            (str(name).strip(),),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def claim_job(self, job_id: int, claimed_by: int) -> bool:
        await self._begin()
        try:
            cur = await self.conn.execute(
                """
                UPDATE jobs
                SET status='claimed', claimed_by=?, updated_at=datetime('now')
                WHERE job_id=? AND status='open' AND claimed_by IS NULL
                """,
                (int(claimed_by), int(job_id)),
            )
            await self._commit()
            return cur.rowcount == 1
        except Exception:
            await self._rollback()
            raise

    async def set_job_thread(self, job_id: int, thread_id: int):
        await self.conn.execute(
            "UPDATE jobs SET thread_id=?, updated_at=datetime('now') WHERE job_id=?",
            (int(thread_id), int(job_id)),
        )
        await self.conn.commit()

    async def complete_job(self, job_id: int) -> bool:
        await self._begin()
        try:
            cur = await self.conn.execute(
                """
                UPDATE jobs
                SET status='completed', updated_at=datetime('now')
                WHERE job_id=? AND status='claimed'
                """,
                (int(job_id),),
            )
            await self._commit()
            return cur.rowcount == 1
        except Exception:
            await self._rollback()
            raise

    async def settle_job_payout(
        self,
        job_id: int,
        payout_targets: list[tuple[int, int]],
        confirmed_by: int | None = None,
        guild_id: int | None = None,
    ) -> dict:
        """Settle a completed job with partial treasury payout + automatic bonds."""
        await self._begin()
        try:
            cur = await self.conn.execute(
                "SELECT status, reward, escrow_amount, escrow_status FROM jobs WHERE job_id=?",
                (int(job_id),),
            )
            row = await cur.fetchone()
            if not row:
                await self._rollback()
                return {"ok": False, "reason": "job_not_found"}

            status, reward, escrow_amount, escrow_status = str(row[0]), int(row[1]), int(row[2] or 0), str(row[3] or "none")
            if status != "completed":
                await self._rollback()
                return {"ok": False, "reason": "job_not_completed"}

            normalized_targets = [(int(uid), max(0, int(amount))) for uid, amount in payout_targets if int(amount) > 0]
            total_owed = sum(int(amount) for _, amount in normalized_targets)
            if total_owed <= 0:
                await self._rollback()
                return {"ok": False, "reason": "no_payout_targets"}

            gid = int(guild_id) if guild_id is not None else 0
            treasury_amount = 0
            if TREASURY_AUTODEDUCT:
                if guild_id is None:
                    tcur = await self.conn.execute("SELECT amount FROM treasury WHERE id=1")
                    trow = await tcur.fetchone()
                    treasury_amount = int(trow[0]) if trow else 0
                else:
                    await self.conn.execute(
                        "INSERT OR IGNORE INTO treasury_by_guild(guild_id, amount) VALUES(?, 0)",
                        (int(guild_id),),
                    )
                    tcur = await self.conn.execute(
                        "SELECT amount FROM treasury_by_guild WHERE guild_id=?",
                        (int(guild_id),),
                    )
                    trow = await tcur.fetchone()
                    treasury_amount = int(trow[0]) if trow else 0

            pay_now = min(int(total_owed), max(0, int(treasury_amount))) if TREASURY_AUTODEDUCT else int(total_owed)
            if TREASURY_AUTODEDUCT and pay_now > 0:
                if guild_id is None:
                    await self.conn.execute(
                        "UPDATE treasury SET amount = amount - ?, updated_by=?, updated_at=datetime('now') WHERE id=1",
                        (int(pay_now), int(confirmed_by) if confirmed_by is not None else None),
                    )
                else:
                    await self.conn.execute(
                        "UPDATE treasury_by_guild SET amount = amount - ?, updated_by=?, updated_at=datetime('now') WHERE guild_id=?",
                        (int(pay_now), int(confirmed_by) if confirmed_by is not None else None, int(guild_id)),
                    )

            remaining_to_pay = int(pay_now)
            paid_targets: list[tuple[int, int]] = []
            bond_targets: list[tuple[int, int, int]] = []
            for uid, owed in normalized_targets:
                paid = min(int(owed), int(remaining_to_pay))
                if paid > 0:
                    paid_targets.append((int(uid), int(paid)))
                    remaining_to_pay -= int(paid)
                outstanding = int(owed) - int(paid)
                if outstanding > 0:
                    bcur = await self.conn.execute(
                        """
                        INSERT INTO payout_bonds(guild_id, org_id, user_id, amount_owed, status, job_reference)
                        VALUES(?, ?, ?, ?, 'pending', ?)
                        """,
                        (gid, None, int(uid), int(outstanding), f"job:{int(job_id)}"),
                    )
                    bond_targets.append((int(uid), int(outstanding), int(bcur.lastrowid)))

            await self.conn.execute(
                """
                UPDATE jobs
                SET status='paid', escrow_status='released', updated_at=datetime('now')
                WHERE job_id=? AND status='completed'
                """,
                (int(job_id),),
            )

            payout_amount = int(escrow_amount or reward)
            if escrow_status == "reserved" and payout_amount > 0:
                await self.add_ledger_entry(
                    entry_type="escrow_released",
                    amount=int(payout_amount),
                    from_account=f"job_escrow:{int(job_id)}",
                    to_account="settled",
                    reference_type="job",
                    reference_id=str(int(job_id)),
                    notes="Released reserved job escrow on confirm",
                    guild_id=guild_id,
                )

            await self.add_ledger_entry(
                entry_type="job_payout_settlement",
                amount=int(total_owed),
                from_account="treasury" if TREASURY_AUTODEDUCT else "external",
                to_account=f"members:{len(normalized_targets)}",
                reference_type="job",
                reference_id=str(int(job_id)),
                notes=f"pay_now={int(pay_now)};bond_amount={int(total_owed - pay_now)}",
                guild_id=guild_id,
            )

            await self._commit()
            return {
                "ok": True,
                "total_owed": int(total_owed),
                "pay_now": int(pay_now),
                "bond_amount": int(total_owed - pay_now),
                "paid_targets": paid_targets,
                "bond_targets": bond_targets,
            }
        except Exception:
            await self._rollback()
            raise

    async def mark_paid(self, job_id: int) -> bool:
        # Backward-compatible wrapper for legacy callers.
        row = await self.get_job(int(job_id), guild_id=None)
        if not row:
            return False
        claimed_by = int(row[8]) if row[8] is not None else None
        reward = int(row[5]) if row[5] is not None else 0
        targets = [(int(claimed_by), int(reward))] if claimed_by and reward > 0 else []
        result = await self.settle_job_payout(int(job_id), targets, confirmed_by=None, guild_id=None)
        return bool(result.get("ok"))

    # =========================
    # PAYOUT BONDS
    # =========================
    async def create_payout_bond(
        self,
        user_id: int,
        amount_owed: int,
        guild_id: int | None = None,
        org_id: str | None = None,
        job_reference: str | None = None,
    ) -> int:
        amount_i = int(amount_owed)
        if amount_i <= 0:
            raise ValueError("Bond amount must be positive.")

        cur = await self.conn.execute(
            """
            INSERT INTO payout_bonds(guild_id, org_id, user_id, amount_owed, status, job_reference)
            VALUES(?, ?, ?, ?, 'pending', ?)
            """,
            (
                int(guild_id) if guild_id is not None else 0,
                str(org_id) if org_id is not None else None,
                int(user_id),
                amount_i,
                str(job_reference) if job_reference is not None else None,
            ),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def list_pending_bonds(
        self,
        user_id: int,
        guild_id: int | None = None,
        limit: int = 100,
    ) -> list[tuple[int, int, int, str, str | None]]:
        """Returns pending bonds FIFO as tuples: (bond_id, user_id, amount_owed, created_at, job_reference)."""
        lim = max(1, min(int(limit), 1000))
        cur = await self.conn.execute(
            """
            SELECT bond_id, user_id, amount_owed, created_at, job_reference
            FROM payout_bonds
            WHERE user_id=? AND guild_id=? AND status='pending'
            ORDER BY datetime(created_at) ASC, bond_id ASC
            LIMIT ?
            """,
            (int(user_id), int(guild_id) if guild_id is not None else 0, lim),
        )
        rows = await cur.fetchall()
        return [(int(r[0]), int(r[1]), int(r[2]), str(r[3]), (str(r[4]) if r[4] is not None else None)) for r in rows]

    async def get_total_outstanding_bonds(self, guild_id: int | None = None) -> int:
        cur = await self.conn.execute(
            "SELECT COALESCE(SUM(amount_owed), 0) FROM payout_bonds WHERE guild_id=? AND status='pending'",
            (int(guild_id) if guild_id is not None else 0,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    async def get_user_outstanding_bonds(self, user_id: int, guild_id: int | None = None) -> tuple[int, int]:
        cur = await self.conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(amount_owed), 0)
            FROM payout_bonds
            WHERE user_id=? AND guild_id=? AND status='pending'
            """,
            (int(user_id), int(guild_id) if guild_id is not None else 0),
        )
        row = await cur.fetchone()
        if not row:
            return 0, 0
        return int(row[0] or 0), int(row[1] or 0)

    async def mark_bond_redeemed(self, bond_id: int, guild_id: int | None = None) -> bool:
        cur = await self.conn.execute(
            """
            UPDATE payout_bonds
            SET status='redeemed', redeemed_at=datetime('now')
            WHERE bond_id=? AND guild_id=? AND status='pending'
            """,
            (int(bond_id), int(guild_id) if guild_id is not None else 0),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def redeem_bonds_for_user(
        self,
        user_id: int,
        guild_id: int | None = None,
        redeemed_by: int | None = None,
    ) -> dict:
        """Redeem pending bonds FIFO for a user using available treasury.

        Returns dict with keys: redeemed_count, paid_total, treasury_before, treasury_after,
        attempted_count, pending_after, redeemed_bond_ids.
        """
        gid = int(guild_id) if guild_id is not None else 0
        uid = int(user_id)

        await self._begin()
        try:
            # Ensure wallet row exists without nested commits.
            if guild_id is None:
                await self.conn.execute(
                    "INSERT OR IGNORE INTO wallets(discord_id, balance) VALUES(?, 0)",
                    (uid,),
                )
                tcur = await self.conn.execute("SELECT amount FROM treasury WHERE id=1")
            else:
                await self.conn.execute(
                    "INSERT OR IGNORE INTO wallets_by_guild(guild_id, discord_id, balance) VALUES(?,?,0)",
                    (gid, uid),
                )
                await self.conn.execute(
                    "INSERT OR IGNORE INTO treasury_by_guild(guild_id, amount) VALUES(?, 0)",
                    (gid,),
                )
                tcur = await self.conn.execute(
                    "SELECT amount FROM treasury_by_guild WHERE guild_id=?",
                    (gid,),
                )

            trow = await tcur.fetchone()
            treasury_before = int(trow[0]) if trow else 0
            remaining = int(treasury_before)

            pcur = await self.conn.execute(
                """
                SELECT bond_id, amount_owed
                FROM payout_bonds
                WHERE user_id=? AND guild_id=? AND status='pending'
                ORDER BY datetime(created_at) ASC, bond_id ASC
                """,
                (uid, gid),
            )
            pending_rows = await pcur.fetchall()

            paid_total = 0
            redeemed_count = 0
            redeemed_bond_ids: list[int] = []

            for bond_id_raw, amount_raw in pending_rows:
                bond_id = int(bond_id_raw)
                owed = max(0, int(amount_raw or 0))
                if owed <= 0:
                    continue
                if remaining < owed:
                    break

                remaining -= owed
                paid_total += owed
                redeemed_count += 1
                redeemed_bond_ids.append(bond_id)

                await self.conn.execute(
                    """
                    UPDATE payout_bonds
                    SET status='redeemed', redeemed_at=datetime('now')
                    WHERE bond_id=? AND guild_id=? AND status='pending'
                    """,
                    (bond_id, gid),
                )

                if guild_id is None:
                    await self.conn.execute(
                        "UPDATE wallets SET balance = balance + ? WHERE discord_id=?",
                        (owed, uid),
                    )
                else:
                    await self.conn.execute(
                        "UPDATE wallets_by_guild SET balance = balance + ? WHERE guild_id=? AND discord_id=?",
                        (owed, gid, uid),
                    )

                await self.conn.execute(
                    "INSERT INTO transactions(discord_id, type, amount, shares_delta, rep_delta, reference, guild_id) VALUES(?,?,?,?,?,?,?)",
                    (
                        uid,
                        "bond_redeem",
                        int(owed),
                        0,
                        0,
                        f"bond:{bond_id}|redeemed_by:{int(redeemed_by)}" if redeemed_by is not None else f"bond:{bond_id}|redeemed",
                        gid,
                    ),
                )

            if paid_total > 0:
                if guild_id is None:
                    await self.conn.execute(
                        "UPDATE treasury SET amount=?, updated_by=?, updated_at=datetime('now') WHERE id=1",
                        (int(remaining), int(redeemed_by) if redeemed_by is not None else None),
                    )
                else:
                    await self.conn.execute(
                        "UPDATE treasury_by_guild SET amount=?, updated_by=?, updated_at=datetime('now') WHERE guild_id=?",
                        (int(remaining), int(redeemed_by) if redeemed_by is not None else None, gid),
                    )

                await self.add_ledger_entry(
                    entry_type="bond_redeem",
                    amount=int(paid_total),
                    from_account="treasury",
                    to_account=f"wallet:{uid}",
                    reference_type="bond",
                    reference_id=(",".join(str(i) for i in redeemed_bond_ids[:20]) if redeemed_bond_ids else None),
                    notes=f"Redeemed {int(redeemed_count)} bond(s) for user {uid}",
                    guild_id=guild_id,
                )

            p2 = await self.conn.execute(
                "SELECT COUNT(*) FROM payout_bonds WHERE user_id=? AND guild_id=? AND status='pending'",
                (uid, gid),
            )
            pending_after_row = await p2.fetchone()
            pending_after = int(pending_after_row[0]) if pending_after_row else 0

            await self._commit()
            return {
                "redeemed_count": int(redeemed_count),
                "paid_total": int(paid_total),
                "treasury_before": int(treasury_before),
                "treasury_after": int(remaining),
                "attempted_count": int(len(pending_rows)),
                "pending_after": int(pending_after),
                "redeemed_bond_ids": redeemed_bond_ids,
            }
        except Exception:
            await self._rollback()
            raise

    async def cancel_job(self, job_id: int) -> bool:
        await self._begin()
        try:
            cur = await self.conn.execute(
                "SELECT status, escrow_amount, escrow_status FROM jobs WHERE job_id=?",
                (int(job_id),),
            )
            row = await cur.fetchone()
            if not row:
                await self._rollback()
                return False

            status, escrow_amount, escrow_status = str(row[0]), int(row[1] or 0), str(row[2] or "none")
            if status in ("paid", "cancelled"):
                await self._rollback()
                return False

            await self.conn.execute(
                """
                UPDATE jobs
                SET status='cancelled', escrow_status='released', updated_at=datetime('now')
                WHERE job_id=? AND status NOT IN ('paid','cancelled')
                """,
                (int(job_id),),
            )

            if escrow_status == "reserved" and int(escrow_amount) > 0:
                await self.add_ledger_entry(
                    entry_type="escrow_released",
                    amount=int(escrow_amount),
                    from_account=f"job_escrow:{int(job_id)}",
                    to_account="treasury_available",
                    reference_type="job",
                    reference_id=str(int(job_id)),
                    notes="Released reserved job escrow on cancel",
                )

            await self._commit()
            return True
        except Exception:
            await self._rollback()
            raise

    # =========================
    # SHARES ESCROW (CASHOUT)
    # =========================
    async def lock_shares(self, discord_id: int, shares: int, guild_id: int | None = None):
        await self.ensure_member(discord_id, guild_id=guild_id)
        available = await self.get_shares_available(discord_id, guild_id=guild_id)
        if available < int(shares):
            raise ValueError("Not enough available shares to lock.")
        if guild_id is None:
            await self.conn.execute(
                "UPDATE shares_escrow SET locked_shares = locked_shares + ? WHERE discord_id=?",
                (int(shares), int(discord_id)),
            )
        else:
            await self.conn.execute(
                "UPDATE shares_escrow_by_guild SET locked_shares = locked_shares + ? WHERE guild_id=? AND discord_id=?",
                (int(shares), int(guild_id), int(discord_id)),
            )
        await self.add_ledger_entry(
            entry_type="escrow_reserved",
            amount=int(shares),
            from_account=f"shares:{int(discord_id)}",
            to_account=f"escrow:{int(discord_id)}",
            reference_type="cashout",
            reference_id=None,
            notes="Shares locked for cashout",
        )
        await self.conn.commit()

    async def unlock_shares(self, discord_id: int, shares: int, guild_id: int | None = None):
        await self.ensure_member(discord_id, guild_id=guild_id)
        locked = await self.get_shares_locked(discord_id, guild_id=guild_id)
        to_unlock = min(int(locked), int(shares))
        if guild_id is None:
            await self.conn.execute(
                "UPDATE shares_escrow SET locked_shares = locked_shares - ? WHERE discord_id=?",
                (int(to_unlock), int(discord_id)),
            )
        else:
            await self.conn.execute(
                "UPDATE shares_escrow_by_guild SET locked_shares = locked_shares - ? WHERE guild_id=? AND discord_id=?",
                (int(to_unlock), int(guild_id), int(discord_id)),
            )
        if int(to_unlock) > 0:
            await self.add_ledger_entry(
                entry_type="escrow_released",
                amount=int(to_unlock),
                from_account=f"escrow:{int(discord_id)}",
                to_account=f"shares:{int(discord_id)}",
                reference_type="cashout",
                reference_id=None,
                notes="Shares unlocked from cashout escrow",
            )
        await self.conn.commit()

    async def finalize_cashout_paid(
        self,
        request_id: int,
        payout_amount: int,
        handled_by: int | None = None,
        note: str | None = None,
        guild_id: int | None = None,
    ):
        if guild_id is None:
            cur = await self.conn.execute(
                "SELECT requester_id, shares, status, guild_id FROM cashout_requests WHERE request_id=?",
                (int(request_id),),
            )
        else:
            cur = await self.conn.execute(
                "SELECT requester_id, shares, status, guild_id FROM cashout_requests WHERE request_id=? AND guild_id=?",
                (int(request_id), int(guild_id)),
            )
        row = await cur.fetchone()
        if not row:
            raise ValueError("Cash-out request not found.")
        requester_id, shares, status, request_guild_id = int(row[0]), int(row[1]), str(row[2]), int(row[3])

        if status != "approved":
            raise ValueError(f"Request must be approved first (status: {status}).")

        lcur = await self.conn.execute(
            "SELECT locked_shares FROM shares_escrow_by_guild WHERE guild_id=? AND discord_id=?",
            (int(request_guild_id), int(requester_id)),
        )
        lrow = await lcur.fetchone()
        locked = int(lrow[0]) if lrow else 0
        if locked < int(shares):
            raise ValueError("Not enough locked shares to finalize this cash-out.")

        hcur = await self.conn.execute(
            "SELECT shares FROM shareholdings_by_guild WHERE guild_id=? AND discord_id=?",
            (int(request_guild_id), int(requester_id)),
        )
        hrow = await hcur.fetchone()
        holding = int(hrow[0]) if hrow else 0
        if holding < int(shares):
            raise ValueError("Member does not have enough shares to sell.")

        if TREASURY_AUTODEDUCT and STRICT_TREASURY:
            treasury_amount = await self.get_treasury(guild_id=request_guild_id)
            if treasury_amount < int(payout_amount):
                raise ValueError("Treasury too low for this payout.")

        await self._begin()
        try:
            if TREASURY_AUTODEDUCT:
                await self.conn.execute(
                    "INSERT OR IGNORE INTO treasury_by_guild(guild_id, amount) VALUES(?, 0)",
                    (int(request_guild_id),),
                )
                await self.conn.execute(
                    "UPDATE treasury_by_guild SET amount = amount - ?, updated_by=?, updated_at=datetime('now') WHERE guild_id=?",
                    (int(payout_amount), int(handled_by) if handled_by is not None else None, int(request_guild_id)),
                )

            await self.conn.execute(
                "UPDATE shares_escrow_by_guild SET locked_shares = locked_shares - ? WHERE guild_id=? AND discord_id=?",
                (int(shares), int(request_guild_id), int(requester_id)),
            )
            await self.add_ledger_entry(
                entry_type="escrow_released",
                amount=int(shares),
                from_account=f"escrow:{int(requester_id)}",
                to_account="sold",
                reference_type="cashout",
                reference_id=str(int(request_id)),
                notes="Escrow released on paid cashout",
                guild_id=request_guild_id,
            )
            await self.conn.execute(
                "UPDATE shareholdings_by_guild SET shares = shares - ? WHERE guild_id=? AND discord_id=?",
                (int(shares), int(request_guild_id), int(requester_id)),
            )
            await self.conn.execute(
                "UPDATE cashout_requests SET status='paid', handled_by=?, handled_note=?, updated_at=datetime('now') WHERE request_id=?",
                (int(handled_by) if handled_by is not None else None, note, int(request_id)),
            )

            await self.add_ledger_entry(
                entry_type="shares_sold",
                amount=int(shares),
                from_account=f"shares:{int(requester_id)}",
                to_account="sold",
                reference_type="cashout",
                reference_id=str(int(request_id)),
                notes=f"Sold {int(shares)} shares via cashout",
                guild_id=request_guild_id,
            )

            await self.add_ledger_entry(
                entry_type="cashout_paid",
                amount=int(payout_amount),
                from_account="treasury" if TREASURY_AUTODEDUCT else "external",
                to_account=f"wallet:{int(requester_id)}",
                reference_type="cashout",
                reference_id=str(int(request_id)),
                notes="Cashout finalized as paid",
                guild_id=request_guild_id,
            )

            await self._commit()
            return requester_id, shares
        except Exception:
            await self._rollback()
            raise

    async def create_cashout_request(self, guild_id: int, channel_id: int, message_id: int, requester_id: int, shares: int) -> int:
        cur = await self.conn.execute(
            "INSERT INTO cashout_requests(guild_id, channel_id, message_id, requester_id, shares, status) VALUES(?,?,?,?,?,?)",
            (int(guild_id), int(channel_id), int(message_id), int(requester_id), int(shares), "pending"),
        )
        await self.conn.commit()
        return int(cur.lastrowid)

    async def set_cashout_thread(self, request_id: int, thread_id: int, guild_id: int | None = None):
        if guild_id is None:
            await self.conn.execute(
                "UPDATE cashout_requests SET thread_id=?, updated_at=datetime('now') WHERE request_id=?",
                (int(thread_id), int(request_id)),
            )
        else:
            await self.conn.execute(
                "UPDATE cashout_requests SET thread_id=?, updated_at=datetime('now') WHERE request_id=? AND guild_id=?",
                (int(thread_id), int(request_id), int(guild_id)),
            )
        await self.conn.commit()

    async def set_cashout_status(self, request_id: int, status: str, handled_by: int | None = None, note: str | None = None, guild_id: int | None = None):
        status_str = str(status)

        await self._begin()
        try:
            if guild_id is None:
                await self.conn.execute(
                    "UPDATE cashout_requests SET status=?, handled_by=?, handled_note=?, updated_at=datetime('now') WHERE request_id=?",
                    (status_str, int(handled_by) if handled_by is not None else None, note, int(request_id)),
                )
            else:
                await self.conn.execute(
                    "UPDATE cashout_requests SET status=?, handled_by=?, handled_note=?, updated_at=datetime('now') WHERE request_id=? AND guild_id=?",
                    (status_str, int(handled_by) if handled_by is not None else None, note, int(request_id), int(guild_id)),
                )

            if status_str == "approved":
                if guild_id is None:
                    cur = await self.conn.execute(
                        "SELECT requester_id, shares, guild_id FROM cashout_requests WHERE request_id=?",
                        (int(request_id),),
                    )
                else:
                    cur = await self.conn.execute(
                        "SELECT requester_id, shares, guild_id FROM cashout_requests WHERE request_id=? AND guild_id=?",
                        (int(request_id), int(guild_id)),
                    )
                row = await cur.fetchone()
                if row:
                    requester_id, shares, row_gid = int(row[0]), int(row[1]), int(row[2])
                    est_amount = int(shares) * int(SHARE_CASHOUT_AUEC_PER_SHARE)
                    await self.add_ledger_entry(
                        entry_type="cashout_approved",
                        amount=int(est_amount),
                        from_account="treasury",
                        to_account=f"wallet:{requester_id}",
                        reference_type="cashout",
                        reference_id=str(int(request_id)),
                        notes="Cashout approved (estimated payout)",
                        guild_id=row_gid,
                    )

            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def get_cashout_request(self, request_id: int, guild_id: int | None = None):
        if guild_id is None:
            cur = await self.conn.execute(
                "SELECT request_id, guild_id, channel_id, message_id, requester_id, shares, status, created_at, updated_at, thread_id, handled_by, handled_note "
                "FROM cashout_requests WHERE request_id=?",
                (int(request_id),),
            )
        else:
            cur = await self.conn.execute(
                "SELECT request_id, guild_id, channel_id, message_id, requester_id, shares, status, created_at, updated_at, thread_id, handled_by, handled_note "
                "FROM cashout_requests WHERE request_id=? AND guild_id=?",
                (int(request_id), int(guild_id)),
            )
        return await cur.fetchone()

    # =========================
    # FINANCE DASHBOARD HELPERS
    # =========================
    async def list_cashout_requests(self, statuses: list[str], limit: int = 25, guild_id: int | None = None):
        """
        Returns rows of cashout_requests, newest first.
        Row shape matches get_cashout_request plus created/updated fields etc.
        """
        statuses = [str(s) for s in (statuses or []) if str(s).strip()]
        if not statuses:
            statuses = ["pending"]

        q_marks = ",".join(["?"] * len(statuses))
        if guild_id is None:
            cur = await self.conn.execute(
                f"""
                SELECT request_id, guild_id, channel_id, message_id, requester_id, shares, status,
                       created_at, updated_at, thread_id, handled_by, handled_note
                FROM cashout_requests
                WHERE status IN ({q_marks})
                ORDER BY datetime(created_at) DESC, request_id DESC
                LIMIT ?
                """,
                (*statuses, int(limit)),
            )
        else:
            cur = await self.conn.execute(
                f"""
                SELECT request_id, guild_id, channel_id, message_id, requester_id, shares, status,
                       created_at, updated_at, thread_id, handled_by, handled_note
                FROM cashout_requests
                WHERE status IN ({q_marks}) AND guild_id=?
                ORDER BY datetime(created_at) DESC, request_id DESC
                LIMIT ?
                """,
                (*statuses, int(guild_id), int(limit)),
            )
        return await cur.fetchall()

    async def count_cashout_requests(self, statuses: list[str], guild_id: int | None = None) -> int:
        statuses = [str(s) for s in (statuses or []) if str(s).strip()]
        if not statuses:
            statuses = ["pending"]
        q_marks = ",".join(["?"] * len(statuses))
        if guild_id is None:
            cur = await self.conn.execute(
                f"SELECT COUNT(*) FROM cashout_requests WHERE status IN ({q_marks})",
                (*statuses,),
            )
        else:
            cur = await self.conn.execute(
                f"SELECT COUNT(*) FROM cashout_requests WHERE status IN ({q_marks}) AND guild_id=?",
                (*statuses, int(guild_id)),
            )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def list_transactions(
        self,
        types: list[str] | None = None,
        limit: int = 25,
        discord_id: int | None = None,
        guild_id: int | None = None,
    ):
        """
        Returns rows of transactions newest first.
        """
        where = []
        params: list = []

        if guild_id is None:
            where.append("guild_id=0")
        else:
            where.append("guild_id=?")
            params.append(int(guild_id))

        if discord_id is not None:
            where.append("discord_id=?")
            params.append(int(discord_id))

        if types:
            clean = [str(t) for t in types if str(t).strip()]
            if clean:
                q_marks = ",".join(["?"] * len(clean))
                where.append(f"type IN ({q_marks})")
                params.extend(clean)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        cur = await self.conn.execute(
            f"""
            SELECT tx_id, discord_id, type, amount, shares_delta, rep_delta, reference, created_at
            FROM transactions
            {where_sql}
            ORDER BY datetime(created_at) DESC, tx_id DESC
            LIMIT ?
            """,
            (*params, int(limit)),
        )
        return await cur.fetchall()

    async def reconcile_escrow(
        self,
        discord_id: int | None = None,
        dry_run: bool = True,
        force_clear_active: bool = False,
        handled_by: int | None = None,
        guild_id: int | None = None,
    ):
        """
        Rebuild escrow locks from active cashout requests.

        Active requests: pending, approved.
        If force_clear_active=True, active requests in scope are marked rejected and expected locks become 0.
        """
        if self.conn is None:
            raise RuntimeError("Database not connected")

        params: list = []
        scope_where = []
        if guild_id is not None:
            scope_where.append("guild_id=?")
            params.append(int(guild_id))
        if discord_id is not None:
            scope_where.append("requester_id=?")
            params.append(int(discord_id))

        where_sql = ("WHERE " + " AND ".join(scope_where)) if scope_where else ""

        requests_rejected: list[int] = []

        # Optionally reject active requests first.
        if force_clear_active:
            cur = await self.conn.execute(
                f"""
                SELECT request_id FROM cashout_requests
                {where_sql} { 'AND' if where_sql else 'WHERE' } status IN ('pending','approved')
                """,
                tuple(params),
            )
            rows = await cur.fetchall()
            requests_rejected = [int(r[0]) for r in rows]

            if not dry_run and requests_rejected:
                q = ",".join(["?"] * len(requests_rejected))
                await self.conn.execute(
                    f"""
                    UPDATE cashout_requests
                    SET status='rejected',
                        handled_by=?,
                        handled_note=COALESCE(handled_note,'') || CASE WHEN handled_note IS NULL OR handled_note='' THEN '' ELSE ' | ' END || 'reconcile force_clear_active',
                        updated_at=datetime('now')
                    WHERE request_id IN ({q})
                    """,
                    (int(handled_by) if handled_by is not None else None, *requests_rejected),
                )

        # Build user scope from existing tables and cashout requests.
        users: set[int] = set()
        if discord_id is not None:
            users.add(int(discord_id))
        else:
            if guild_id is None:
                for table, col in (("shareholdings", "discord_id"), ("shares_escrow", "discord_id"), ("cashout_requests", "requester_id")):
                    cur = await self.conn.execute(f"SELECT DISTINCT {col} FROM {table}")
                    rows = await cur.fetchall()
                    users.update(int(r[0]) for r in rows if r and r[0] is not None)
            else:
                for table, col in (("shareholdings_by_guild", "discord_id"), ("shares_escrow_by_guild", "discord_id")):
                    cur = await self.conn.execute(f"SELECT DISTINCT {col} FROM {table} WHERE guild_id=?", (int(guild_id),))
                    rows = await cur.fetchall()
                    users.update(int(r[0]) for r in rows if r and r[0] is not None)
                cur = await self.conn.execute(
                    "SELECT DISTINCT requester_id FROM cashout_requests WHERE guild_id=?",
                    (int(guild_id),),
                )
                rows = await cur.fetchall()
                users.update(int(r[0]) for r in rows if r and r[0] is not None)

        results = []
        for uid in sorted(users):
            await self.ensure_member(uid, guild_id=guild_id)

            if guild_id is None:
                cur_hold = await self.conn.execute("SELECT shares FROM shareholdings WHERE discord_id=?", (uid,))
                row_hold = await cur_hold.fetchone()
                total_shares = int(row_hold[0]) if row_hold else 0

                cur_lock = await self.conn.execute("SELECT locked_shares FROM shares_escrow WHERE discord_id=?", (uid,))
                row_lock = await cur_lock.fetchone()
                locked_before = int(row_lock[0]) if row_lock else 0
            else:
                cur_hold = await self.conn.execute(
                    "SELECT shares FROM shareholdings_by_guild WHERE guild_id=? AND discord_id=?",
                    (int(guild_id), int(uid)),
                )
                row_hold = await cur_hold.fetchone()
                total_shares = int(row_hold[0]) if row_hold else 0

                cur_lock = await self.conn.execute(
                    "SELECT locked_shares FROM shares_escrow_by_guild WHERE guild_id=? AND discord_id=?",
                    (int(guild_id), int(uid)),
                )
                row_lock = await cur_lock.fetchone()
                locked_before = int(row_lock[0]) if row_lock else 0

            if force_clear_active:
                expected_locked = 0
            else:
                if guild_id is None:
                    cur_exp = await self.conn.execute(
                        """
                        SELECT COALESCE(SUM(shares),0)
                        FROM cashout_requests
                        WHERE requester_id=? AND status IN ('pending','approved')
                        """,
                        (uid,),
                    )
                else:
                    cur_exp = await self.conn.execute(
                        """
                        SELECT COALESCE(SUM(shares),0)
                        FROM cashout_requests
                        WHERE guild_id=? AND requester_id=? AND status IN ('pending','approved')
                        """,
                        (int(guild_id), int(uid)),
                    )
                row_exp = await cur_exp.fetchone()
                expected_locked = int(row_exp[0]) if row_exp else 0

            locked_after = max(0, min(int(expected_locked), int(total_shares)))
            changed = int(locked_before) != int(locked_after)

            if changed and not dry_run:
                if guild_id is None:
                    await self.conn.execute(
                        "UPDATE shares_escrow SET locked_shares=? WHERE discord_id=?",
                        (int(locked_after), int(uid)),
                    )
                else:
                    await self.conn.execute(
                        "UPDATE shares_escrow_by_guild SET locked_shares=? WHERE guild_id=? AND discord_id=?",
                        (int(locked_after), int(guild_id), int(uid)),
                    )

            results.append(
                {
                    "discord_id": int(uid),
                    "total_shares": int(total_shares),
                    "expected_locked": int(expected_locked),
                    "locked_before": int(locked_before),
                    "locked_after": int(locked_after),
                    "changed": bool(changed),
                }
            )

        if not dry_run:
            await self.conn.commit()

        return {"users": results, "requests_rejected": requests_rejected}
