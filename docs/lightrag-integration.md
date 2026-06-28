# 完整 LightRAG + Obsidian 集成

## 为什么要加

Obsidian 适合人读和长期维护，但公司级辅助决策还需要 Agent 能回答：

- 哪些 SKU、供应商、库存表、财务表和历史决策有关联？
- 当前结论引用了哪些 wiki 页面和 cleaned CSV？
- 某个经营风险是从哪个资料链路推出来的？

LightRAG 的核心思想是“图谱结构 + 文档检索”结合。当前项目已经升级为双模式：

- `official`：优先连接完整 LightRAG Server，支持语义检索、图谱关系和文档引用。
- `local fallback`：LightRAG Server 不可用时，自动使用本地轻量索引兜底，保证前端和多 Agent 链路不断。

## 当前实现

代码：

```text
<A2A_PROJECT_ROOT>/src/a2a_ecommerce_demo/lightrag_tools.py
```

完整 LightRAG 同步状态：

```text
<A2A_PROJECT_ROOT>/data/lightrag/official_sync.json
```

本地兜底索引：

```text
<A2A_PROJECT_ROOT>/data/lightrag/index.json
```

读取来源：

```text
<A2A_PROJECT_ROOT>/wiki
<A2A_PROJECT_ROOT>/data/cleaned
```

提供工具：

```text
lightrag_server_status
sync_obsidian_to_official_lightrag
query_official_lightrag
get_lightrag_track_status
rebuild_lightrag_index
query_lightrag
list_lightrag_entities
get_lightrag_entity
```

`query_lightrag` 是统一入口：完整 LightRAG 可用时优先查询官方服务；不可用时自动使用本地索引。

## 启动完整 LightRAG

安装完整 LightRAG Server：

```powershell
cd /d <A2A_PROJECT_ROOT>
./scripts/install_lightrag.ps1
```

配置 `.env` 中的 embedding 参数。注意：完整 LightRAG 需要 embedding 模型，不能只配聊天 LLM。

```text
A2A_LIGHTRAG_MODE=official
LIGHTRAG_API_URL=http://127.0.0.1:9621
LIGHTRAG_API_KEY=

LLM_BINDING=openai
LLM_MODEL=xiaomi/mimo-v2.5-pro
LLM_BINDING_HOST=https://token-plan-cn.xiaomimimo.com/v1
LLM_BINDING_API_KEY=你的 LLM token

EMBEDDING_BINDING=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BINDING_HOST=https://api.openai.com/v1
EMBEDDING_BINDING_API_KEY=你的 embedding token
```

如果你的 Xiaomi 接口也提供 OpenAI-compatible embedding，可以把 `EMBEDDING_BINDING_HOST` 和 `EMBEDDING_BINDING_API_KEY` 换成同一套服务；如果不提供，需要单独配置一个 embedding 服务。

启动服务：

```powershell
cd /d <A2A_PROJECT_ROOT>
./scripts/start_lightrag_server.ps1
```

健康检查：

```powershell
cd /d <A2A_PROJECT_ROOT>
./scripts/health_lightrag.ps1
```

同步 Obsidian + cleaned CSV：

```powershell
cd /d <A2A_PROJECT_ROOT>
./scripts/sync_lightrag.ps1
```

停止服务：

```powershell
cd /d <A2A_PROJECT_ROOT>
./scripts/stop_lightrag_server.ps1
```

## 工作逻辑

```text
Obsidian Markdown + cleaned CSV
        ↓
sync_obsidian_to_official_lightrag
        ↓
完整 LightRAG Server 建立语义索引和知识图谱
        ↓
query_lightrag / query_official_lightrag
        ↓
返回 answer + references/source/path
        ↓
多 Agent 输出带证据链的辅助决策
```

## 在多 Agent 中的位置

```text
data_pipeline_team
  → wiki_ingest_agent
  → lightrag_agent
  → quality_gate_agent

decision_team / strategy_team
  → query_lightrag
  → 引用证据链后再输出建议
```

## 前端用法

```text
请检查完整 LightRAG 服务状态，然后把 Obsidian 和 cleaned 数据同步进去。
```

```text
请基于完整 LightRAG 查询库存、现金流、供应商交期之间有哪些证据关系。
```

```text
查看 LightRAG 里和某个品牌、渠道或产品线相关的实体、来源页面和关系。
```

## 和 Karpathy LLM Wiki 的关系

这条路线非常契合 Karpathy LLM Wiki：

```text
Obsidian = 人类可维护的长期知识库
LightRAG = Agent 可检索、可关联、可引用的索引层
LangGraph = 多 Agent 任务编排和工具执行层
```

也就是说，Obsidian 仍然是 source of truth。LightRAG 不替代 Obsidian，只负责索引和查询。

## 企业级注意事项

- embedding 模型必须稳定，否则文档插入和查询会失败。
- 真实财务、采购价、客户信息进入 LightRAG 前要做权限和脱敏。
- `raw` 原始资料保持只读，避免 Agent 覆盖真实文件。
- 决策报告必须引用 LightRAG references、Obsidian 页面或 cleaned 数据路径。
- 大额采购、调价、广告预算、外发消息仍然必须人工确认。

## 后续企业增强

- Neo4j / Postgres / Milvus / OpenSearch 存储
- 前端图谱可视化
- 决策报告逐条引用 CSV 行号和 wiki 段落
- 基于文件变更的自动增量同步
- 多用户权限、审计后台、敏感字段脱敏规则库
