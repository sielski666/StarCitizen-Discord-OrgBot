import os
import tempfile
import unittest

from services.db import Database


class StockGuardrailsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.NamedTemporaryFile(prefix="orgbot-stock-test-", suffix=".db", delete=False)
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

    async def test_buy_stocks_rejects_non_positive_quantity(self):
        await self.db.add_balance(1, 1_000_000, "seed")
        with self.assertRaises(ValueError):
            await self.db.buy_shares(1, shares_delta=0, cost=100_000)
        with self.assertRaises(ValueError):
            await self.db.buy_shares(1, shares_delta=-5, cost=100_000)

    async def test_buy_stocks_rejects_non_positive_cost(self):
        await self.db.add_balance(1, 1_000_000, "seed")
        with self.assertRaises(ValueError):
            await self.db.buy_shares(1, shares_delta=1, cost=0)
        with self.assertRaises(ValueError):
            await self.db.buy_shares(1, shares_delta=1, cost=-1)

    async def test_lock_stocks_rejects_non_positive_quantity(self):
        await self.db.add_balance(2, 1_000_000, "seed")
        await self.db.buy_shares(2, shares_delta=2, cost=200_000)
        with self.assertRaises(ValueError):
            await self.db.lock_shares(2, 0)
        with self.assertRaises(ValueError):
            await self.db.lock_shares(2, -2)

    async def test_stock_price_config_bounds(self):
        with self.assertRaises(ValueError):
            await self.db.set_stock_market_config(min_price=200_000, max_price=100_000)

    async def test_migration_compat_existing_holdings_still_readable(self):
        await self.db.add_balance(3, 500_000, "seed")
        await self.db.buy_shares(3, shares_delta=3, cost=300_000)
        await self.db.ensure_stock_market_rows()
        total = await self.db.get_shares(3)
        self.assertEqual(total, 3)


if __name__ == "__main__":
    unittest.main()
