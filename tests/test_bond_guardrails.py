import os
import tempfile
import unittest

from services.db import Database


class BondGuardrailsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.NamedTemporaryFile(prefix="orgbot-test-", suffix=".db", delete=False)
        self.tmp.close()
        self.db = Database(path=self.tmp.name)
        await self.db.connect()

    async def asyncTearDown(self):
        try:
            await self.db.close()
        except Exception:
            pass
        try:
            os.unlink(self.tmp.name)
        except Exception:
            pass

    async def test_partial_payout_creates_bond_without_overdraw(self):
        await self.db.set_treasury(300)

        job_id = await self.db.create_job(
            channel_id=1,
            message_id=1,
            title="Test Job",
            description="partial payout",
            reward=500,
            created_by=42,
        )
        self.assertTrue(await self.db.claim_job(job_id, claimed_by=99))
        self.assertTrue(await self.db.complete_job(job_id))

        result = await self.db.settle_job_payout(job_id, [(99, 500)], confirmed_by=42)

        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("pay_now"), 300)
        self.assertEqual(result.get("bond_amount"), 200)

        treasury = await self.db.get_treasury()
        self.assertEqual(treasury, 0)

        pending = await self.db.list_pending_bonds(user_id=99)
        self.assertEqual(len(pending), 1)
        self.assertEqual(int(pending[0][2]), 200)

    async def test_redeem_bonds_fifo_and_no_double_redeem(self):
        b1 = await self.db.create_payout_bond(user_id=111, amount_owed=100, job_reference="job:1")
        b2 = await self.db.create_payout_bond(user_id=111, amount_owed=200, job_reference="job:2")
        self.assertGreater(b2, b1)

        await self.db.set_treasury(150)

        r1 = await self.db.redeem_bonds_for_user(user_id=111, redeemed_by=999)
        self.assertEqual(r1.get("redeemed_count"), 1)
        self.assertEqual(r1.get("paid_total"), 100)
        self.assertEqual(r1.get("treasury_after"), 50)

        pending_after_first = await self.db.list_pending_bonds(user_id=111)
        self.assertEqual(len(pending_after_first), 1)
        self.assertEqual(int(pending_after_first[0][2]), 200)

        # Second redemption should not double-redeem or overdraw with only 50 treasury.
        r2 = await self.db.redeem_bonds_for_user(user_id=111, redeemed_by=999)
        self.assertEqual(r2.get("redeemed_count"), 0)
        self.assertEqual(r2.get("paid_total"), 0)
        self.assertEqual(r2.get("treasury_after"), 50)

    async def test_negative_bond_rejected(self):
        with self.assertRaises(ValueError):
            await self.db.create_payout_bond(user_id=123, amount_owed=-10)


if __name__ == "__main__":
    unittest.main()
