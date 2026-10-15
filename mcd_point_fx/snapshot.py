"""快照加载：让 demo 在完全没有 Token 的情况下也能跑出真实结论。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SNAPSHOT_PATH = os.path.join(_DATA_DIR, "snapshot.json")

# MCP 商品状态：1-仓库中 2-上架 3-售罄 4-下架 5-预热
STATUS_TEXT = {1: "仓库中", 2: "上架", 3: "售罄", 4: "下架", 5: "预热"}


def load_snapshot(path: str = SNAPSHOT_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_dt(text: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except (ValueError, TypeError):
            continue
    return None


def is_live(product: Dict[str, Any], now: datetime | None = None) -> bool:
    """商品当前是否仍可兑换。"""
    now = now or datetime.now()
    if product.get("status") != 2:
        return False
    down = parse_dt(product.get("downTime", "") or "")
    if down is None:
        return True
    return down > now


def products(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(snap.get("products", []))


def lottery(snap: Dict[str, Any]) -> Dict[str, Any]:
    return dict(snap.get("lottery", {}))
