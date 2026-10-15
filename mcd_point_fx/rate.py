"""汇率引擎：把积分商城的每一个 SKU 当成 POINT/CNY 货币对来定价。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .snapshot import is_live, parse_dt

# 优先从名称里匹配“18.8元2份麦辣鸡翅”这类带现金价的商品
_RE_YUAN = re.compile(r"(\d+(?:\.\d+)?)\s*元")
# 兜底：匹配“只要13.9起”这种不带“元”的写法
_RE_QI = re.compile(r"(?:只要|仅需|低至)\s*(\d+(?:\.\d+)?)\s*起")


@dataclass
class Quote:
    """一个货币对的牌价。"""

    spu_id: int
    name: str
    points: int
    cash_cny: float
    rate: float  # 元 / 积分
    cat_name: str
    live: bool
    down_time: str
    status_text: str
    note: str = ""

    @property
    def points_per_yuan(self) -> float:
        """反牌价：换 1 块钱需要多少积分。"""
        return 1.0 / self.rate if self.rate else float("inf")


@dataclass
class Board:
    """汇率牌价表。"""

    quotes: List[Quote] = field(default_factory=list)
    generated_at: str = ""

    def sorted_by_rate(self, desc: bool = True) -> List[Quote]:
        return sorted(self.quotes, key=lambda q: q.rate, reverse=desc)

    @property
    def best(self) -> Optional[Quote]:
        return self.sorted_by_rate()[0] if self.quotes else None

    @property
    def worst(self) -> Optional[Quote]:
        return self.sorted_by_rate(desc=False)[0] if self.quotes else None

    @property
    def spread(self) -> float:
        """最优汇率与最差汇率的倍数差 —— 这是整个项目的核心指标。"""
        b, w = self.best, self.worst
        if not b or not w or w.rate <= 0:
            return 0.0
        return b.rate / w.rate

    def median_rate(self) -> float:
        if not self.quotes:
            return 0.0
        rs = sorted(q.rate for q in self.quotes)
        mid = len(rs) // 2
        if len(rs) % 2 == 1:
            return rs[mid]
        return (rs[mid - 1] + rs[mid]) / 2


def extract_cash(product: Dict[str, Any]) -> tuple[Optional[float], str]:
    """从商品名/卖点里提取现金价值，返回 (现金价, 取值依据)。"""
    # 官方 price 字段优先（部分类目如派对是现金售卖）
    price = product.get("price")
    try:
        if price not in (None, "", 0, "0"):
            v = float(price)
            if v > 0:
                return v, "官方 price 字段"
    except (TypeError, ValueError):
        pass

    name_text = product.get("name") or product.get("spuName") or ""
    for text in (name_text, product.get("selling", "")):
        m = _RE_YUAN.search(text or "")
        if m:
            return float(m.group(1)), "商品名称标注价"
        m = _RE_QI.search(text or "")
        if m:
            return float(m.group(1)), "商品名称活动价"

    # 最后兜底：数据里自带的公开市场参考价（如罗技键鼠套装）
    ref = product.get("market_ref_cny")
    if ref:
        return float(ref), str(product.get("market_ref_note", "公开市场参考价"))

    return None, ""


def build_board(
    raw_products: List[Dict[str, Any]],
    now: datetime | None = None,
    live_only: bool = True,
) -> Board:
    """构建牌价表。

    默认只统计**当前在售**商品：已下架的历史活动（如 1 积分限时兑换）
    会严重扭曲最优/最差牌价，不能与在售商品同台比较。
    """
    now = now or datetime.now()
    board = Board(generated_at=now.strftime("%Y-%m-%d %H:%M:%S"))

    for p in raw_products:
        if live_only and not is_live(p, now):
            continue
        try:
            points = int(float(p.get("point", 0) or 0))
        except (TypeError, ValueError):
            continue
        if points <= 0:
            continue  # point=0 的派对/品鉴会是现金售卖，不构成货币对

        cash, basis = extract_cash(p)
        if cash is None or cash <= 0:
            continue  # 无公开现金价，无法定价

        status = p.get("status")
        # MCP 实时返回 spuName，快照里为 name，两者都要兼容
        name = p.get("name") or p.get("spuName") or ""
        selling = p.get("selling") or ""
        board.quotes.append(
            Quote(
                spu_id=int(p.get("spuId", 0)),
                name=name,
                points=points,
                cash_cny=round(cash, 2),
                rate=round(cash / points, 6),
                cat_name=p.get("catName", "") or selling[:8],
                live=is_live(p, now),
                down_time=p.get("downTime", ""),
                status_text={1: "仓库中", 2: "上架", 3: "售罄", 4: "下架", 5: "预热"}.get(status, str(status)),
                note=basis,
            )
        )

    return board


def value_of_points(board: Board, points: float, strategy: str = "best") -> float:
    """给定积分数，按指定策略折算成现金价值。"""
    if not board.quotes:
        return 0.0
    if strategy == "best":
        rate = board.best.rate
    elif strategy == "median":
        rate = board.median_rate()
    else:  # worst
        rate = board.worst.rate
    return round(points * rate, 2)


def best_redeem(board: Board, points: int, live_only: bool = True) -> List[Quote]:
    """给定积分余额，按汇率从高到低推荐可兑换商品。"""
    pool = [q for q in board.quotes if (not live_only or q.live)]
    return sorted([q for q in pool if q.points <= points], key=lambda q: q.rate, reverse=True)


def render_board(board: Board, limit: int = 20) -> str:
    """渲染 ASCII 牌价表。统计口径与展示口径完全一致。"""
    rows = board.sorted_by_rate()[:limit]

    lines: List[str] = []
    lines.append("")
    lines.append("  POINT / CNY  EXCHANGE BOARD".center(92))
    lines.append(f"  生成时间 {board.generated_at}    样本 {len(rows)} 个在售商品".center(92))
    lines.append("")
    header = f"  {'#':>2}  {'商品':<32} {'积分':>6} {'现金价':>7} {'汇率(元/分)':>12} {'反牌价(分/元)':>13}"
    lines.append(header)
    lines.append("  " + "-" * 88)
    for i, q in enumerate(rows, 1):
        name = q.name[:30] + (".." if len(q.name) > 30 else "")
        lines.append(
            f"  {i:>2}  {name:<32} {q.points:>6} {q.cash_cny:>7.2f} "
            f"{q.rate:>12.4f} {q.points_per_yuan:>13.1f}"
        )
    lines.append("  " + "-" * 88)
    b, w = board.best, board.worst
    if b and w:
        lines.append("")
        lines.append(f"  最优牌价   {b.rate:.4f} 元/分   <- {b.name}（{b.points} 分）")
        lines.append(f"  最差牌价   {w.rate:.4f} 元/分   <- {w.name}（{w.points} 分）")
        lines.append(f"  中位牌价   {board.median_rate():.4f} 元/分")
        lines.append(f"  极    差   {board.spread:.2f} x   "
                     f"（同样 1 积分，选对选错价值差 {board.spread:.2f} 倍）")
    lines.append("")
    return "\n".join(lines)
