# 智法通 V2 —— 企业级智能法律顾问平台

> 从零重构 + 补齐旧项目路线图 + Docker 部署交付

智法通是一套**基于本地大模型的企业级智能法律顾问平台**：法律智能问答（带法条引用）、两阶段 RAG 检索、多 Agent 对抗式合同审查、法律知识库管理、Neo4j 知识图谱 + GraphRAG、数据分析与可视化。面向企业法务、执业律师与中小企业主。

本项目以旧版生产级范本为参照**独立从零开发**，在功能对齐基础上补齐了旧项目的路线图缺口（Neo4j 图谱语义化、GraphRAG 三路融合、Self-RAG 自评估闭环、时间旅行查询、官方 MCP 工具接线、Agent Function Calling），并修复其多项缺陷（上传文档检索不到、流式问答引用缺失等）。UI 布局与风格致敬旧范本。

## ✨ 核心能力

| 模块 | 说明 |
|------|------|
| 法律智能问答 | 查询重写 / 子查询分解 / 混合检索 / **LLM 自评估+重检索闭环** / SSE 流式 / 法条引用校验 |
| 两阶段检索 | 粗排（Chroma `bge-large-zh-v1.5` 1024 维 ANN + BM25 + RRF）→ 精排（Cross-Encoder `bge-reranker-v2-m3` 微服务） |
| GraphRAG（新增） | 法条-案例-概念实体链接 + Cypher 图谱扩展，三路 RRF 融合检索 |
| 知识图谱（补齐） | Neo4j：Law/Article/Case/Concept/PartyType + RELATES/REFERENCES/HAS_ARTICLE/MENTIONS/INVOLVES，语义化约束 |
| 时间旅行查询（新增） | 法条版本化（生效/废止日期），按时间点返回当时有效版本 |
| 合同审查 | LangGraph 12 节点多 Agent 对抗式（主审/复核/反方/辩论）+ 公共规则库 + 优化并下载 |
| MCP 工具生态（补齐） | 官方 MCP SDK 工具中心 + law/case/contract/calc/compliance/graph_query 服务器 + Function Calling 接线 |
| 知识库管理 | 文档上传→条款级分块→向量化→增量维护；统一 metadata schema |
| 数据分析 | 咨询热点 / 法条引用统计 / 用户聚类 / 趋势 / 仪表盘 / ECharts 可视化 |
| 安全与合规 | JWT+RBAC 三级权限 / 登录防爆破 / XSS 净化 / 额度控制 / AI 免责声明 |

## 🏗 技术栈

FastAPI · SQLAlchemy 2.0(async, MySQL 8.0) · Redis 7 · ChromaDB · Neo4j 5
LangGraph · MCP SDK · Ollama(qwen2.5:1.5b / bge-large-zh-v1.5) · bge-reranker-v2-m3
Vue3 + TypeScript + Vite + Element Plus + Pinia + ECharts · Docker Compose · Nginx

## 📁 目录结构

```
backend/            FastAPI 后端（api/models/services/agent/rag/mcp_servers/utils）
frontend/           Vue3 前端（M6 交付）
rerank_service/     Cross-Encoder 精排微服务（pytorch 环境）
scripts/            DB 初始化 / 一键启动等运维脚本
sql/                MySQL 建库脚本
docs/               需求文档 / 部署手册 / 测试报告（随里程碑产出）
docker-compose.yml  生产编排（M8 交付）
docker-compose.infra.yml  开发期基础设施（mysql/redis/neo4j）
```

## 🚀 快速开始（开发模式）

```bash
# 1. 基础设施（Docker Desktop 需运行）
docker compose -f docker-compose.infra.yml up -d mysql redis neo4j

# 2. 精排服务（pytorch 环境，模型自动下载约 1.1GB）
python rerank_service/server.py            # 监听 127.0.0.1:9999

# 3. 后端（conda base，已装依赖；首次启动自动建表+幂等种子+向量索引）
cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 28000

# 4. 前端（开发预览 http://localhost:5173）
cd frontend && npm install && npm run dev
```

访问：后端 `http://localhost:28000/docs`（Swagger）· 健康 `http://localhost:28000/health`

### 默认演示账号

| 角色 | 账号 | 密码 | 权限 |
|------|------|------|------|
| 超级管理员 | `admin` | `admin123` | 全部功能 + 用户管理，不限额度 |
| 法务负责人 | `lawyer` | `lawyer123` | 业务 + 数据分析 + 知识库管理 |
| 普通用户 | `user` | `user123456` | 问答/合同/检索，问答 50 次/日 |

## 🗺 交付进度（全部完成）

- ✅ M0 环境与脚手架（依赖 / 基础设施 compose / 自建 rerank 精排服务）
- ✅ M1 后端基础设施（16 表 / RBAC / 认证 / 通知 / 用户管理 / 幂等种子 / 生命周期）
- ✅ M2 知识库 + 两阶段 RAG（修复"上传文档检索不到"缺陷）
- ✅ M3 智能问答 + Self-RAG 闭环 + SSE
- ✅ M4 LangGraph 12 节点对抗式合同审查 + 公共规则库 + Function Calling 工具集
- ✅ M5 Neo4j 语义图谱 / GraphRAG 三路 / 时间旅行 / 官方 MCP(MCPServer) / 分析仪表盘
- ✅ M6 Vue3 前端重建（8 页面 · 布局风格对齐 · 4 主题 · SSE · ECharts）
- ✅ M7 测试与文档（需求文档 / 部署手册 / 测试报告）
- ✅ M8 Docker 化与部署验收（5 容器全 healthy，端到端 24/24 · 100%）

## 📚 文档
- 需求文档：[docs/项目需求文档.md](docs/项目需求文档.md)
- 部署手册：[docs/部署手册.md](docs/部署手册.md)
- 测试报告：[docs/测试报告.md](docs/测试报告.md)
