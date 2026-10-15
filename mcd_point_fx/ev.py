"""抽奖 EV 引擎：把积分抽奖当成一张可以定价的期权。

官方未公布各奖品的中奖概率，因此本模块默认采用**等概率假设**，
并额外给出敏感性分析：概率要偏到什么程度，抽奖才会输给直接兑换。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .rate import Board


@dataclass
class Prize:
    name: str
    value_cny: Optional[float]
    basis: str
    is_points: bool = False
    points: int = 0


@dataclass
class EVResult:
    cost_points: int
    ev_cny: float
    ev_per_point: float
    redeem_value_per_point: float
    redeem_value_total: float
    verdict: str
    edge_ratio: float
    breakeven_prob_factor: float


def resolve_prizes(lottery: Dict[str, Any], board: Board, rate_strategy: str = "median") -> List[Prize]:
    """把奖池解析成带现金价值的奖品列表。

    其中「30积分」这类积分奖，按给定汇率策略折成现金。
    """
    if rate_strategy == "best":
        rate = board.best.rate if board.best else 0.0
    elif rate_strategy == "worst":
        rate = board.worst.rate if board.worst else 0.0
    else:
        rate = board.median_rate()

    prizes: List[Prize] = []
    for raw in lottery.get("prizes", []):
        name = raw.get("name", "")
        value = raw.get("value_cny")
        basis = raw.get("basis", "")
        is_points = "积分" in name and value is None
        pts = 0
        if is_points:
            digits = "".join(ch for ch in name if ch.isdigit())
            pts = int(digits) if digits else 0
            value = round(pts * rate, 2)
            basis = f"积分奖，按{rate_strategy}汇率 {rate:.4f} 元/分 折算"
        prizes.append(Prize(name=name, value_cny=float(value or 0), basis=basis, is_points=is_points, points=pts))
    return prizes


def expected_value(prizes: List[Prize], weights: Optional[List[float]] = None) -> float:
    """等概率（或给定权重）下的期望现金价值。"""
    if not prizes:
        return 0.0
    if weights is None:
        weights = [1.0] * len(prizes)
    total_w = sum(weights) or 1.0
    return sum((p.value_cny or 0) * w for p, w in zip(prizes, weights)) / total_w


def analyse(lottery: Dict[str, Any], board: Board, rate_strategy: str = "median") -> Tuple[EVResult, List[Prize]]:
    cost = int(lottery.get("drawPoint", 0) or 0)
    prizes = resolve_prizes(lottery, board, rate_strategy)
    ev = expected_value(prizes)

    if rate_strategy == "best":
        rpp = board.best.rate if board.best else 0.0
    elif rate_strategy == "worst":
        rpp = board.worst.rate if board.worst else 0.0
    else:
        rpp = board.median_rate()

    redeem_total = round(cost * rpp, 2)
    ev_per_point = ev / cost if cost else 0.0
    edge = ev_per_point / rpp if rpp else 0.0

    if ev_per_point > rpp:
        verdict = f"抽奖更划算（每积分回报是直接兑换的 {edge:.2f} 倍）"
    else:
        verdict = f"直接兑换更划算（抽奖每积分回报仅为其 {edge:.2f} 倍）"

    # 敏感性：若真实概率全部按「奖品价值越低越可能中」倾斜，
    # 需要把高价值奖品的概率压低到什么倍数，抽奖才不再划算。
    breakeven = rpp / ev_per_point if ev_per_point else float("inf")

    return (
        EVResult(
            cost_points=cost,
            ev_cny=round(ev, 2),
            ev_per_point=round(ev_per_point, 4),
            redeem_value_per_point=round(rpp, 4),
            redeem_value_total=redeem_total,
            verdict=verdict,
            edge_ratio=round(edge, 2),
            breakeven_prob_factor=round(breakeven, 3),
        ),
        prizes,
    )


def monte_carlo(
    prizes: List[Prize],
    cost_points: int = 0,
    redeem_rate: float = 0.0,
    draws: int = 10000,
    seed: int = 1024,
) -> Dict[str, float]:
    """模拟连续抽奖 n 次，并与「直接兑换」做同成本对比。"""
    rng = random.Random(seed)
    values = [p.value_cny or 0 for p in prizes]
    if not values:
        return {}
    total = 0.0
    best_hit = 0.0
    for _ in range(draws):
        v = rng.choice(values)
        total += v
        best_hit = max(best_hit, v)

    spent = cost_points * draws
    alt = spent * redeem_rate
    return {
        "draws": draws,
        "cost_points": spent,
        "total_cny": round(total, 2),
        "avg_per_draw": round(total / draws, 2),
        "best_single": round(best_hit, 2),
        "alternative_cny": round(alt, 2),
        "net_edge_cny": round(total - alt, 2),
    }


def render_ev(result: EVResult, prizes: List[Prize], lottery: Dict[str, Any], mc: Dict[str, float]) -> str:
    lines: List[str] = []
    lines.append("")
    lines.append("  LOTTERY EV DESK".center(88))
    lines.append(f"  {lottery.get('activityName', '')} · 单次消耗 {result.cost_points} 积分".center(88))
    lines.append("")
    lines.append(f"  {'奖品':<22} {'估值(元)':>10}  取值依据")
    lines.append("  " + "-" * 84)
    for p in prizes:
        lines.append(f"  {p.name[:20]:<22} {p.value_cny:>10.2f}  {p.basis[:46]}")
    lines.append("  " + "-" * 84)
    lines.append("")
    lines.append(f"  期望价值 EV        {result.ev_cny:>8.2f} 元 / 次")
    lines.append(f"  每积分回报(抽奖)   {result.ev_per_point:>8.4f} 元/分")
    lines.append(f"  每积分回报(兑换)   {result.redeem_value_per_point:>8.4f} 元/分")
    lines.append(f"  {result.cost_points} 积分兑换等价  {result.redeem_value_total:>8.2f} 元")
    lines.append("")
    lines.append(f"  >>> 结论：{result.verdict}")
    lines.append(
        f"  >>> 安全边际：抽奖的每积分回报要跌到当前的 "
        f"{result.breakeven_prob_factor * 100:.1f}% 以下，直接兑换才会反超"
    )
    lines.append("  >>> 前提：官方未公布中奖概率，以上按等概率假设计算")
    if mc:
        lines.append("  蒙特卡洛同成本对比：")
        lines.append(f"    抽 {int(mc['draws'])} 次，共消耗 {int(mc['cost_points'])} 积分")
        lines.append(f"    -> 抽奖所得   {mc['total_cny']:>10.2f} 元")
        lines.append(f"    -> 直接兑换   {mc['alternative_cny']:>10.2f} 元")
        lines.append(f"    -> 净  差     {mc['net_edge_cny']:>10.2f} 元")
    lines.append("")
    return "\n".join(lines)
