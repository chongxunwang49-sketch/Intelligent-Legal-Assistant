# -*- coding: utf-8 -*-
"""
智法通 V2 —— MCP 工具服务器（mcp 2.x MCPServer，stdio 传输）

工具：graph_query / search_law / check_compliance / calculate_damages / get_time_limit
运行：python -m app.mcp_servers.mcp_tool_server
接入：外部 MCP 客户端 list_tools/call_tool 或 LLM 经 tools 调用。
"""
from __future__ import annotations

import asyncio
import json
import logging

from mcp.server.mcpserver import MCPServer

logger = logging.getLogger(__name__)

app = MCPServer("zhifatong-mcp")


@app.tool()
async def graph_query(query: str, top_n: int = 5) -> str:
    """在法律知识图谱(Neo4j)中查询与问题相关的法条/案例"""
    from app.services.graph_service import graph_service

    rows = await graph_service.graph_query_text(query, max(1, min(int(top_n), 10)))
    return json.dumps(rows, ensure_ascii=False)


@app.tool()
async def search_law(query: str, top_k: int = 3) -> str:
    """在本地法律向量库检索法条条文"""
    from app.agent.tools import search_law_database

    return json.dumps(await search_law_database(query, max(1, min(int(top_k), 10))), ensure_ascii=False)


@app.tool()
async def check_compliance(clause_text: str) -> str:
    """用规则库核查合同条款风险与合法性"""
    from app.agent.tools import check_clause_legality

    return json.dumps(check_clause_legality(clause_text), ensure_ascii=False)


@app.tool()
async def calculate_damages(kind: str = "labor", **kwargs: float) -> str:
    """法律金额测算(经济补偿/利息等)"""
    from app.agent.tools import calculate_damages as _calc

    return json.dumps(_calc(kind, **{k: float(v) for k, v in kwargs.items()}), ensure_ascii=False)


@app.tool()
async def get_time_limit(topic: str = "") -> str:
    """查询常见法律时效"""
    from app.agent.tools import get_legal_time_limit

    return json.dumps(get_legal_time_limit(topic), ensure_ascii=False)


def main() -> None:
    asyncio.run(app.run_stdio_async())


if __name__ == "__main__":
    main()
