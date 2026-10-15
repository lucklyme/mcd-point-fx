"""命令行入口：rate / ev / best。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from . import ev as ev_mod
from . import mcp_live, rate as rate_mod
from .snapshot import load_snapshot, lottery as snap_lottery, products as snap_products


def _load(live: bool):
    """返回 (products, lottery, source_label)。"""
    if live:
        try:
            prods = mcp_live.fetch_products()
            lot = mcp_live.fetch_lottery()
            return prods, lot, "LIVE (MCP mcp.mcd.cn)"
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] 实时拉取失败，回退到内置快照：{exc}", file=sys.stderr)
    snap = load_snapshot()
    return snap_products(snap), snap_lottery(snap), "SNAPSHOT (data/snapshot.json)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="mcd-point-fx",
        description="麦当劳积分外汇交易所：汇率牌价 + 抽奖 EV",
    )
    ap.add_argument("command", choices=["rate", "ev", "best", "all"], nargs="?", default="all")
    ap.add_argument("--live", action="store_true", help="从 MCP 实时拉取（需 MCD_MCP_TOKEN）")
    ap.add_argument("--points", type=int, default=0, help="best 命令：你的积分余额")
    ap.add_argument("--strategy", choices=["best", "median", "worst"], default="median", help="折算汇率策略")
    ap.add_argument("--draws", type=int, default=10000, help="蒙特卡洛模拟次数")
    ap.add_argument("--history", action="store_true", help="含已下架商品")
    args = ap.parse_args(argv)

    prods, lot, source = _load(args.live)
    board = rate_mod.build_board(prods, datetime.now(), live_only=not args.history)

    scope = "全部商品（含已下架）" if args.history else "当前在售商品"
    print(f"\n数据源：{source}")
    print(f"统计范围：{scope}\n")

    if args.command in ("rate", "all"):
        print(rate_mod.render_board(board))

    if args.command in ("ev", "all"):
        if not lot:
            print("  [skip] 未获取到抽奖活动信息\n")
        else:
            result, prizes = ev_mod.analyse(lot, board, args.strategy)
            mc = ev_mod.monte_carlo(prizes, draws=args.draws)
            print(ev_mod.render_ev(result, prizes, lot, mc))

    if args.command == "best":
        if not args.points:
            print("  用法：python -m mcd_point_fx best --points 500\n")
            return 1
        recs = rate_mod.best_redeem(board, args.points, live_only=not args.history)
        print(f"\n  你有 {args.points} 积分，按汇率从优到劣的可兑换选项：\n")
        if not recs:
            print("    （当前无在售商品可用这些积分兑换）\n")
        for i, q in enumerate(recs[:10], 1):
            print(f"   {i:>2}. {q.name[:34]:<36} {q.points:>5} 分  值 {q.cash_cny:>6.2f} 元  ({q.rate:.4f} 元/分)")
        print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
