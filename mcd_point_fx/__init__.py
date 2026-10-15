"""mcd-point-fx - McDonald's China Points Foreign Exchange Desk.

把麦当劳积分体系当成一个外汇市场：
每个可兑换商品是一个货币对 POINT/CNY，汇率 = 现金价值 / 所需积分。
"""

__version__ = "1.0.0"
__all__ = ["rate", "ev", "snapshot", "mcp_live", "cli"]
