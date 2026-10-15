"""mcd-point-fx 核心逻辑测试（零依赖，python -m unittest 直接跑）。"""

import unittest
from datetime import datetime

from mcd_point_fx import ev as ev_mod, rate as rate_mod
from mcd_point_fx.snapshot import load_snapshot

NOW = datetime(2026, 10, 15, 22, 0, 0)


class TestRate(unittest.TestCase):
    def setUp(self):
        snap = load_snapshot()
        self.products = snap["products"]
        self.lottery = snap["lottery"]
        self.board = rate_mod.build_board(self.products, NOW, live_only=True)

    def test_board_only_contains_live(self):
        """默认口径必须只含在售商品，历史活动不得污染牌价。"""
        self.assertTrue(all(q.live for q in self.board.quotes))
        names = [q.name for q in self.board.quotes]
        self.assertNotIn("为随心配五大巨星“应援”1积分兑换活动", names)

    def test_rate_math(self):
        """汇率 = 现金价 / 积分。"""
        q = next(q for q in self.board.quotes if q.spu_id == 17073)  # 6.9元可乐麦炫酷 / 50分
        self.assertAlmostEqual(q.rate, 6.9 / 50, places=6)
        self.assertAlmostEqual(q.points_per_yuan, 50 / 6.9, places=3)

    def test_best_and_worst_ordering(self):
        self.assertGreater(self.board.best.rate, self.board.worst.rate)
        self.assertGreater(self.board.spread, 1.0)

    def test_spread_is_credible(self):
        """在售口径下的极差应该是个合理倍数，不应被历史活动放大到几百倍。"""
        self.assertLess(self.board.spread, 50.0)

    def test_zero_point_products_excluded(self):
        """point=0 的派对/品鉴会是现金售卖，不构成货币对。"""
        ids = {q.spu_id for q in self.board.quotes}
        self.assertNotIn(1830, ids)  # 麦当劳亲子读书会 point=0

    def test_products_without_cash_price_excluded(self):
        """无公开现金价的商品不参与定价。"""
        ids = {q.spu_id for q in self.board.quotes}
        self.assertNotIn(6114, ids)  # 麦麦脆汁鸡两件套，无价

    def test_best_redeem_within_budget(self):
        recs = rate_mod.best_redeem(self.board, 100, live_only=True)
        self.assertTrue(recs)
        for q in recs:
            self.assertLessEqual(q.points, 100)


class TestEV(unittest.TestCase):
    def setUp(self):
        snap = load_snapshot()
        self.board = rate_mod.build_board(snap["products"], NOW, live_only=True)
        self.lottery = snap["lottery"]

    def test_points_prize_converted(self):
        """30 积分奖必须折算成现金价值。"""
        prizes = ev_mod.resolve_prizes(self.lottery, self.board, "median")
        pts_prize = next(p for p in prizes if p.is_points)
        self.assertEqual(pts_prize.points, 30)
        self.assertGreater(pts_prize.value_cny, 0)

    def test_ev_positive(self):
        result, prizes = ev_mod.analyse(self.lottery, self.board, "median")
        self.assertGreater(result.ev_cny, 0)
        self.assertGreater(result.ev_per_point, result.redeem_value_per_point)

    def test_monte_carlo_reproducible(self):
        """固定种子必须可复现。"""
        _, prizes = ev_mod.analyse(self.lottery, self.board, "median")
        a = ev_mod.monte_carlo(prizes, 24, 0.05, draws=500, seed=1024)
        b = ev_mod.monte_carlo(prizes, 24, 0.05, draws=500, seed=1024)
        self.assertEqual(a["total_cny"], b["total_cny"])

    def test_monte_carlo_cost_is_accounted(self):
        """回归：CLI 曾漏传 cost_points/redeem_rate，导致「消耗 0 积分」的失真输出。"""
        _, prizes = ev_mod.analyse(self.lottery, self.board, "median")
        cost_points = 24
        redeem_rate = 0.05
        draws = 1000
        mc = ev_mod.monte_carlo(prizes, cost_points, redeem_rate, draws=draws, seed=1024)
        self.assertEqual(mc["cost_points"], cost_points * draws)
        self.assertGreater(mc["alternative_cny"], 0)
        self.assertAlmostEqual(
            mc["alternative_cny"], round(cost_points * draws * redeem_rate, 2), places=2
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
