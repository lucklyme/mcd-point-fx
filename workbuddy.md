# WorkBuddy 开发上下文

> 本文件记录 mcd-point-fx 使用腾讯 WorkBuddy 智能体完成的开发过程，
> 用于核验「麦当劳程序员创意开发大赛 × WorkBuddy」联动奖励条件。

## 1. 使用的 WorkBuddy 能力

| 能力 | 在项目中的具体用途 |
|---|---|
| 连接器 · 自定义 MCP | 在 WorkBuddy 中配置并启用 `mcd-mcp`，直连 `https://mcp.mcd.cn`，用于实时拉取积分商城与抽奖数据 |
| 网页读取 / 信息提取 | 抓取官方活动仓库 README、`activityGuidelines.md`、`RANKING.md`，完成赛制与竞品分析 |
| 本地文件读写与代码生成 | 生成项目骨架、核心算法、测试用例与全部参赛文档 |
| 命令执行 | 运行 `demo.py`、执行单元测试、验证输出正确性 |

## 2. 通过 WorkBuddy 直连 MCP 的实证记录

WorkBuddy 侧配置（`~/.workbuddy/mcp.json`）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer ${MCD_MCP_TOKEN}" }
    }
  }
}
```

以下 MCP 工具均通过 WorkBuddy 实际调用成功（真实响应，非模拟）：

| 调用 | 结果 |
|---|---|
| `tools/list` | HTTP 200，返回 35 个工具（官方 README 仅列出 30 个） |
| `now-time-info` | 返回服务器时间 `2026-10-15 22:09:47 GMT+08:00` |
| `query-my-account` | 返回积分账户：可用 0 / 累计 310.5 / 已过期 305.5 |
| `mall-points-products` | 返回 49 个商品，`1>4` 类目 25 个，含积分价与上下架时间 |
| `query-lottery-info` | 返回奖池 10 个奖品，单次消耗 24 积分，活动进行中 |
| `campaign-calendar` | 返回 2026 年 10 月整月营销活动日历 |
| `available-coupons` | 返回 7 张麦麦省可领券 |
| `order-list` / `query-my-coupons` | 返回空（该账号无历史订单与卡包） |

**关键决策依据**：正因为 `order-list` 返回空，WorkBuddy 分析后明确指出——
凡依赖个人历史消费数据的选题（消费画像、年度账单）在本账号上无法产出 demo，
本项目因此改为**完全由公开数据驱动**，这也是最终选定「积分汇率 + 抽奖 EV」方向的直接原因。

## 3. 关键开发对话摘要

1. **赛制分析**：WorkBuddy 读完官方规则后指出排名机制是纯 GitHub Star 排序、无技术评审，
   且同一账号多项目只取 Star 最高者，据此建议集中资源做单个项目。
2. **赛道定位**：对 104 个上榜项目按名称归类，发现点餐助手（18+）、省钱比价（14+）、
   MBTI 玄学（11+）已极度拥挤，而**积分/商城仅 4 个、抽奖仅 1 个**，遂选定空白赛道。
3. **概念设计**：提出把积分体系建模为外汇市场——每个 SKU 是一个 `POINT/CNY` 货币对，
   抽奖是一张可定价的期权。
4. **缺陷发现与修复**：首版 `demo.py` 输出「极差 621.87 倍」，WorkBuddy 判定为统计口径 bug
   （把已下架的 1 积分历史活动计入了最优牌价），修正为默认只统计在售商品后，
   得到可信的 **5.04 倍**，并补充单元测试 `test_spread_is_credible` 防止回归。
5. **表述严谨化**：将最初的「只要实际概率不低于等概率假设的 0.188 倍」
   改写为「抽奖回报要跌到当前的 18.8% 以下，兑换才会反超」，避免对概率的误导性表述。

## 4. 产出清单

- 核心代码：`mcd_point_fx/`（`rate.py` 汇率引擎、`ev.py` EV 引擎、`mcp_live.py` 实时接入、`cli.py` 命令行）
- 一键演示：`demo.py`（零第三方依赖、零 Token 可跑）
- 真实数据快照：`data/snapshot.json`
- 单元测试：`tests/test_core.py`（10 项，全部通过）
- 参赛文档：`README.md` / `CONTEST_DECLARATION.md` / `MCP_INTEGRATION.md` / `mcp-config.example.json` / 本文件

## 5. 合规说明

- 本文件不含任何真实 Token、密钥或账号凭证。
- 项目中所有涉及凭证的位置均使用 `${MCD_MCP_TOKEN}` 环境变量占位符。
- 未读取、未存储任何第三方个人信息；`order-list`、`query-my-coupons` 在本账号下返回空。
