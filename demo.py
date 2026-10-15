#!/usr/bin/env python3
"""mcd-point-fx 一键演示。

零第三方依赖、零 Token，**直接跑**：

    python demo.py

想看实时数据（需先在 https://open.mcd.cn/mcp 申请 Token）：

    export MCD_MCP_TOKEN=你的Token
    python demo.py --live
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from mcd_point_fx import ev as ev_mod, mcp_live, rate as rate_mod
from mcd_point_fx.snapshot import load_snapshot, lottery as snap_lottery, products as snap_products

BANNER = r"""
  __  __  ___ ___    ___  ___  _  _  _____        __ _______  __
 |  \/  |/ __|   \  | _ \/ _ \| \| ||_ _\ \      / /| __\ \/ /
 | |\/| | (_ | |) | |  _/ (_) | .` | | | \ \ /\ / / | _| \>  <
 |_|  |_|\___|___/  |_|  \___/|_|\_||___| \ V  V /  |___|/_/\_\

        麦当劳积分外汇交易所  ·  POINT / CNY
"""


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--live", action="store_true", help="从 MCP 实时拉取（需 MCD_MCP_TOKEN）")
    ap.add_argument("--draws", type=int, default=10000, help="蒙特卡洛模拟次数")
    args = ap.parse_args()

    print(BANNER)

    if args.live:
        source = "LIVE  ·  mcp.mcd.cn"
        try:
            prods = mcp_live.fetch_products()
            lot = mcp_live.fetch_lottery()
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] 实时拉取失败，回退内置快照：{exc}\n")
            snap = load_snapshot()
            prods, lot = snap_products(snap), snap_lottery(snap)
            source = "SNAPSHOT  ·  data/snapshot.json"
    else:
        snap = load_snapshot()
        prods, lot = snap_products(snap), snap_lottery(snap)
        source = "SNAPSHOT  ·  data/snapshot.json（无需 Token）"

    print(f"  数据源：{source}")
    print(f"  时间  ：{datetime.now():%Y-%m-%d %H:%M:%S}\n")

    board = rate_mod.build_board(prods, datetime.now())
    print(rate_mod.render_board(board))

    b, w = board.best, board.worst
    if b and w:
        print("  一句话结论：")
        print(f"    同样是 100 积分，换「{b.name}」值 "
              f"{100 * b.rate:.2f} 元，换「{w.name}」只值 {100 * w.rate:.2f} 元。")
        print(f"    汇率极差 {board.spread:.2f} 倍 —— 选错商品，等于白扔 "
              f"{(1 - w.rate / b.rate) * 100:.0f}% 的积分价值。\n")

    if lot:
        result, prizes = ev_mod.analyse(lot, board, "median")
        mc = ev_mod.monte_carlo(prizes, result.cost_points, result.redeem_value_per_point, draws=args.draws)
        print(ev_mod.render_ev(result, prizes, lot, mc))
    else:
        print("  [skip] 无抽奖活动数据\n")

    print("  下一步：")
    print("    python -m mcd_point_fx rate            # 只看牌价表")
    print("    python -m mcd_point_fx ev              # 只看抽奖 EV")
    print("    python -m mcd_point_fx best --points 500   # 我有 500 分，换什么最值")
    print("    python demo.py --live                  # 接真实 MCP（需设置 MCD_MCP_TOKEN）\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
