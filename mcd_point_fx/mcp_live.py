"""实时模式：直接从麦当劳 MCP Server 拉数据。

零第三方依赖，只用标准库 urllib。
Token 从环境变量 MCD_MCP_TOKEN 读取，**绝不硬编码**。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

MCP_URL = "https://mcp.mcd.cn"
DEFAULT_TIMEOUT = 25


class MCPError(RuntimeError):
    pass


def _token() -> str:
    tok = os.environ.get("MCD_MCP_TOKEN", "").strip()
    if not tok:
        raise MCPError(
            "未检测到环境变量 MCD_MCP_TOKEN。\n"
            "  获取方式：登录 https://open.mcd.cn/mcp -> 控制台 -> 激活 -> 复制 MCP Token\n"
            "  设置方式：export MCD_MCP_TOKEN=你的Token   （Windows: setx MCD_MCP_TOKEN 你的Token）\n"
            "  不配置也可以：直接跑 python demo.py，会用内置快照演示。"
        )
    return tok


def _json_from(text: str, start: int) -> Any:
    """从 start 位置起解析一个完整 JSON 值。"""
    dec = json.JSONDecoder()
    return dec.raw_decode(text[start:])[0]


def _parse_payload(raw: str) -> Any:
    """MCP 响应可能是裸 JSON，也可能是 SSE；payload 本身还可能是 Markdown 包着的。"""
    raw = raw.strip()

    if raw.startswith("{"):
        obj = json.loads(raw)
    else:
        obj = None
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                body = line[len("data:"):].strip()
                if body:
                    obj = json.loads(body)
                    break
        if obj is None:
            raise MCPError(f"无法解析 MCP 响应：{raw[:200]}")

    result = obj.get("result", obj)

    # 优先用结构化内容
    if isinstance(result, dict) and isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]

    # 否则从 content[].text 里挖出内嵌 JSON
    contents = result.get("content") if isinstance(result, dict) else None
    if isinstance(contents, list):
        for item in contents:
            text = item.get("text", "") if isinstance(item, dict) else ""
            if not text:
                continue
            marker = text.find("## Original Response")
            search = text[marker:] if marker >= 0 else text
            idx = search.find("{")
            if idx >= 0:
                try:
                    return _json_from(search, idx)
                except ValueError:
                    continue
    return result


def call_tool(tool: str, arguments: Optional[Dict[str, Any]] = None, url: str = MCP_URL) -> Any:
    """调用一个 MCP tool 并返回其业务数据体。"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {_token()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise MCPError("401 未授权：MCP Token 无效或已过期，请重新申请。") from exc
        if exc.code == 429:
            raise MCPError("429 限流：单 Token 每分钟最多 600 次请求，请降低频率。") from exc
        raise MCPError(f"MCP 调用失败 HTTP {exc.code}：{exc.read().decode('utf-8', 'ignore')[:200]}") from exc
    except urllib.error.URLError as exc:
        raise MCPError(f"网络错误：{exc.reason}") from exc

    return _parse_payload(raw)


def fetch_products() -> list:
    """返回积分商城商品列表。"""
    payload = call_tool("mall-points-products", {})
    if isinstance(payload, dict):
        return payload.get("data", []) or []
    return payload or []


def fetch_lottery() -> dict:
    """返回抽奖活动信息。"""
    payload = call_tool("query-lottery-info", {})
    if isinstance(payload, dict):
        inner = payload.get("data")
        return inner if isinstance(inner, dict) else (payload or {})
    return {}
