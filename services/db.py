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


TREASURY_AUTODEDUCT = _env_flag("TREASURY_AUTODEDUCT", default=True)
STRICT_TREASURY = _env_flag("STRICT_TREASURY", default=False)
SHARE_CASHOUT_AUEC_PER_SHARE = int(os.getenv("SHARE_CASHOUT_AUEC_PER_SHARE", "100000") or "100000")

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS wallets (
  discord_id INTEGER PRIMARY KEY,
  balance INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shareholdings (
  discord_id INTEGER PRIMARY KEY,
  shares INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reputation (
  discord_id INTEGER PRIMARY KEY,
  rep INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shares_escrow (
  discord_id INTEGER PRIMARY KEY,
  locked_shares INTEGER NOT NULL DEFAULT 0
);

-- Treasury is a single-row table (id=1)
CREATE TABLE IF NOT EXISTS treasury (
  id INTEGER PRIMARY KEY CHECK (id = 1),
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

-- Simple transaction log (for balance + shares + rep deltas)
CREATE TABLE IF NOT EXISTS transactions (
  tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
  discord_id INTEGER NOT NULL,
  type TEXT NOT NULL,
  amount INTEGER NOT NULL DEFAULT 0,
  shares_delta INTEGER NOT NULL DEFAULT 0,
  rep_delta INTEGER NOT NULL DEFAULT 0,
  reference TEXT,
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
  notes TEXT
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

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

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
    ):
        await self.conn.execute(
            """
            INSERT INTO ledger_entries(entry_type, amount, from_account, to_account, reference_type, reference_id, notes)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                str(entry_type),
                int(amount),
                str(from_account) if from_account is not None else None,
                str(to_account) if to_account is not None else None,
                str(reference_type) if reference_type is not None else None,
                str(reference_id) if reference_id is not None else None,
                str(notes) if notes is not None else None,
            ),
        )

    async def get_ledger_reconcile(self):
        """Return (current_treasury, ledger_treasury, drift, baseline_at)."""
        current = await self.get_treasury()

        cur = await self.conn.execute(
            """
            SELECT timestamp, amount
            FROM ledger_entries
            WHERE entry_type='treasury_set'
            ORDER BY entry_id DESC
            LIMIT 1
            """
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
                WHERE timestamp > ? AND entry_type != 'treasury_set'
                """,
                (baseline_at,),
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
                WHERE entry_type != 'treasury_set'
                """
            )
            delta = await dcur.fetchone()
            ledger_treasury = int(delta[0]) if delta and delta[0] is not None else 0

        drift = int(current) - int(ledger_treasury)
        return int(current), int(ledger_treasury), int(drift), baseline_at

    async def ensure_member(self, discord_id: int):
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
        await self.conn.commit()

    # =========================
    # BALANCE / SHARES / REP
    # =========================
    async def get_balance(self, discord_id: int) -> int:
        await self.ensure_member(discord_id)
        cur = await self.conn.execute("SELECT balance FROM wallets WHERE discord_id=?", (int(discord_id),))
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def add_balance(self, discord_id: int, amount: int, tx_type: str, reference: str | None = None):
        await self.ensure_member(discord_id)
        await self._begin()
        try:
            await self.conn.execute(
                "UPDATE wallets SET balance = balance + ? WHERE discord_id=?",
                (int(amount), int(discord_id)),
            )
            await self.conn.execute(
                "INSERT INTO transactions(discord_id, type, amount, shares_delta, rep_delta, reference) VALUES(?,?,?,?,?,?)",
                (int(discord_id), str(tx_type), int(amount), 0, 0, reference),
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
                )
            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def get_shares(self, discord_id: int) -> int:
        await self.ensure_member(discord_id)
        cur = await self.conn.execute("SELECT shares FROM shareholdings WHERE discord_id=?", (int(discord_id),))
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get_shares_locked(self, discord_id: int) -> int:
        await self.ensure_member(discord_id)
        cur = await self.conn.execute("SELECT locked_shares FROM shares_escrow WHERE discord_id=?", (int(discord_id),))
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get_shares_available(self, discord_id: int) -> int:
        total = await self.get_shares(discord_id)
        locked = await self.get_shares_locked(discord_id)
        return max(0, int(total) - int(locked))

    async def buy_shares(self, discord_id: int, shares_delta: int, cost: int, reference: str | None = None):
        await self.ensure_member(discord_id)
        bal = await self.get_balance(discord_id)
        if bal < int(cost):
            raise ValueError("Not enough Org Credits to buy shares.")
        await self._begin()
        try:
            await self.conn.execute(
                "UPDATE wallets SET balance = balance - ? WHERE discord_id=?",
                (int(cost), int(discord_id)),
            )
            await self.conn.execute(
                "UPDATE shareholdings SET shares = shares + ? WHERE discord_id=?",
                (int(shares_delta), int(discord_id)),
            )
            await self.conn.execute(
                "INSERT INTO transactions(discord_id, type, amount, shares_delta, rep_delta, reference) VALUES(?,?,?,?,?,?)",
                (int(discord_id), "buy_shares", -int(cost), int(shares_delta), 0, reference),
            )
            await self.add_ledger_entry(
                entry_type="shares_bought",
                amount=int(cost),
                from_account=f"wallet:{int(discord_id)}",
                to_account="treasury",
                reference_type="shares",
                reference_id=str(reference or ""),
                notes=f"Bought {int(shares_delta)} shares",
            )
            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def get_rep(self, discord_id: int) -> int:
        await self.ensure_member(discord_id)
        cur = await self.conn.execute("SELECT rep FROM reputation WHERE discord_id=?", (int(discord_id),))
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def add_rep(self, discord_id: int, amount: int, reference: str | None = None):
        await self.ensure_member(discord_id)
        await self._begin()
        try:
            await self.conn.execute(
                "UPDATE reputation SET rep = rep + ? WHERE discord_id=?",
                (int(amount), int(discord_id)),
            )
            await self.conn.execute(
                "INSERT INTO transactions(discord_id, type, amount, shares_delta, rep_delta, reference) VALUES(?,?,?,?,?,?)",
                (int(discord_id), "rep", 0, 0, int(amount), reference),
            )
            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def get_level(self, discord_id: int, per_level: int = 100) -> int:
        rep = await self.get_rep(discord_id)
        return int(rep) // int(per_level)

    # =========================
    # TREASURY
    # =========================
    async def get_treasury(self) -> int:
        cur = await self.conn.execute("SELECT amount FROM treasury WHERE id=1")
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get_treasury_meta(self):
        cur = await self.conn.execute("SELECT amount, updated_by, updated_at FROM treasury WHERE id=1")
        row = await cur.fetchone()
        if not row:
            return 0, None, None
        amount = int(row[0]) if row[0] is not None else 0
        updated_by = int(row[1]) if row[1] is not None else None
        updated_at = str(row[2]) if row[2] is not None else None
        return amount, updated_by, updated_at

    async def set_treasury(self, amount: int, updated_by: int | None = None):
        current = await self.get_treasury()
        await self._begin()
        try:
            await self.conn.execute(
                "UPDATE treasury SET amount=?, updated_by=?, updated_at=datetime('now') WHERE id=1",
                (int(amount), int(updated_by) if updated_by is not None else None),
            )
            await self.add_ledger_entry(
                entry_type="treasury_set",
                amount=int(amount),
                from_account=f"actor:{int(updated_by)}" if updated_by is not None else None,
                to_account="treasury",
                reference_type="treasury",
                reference_id="manual-set",
                notes=f"Manual set from {int(current)} to {int(amount)}",
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
    async def get_reserved_job_escrow(self) -> int:
        cur = await self.conn.execute(
            "SELECT COALESCE(SUM(escrow_amount), 0) FROM jobs WHERE escrow_status='reserved'"
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
    ) -> int:
        reward_i = int(reward)

        await self._begin()
        try:
            current_treasury = await self.get_treasury()
            reserved = await self.get_reserved_job_escrow()
            available = int(current_treasury) - int(reserved)
            if available < reward_i:
                raise ValueError(
                    f"Insufficient available treasury for this job. Available: {available:,} aUEC, required: {reward_i:,} aUEC."
                )

            cur = await self.conn.execute(
                """
                INSERT INTO jobs(channel_id, message_id, title, description, reward, status, created_by, escrow_amount, escrow_status, funded, category, template_id)
                VALUES(?,?,?,?,?,'open',?,?, 'reserved', 1, ?, ?)
                """,
                (
                    int(channel_id),
                    int(message_id),
                    str(title),
                    str(description),
                    reward_i,
                    int(created_by),
                    reward_i,
                    (str(category).strip() if category else None),
                    (int(template_id) if template_id is not None else None),
                ),
            )
            job_id = int(cur.lastrowid)

            await self.add_ledger_entry(
                entry_type="escrow_reserved",
                amount=reward_i,
                from_account="treasury_available",
                to_account=f"job_escrow:{job_id}",
                reference_type="job",
                reference_id=str(job_id),
                notes="Reserved treasury for new job",
            )

            await self._commit()
            return job_id
        except Exception:
            await self._rollback()
            raise

    async def get_job(self, job_id: int):
        cur = await self.conn.execute(
            """
            SELECT job_id, channel_id, message_id, title, description, reward, status,
                   created_by, claimed_by, thread_id, created_at, updated_at
            FROM jobs WHERE job_id=?
            """,
            (int(job_id),),
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

    async def add_event_attendee(self, job_id: int, discord_id: int) -> bool:
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO job_event_attendance(job_id, discord_id, status) VALUES(?,?, 'joined')",
            (int(job_id), int(discord_id)),
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def remove_event_attendee(self, job_id: int, discord_id: int) -> bool:
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

    async def mark_paid(self, job_id: int) -> bool:
        await self._begin()
        try:
            cur = await self.conn.execute(
                "SELECT status, reward, escrow_amount, escrow_status FROM jobs WHERE job_id=?",
                (int(job_id),),
            )
            row = await cur.fetchone()
            if not row:
                await self._rollback()
                return False

            status, reward, escrow_amount, escrow_status = str(row[0]), int(row[1]), int(row[2] or 0), str(row[3] or "none")
            if status != "completed":
                await self._rollback()
                return False

            payout_amount = int(escrow_amount or reward)
            if TREASURY_AUTODEDUCT and payout_amount > 0:
                tcur = await self.conn.execute("SELECT amount FROM treasury WHERE id=1")
                trow = await tcur.fetchone()
                treasury_amount = int(trow[0]) if trow else 0
                if treasury_amount < payout_amount:
                    raise ValueError("Treasury too low for this payout.")
                await self.conn.execute(
                    "UPDATE treasury SET amount = amount - ?, updated_by=NULL, updated_at=datetime('now') WHERE id=1",
                    (int(payout_amount),),
                )

            await self.conn.execute(
                """
                UPDATE jobs
                SET status='paid', escrow_status='released', updated_at=datetime('now')
                WHERE job_id=? AND status='completed'
                """,
                (int(job_id),),
            )

            if escrow_status == "reserved" and payout_amount > 0:
                await self.add_ledger_entry(
                    entry_type="escrow_released",
                    amount=int(payout_amount),
                    from_account=f"job_escrow:{int(job_id)}",
                    to_account="settled",
                    reference_type="job",
                    reference_id=str(int(job_id)),
                    notes="Released reserved job escrow on confirm",
                )

            await self._commit()
            return True
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
    async def lock_shares(self, discord_id: int, shares: int):
        await self.ensure_member(discord_id)
        available = await self.get_shares_available(discord_id)
        if available < int(shares):
            raise ValueError("Not enough available shares to lock.")
        await self.conn.execute(
            "UPDATE shares_escrow SET locked_shares = locked_shares + ? WHERE discord_id=?",
            (int(shares), int(discord_id)),
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

    async def unlock_shares(self, discord_id: int, shares: int):
        await self.ensure_member(discord_id)
        locked = await self.get_shares_locked(discord_id)
        to_unlock = min(int(locked), int(shares))
        await self.conn.execute(
            "UPDATE shares_escrow SET locked_shares = locked_shares - ? WHERE discord_id=?",
            (int(to_unlock), int(discord_id)),
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
    ):
        cur = await self.conn.execute(
            "SELECT requester_id, shares, status FROM cashout_requests WHERE request_id=?",
            (int(request_id),),
        )
        row = await cur.fetchone()
        if not row:
            raise ValueError("Cash-out request not found.")
        requester_id, shares, status = int(row[0]), int(row[1]), str(row[2])

        if status != "approved":
            raise ValueError(f"Request must be approved first (status: {status}).")

        lcur = await self.conn.execute(
            "SELECT locked_shares FROM shares_escrow WHERE discord_id=?",
            (int(requester_id),),
        )
        lrow = await lcur.fetchone()
        locked = int(lrow[0]) if lrow else 0
        if locked < int(shares):
            raise ValueError("Not enough locked shares to finalize this cash-out.")

        hcur = await self.conn.execute(
            "SELECT shares FROM shareholdings WHERE discord_id=?",
            (int(requester_id),),
        )
        hrow = await hcur.fetchone()
        holding = int(hrow[0]) if hrow else 0
        if holding < int(shares):
            raise ValueError("Member does not have enough shares to sell.")

        if TREASURY_AUTODEDUCT and STRICT_TREASURY:
            tcur = await self.conn.execute("SELECT amount FROM treasury WHERE id=1")
            trow = await tcur.fetchone()
            treasury_amount = int(trow[0]) if trow else 0
            if treasury_amount < int(payout_amount):
                raise ValueError("Treasury too low for this payout.")

        await self._begin()
        try:
            if TREASURY_AUTODEDUCT:
                await self.conn.execute(
                    "UPDATE treasury SET amount = amount - ?, updated_by=?, updated_at=datetime('now') WHERE id=1",
                    (int(payout_amount), int(handled_by) if handled_by is not None else None),
                )

            await self.conn.execute(
                "UPDATE shares_escrow SET locked_shares = locked_shares - ? WHERE discord_id=?",
                (int(shares), int(requester_id)),
            )
            await self.add_ledger_entry(
                entry_type="escrow_released",
                amount=int(shares),
                from_account=f"escrow:{int(requester_id)}",
                to_account="sold",
                reference_type="cashout",
                reference_id=str(int(request_id)),
                notes="Escrow released on paid cashout",
            )
            await self.conn.execute(
                "UPDATE shareholdings SET shares = shares - ? WHERE discord_id=?",
                (int(shares), int(requester_id)),
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
            )

            await self.add_ledger_entry(
                entry_type="cashout_paid",
                amount=int(payout_amount),
                from_account="treasury" if TREASURY_AUTODEDUCT else "external",
                to_account=f"wallet:{int(requester_id)}",
                reference_type="cashout",
                reference_id=str(int(request_id)),
                notes="Cashout finalized as paid",
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

    async def set_cashout_thread(self, request_id: int, thread_id: int):
        await self.conn.execute(
            "UPDATE cashout_requests SET thread_id=?, updated_at=datetime('now') WHERE request_id=?",
            (int(thread_id), int(request_id)),
        )
        await self.conn.commit()

    async def set_cashout_status(self, request_id: int, status: str, handled_by: int | None = None, note: str | None = None):
        status_str = str(status)

        await self._begin()
        try:
            await self.conn.execute(
                "UPDATE cashout_requests SET status=?, handled_by=?, handled_note=?, updated_at=datetime('now') WHERE request_id=?",
                (status_str, int(handled_by) if handled_by is not None else None, note, int(request_id)),
            )

            if status_str == "approved":
                cur = await self.conn.execute(
                    "SELECT requester_id, shares FROM cashout_requests WHERE request_id=?",
                    (int(request_id),),
                )
                row = await cur.fetchone()
                if row:
                    requester_id, shares = int(row[0]), int(row[1])
                    est_amount = int(shares) * int(SHARE_CASHOUT_AUEC_PER_SHARE)
                    await self.add_ledger_entry(
                        entry_type="cashout_approved",
                        amount=int(est_amount),
                        from_account="treasury",
                        to_account=f"wallet:{requester_id}",
                        reference_type="cashout",
                        reference_id=str(int(request_id)),
                        notes="Cashout approved (estimated payout)",
                    )

            await self._commit()
        except Exception:
            await self._rollback()
            raise

    async def get_cashout_request(self, request_id: int):
        cur = await self.conn.execute(
            "SELECT request_id, guild_id, channel_id, message_id, requester_id, shares, status, created_at, updated_at, thread_id, handled_by, handled_note "
            "FROM cashout_requests WHERE request_id=?",
            (int(request_id),),
        )
        return await cur.fetchone()

    # =========================
    # FINANCE DASHBOARD HELPERS
    # =========================
    async def list_cashout_requests(self, statuses: list[str], limit: int = 25):
        """
        Returns rows of cashout_requests, newest first.
        Row shape matches get_cashout_request plus created/updated fields etc.
        """
        statuses = [str(s) for s in (statuses or []) if str(s).strip()]
        if not statuses:
            statuses = ["pending"]

        q_marks = ",".join(["?"] * len(statuses))
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
        return await cur.fetchall()

    async def count_cashout_requests(self, statuses: list[str]) -> int:
        statuses = [str(s) for s in (statuses or []) if str(s).strip()]
        if not statuses:
            statuses = ["pending"]
        q_marks = ",".join(["?"] * len(statuses))
        cur = await self.conn.execute(
            f"SELECT COUNT(*) FROM cashout_requests WHERE status IN ({q_marks})",
            (*statuses,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def list_transactions(self, types: list[str] | None = None, limit: int = 25, discord_id: int | None = None):
        """
        Returns rows of transactions newest first.
        """
        where = []
        params: list = []

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
    ):
        """
        Rebuild shares_escrow.locked_shares from active cashout requests.

        Active requests: pending, approved.
        If force_clear_active=True, active requests in scope are marked rejected and expected locks become 0.
        """
        if self.conn is None:
            raise RuntimeError("Database not connected")

        params: list = []
        scope_where = ""
        if discord_id is not None:
            scope_where = "WHERE requester_id=?"
            params.append(int(discord_id))

        requests_rejected: list[int] = []

        # Optionally reject active requests first.
        if force_clear_active:
            cur = await self.conn.execute(
                f"""
                SELECT request_id FROM cashout_requests
                {scope_where} { 'AND' if scope_where else 'WHERE' } status IN ('pending','approved')
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
            for table, col in (("shareholdings", "discord_id"), ("shares_escrow", "discord_id"), ("cashout_requests", "requester_id")):
                cur = await self.conn.execute(f"SELECT DISTINCT {col} FROM {table}")
                rows = await cur.fetchall()
                users.update(int(r[0]) for r in rows if r and r[0] is not None)

        results = []
        for uid in sorted(users):
            await self.ensure_member(uid)

            cur_hold = await self.conn.execute("SELECT shares FROM shareholdings WHERE discord_id=?", (uid,))
            row_hold = await cur_hold.fetchone()
            total_shares = int(row_hold[0]) if row_hold else 0

            cur_lock = await self.conn.execute("SELECT locked_shares FROM shares_escrow WHERE discord_id=?", (uid,))
            row_lock = await cur_lock.fetchone()
            locked_before = int(row_lock[0]) if row_lock else 0

            if force_clear_active:
                expected_locked = 0
            else:
                cur_exp = await self.conn.execute(
                    """
                    SELECT COALESCE(SUM(shares),0)
                    FROM cashout_requests
                    WHERE requester_id=? AND status IN ('pending','approved')
                    """,
                    (uid,),
                )
                row_exp = await cur_exp.fetchone()
                expected_locked = int(row_exp[0]) if row_exp else 0

            locked_after = max(0, min(int(expected_locked), int(total_shares)))
            changed = int(locked_before) != int(locked_after)

            if changed and not dry_run:
                await self.conn.execute(
                    "UPDATE shares_escrow SET locked_shares=? WHERE discord_id=?",
                    (int(locked_after), int(uid)),
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
