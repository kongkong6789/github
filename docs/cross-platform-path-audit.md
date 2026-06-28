# Windows + macOS 路径审计清单

## 目标

让项目可以：

1. 在 macOS 上开发和启动。
2. 后续回到 Windows 时不需要维护两套业务代码。
3. 把操作系统差异尽量收敛到启动脚本和少量运维脚本里。

## 这次已经落地的部分

### 1. 运行时路径继续环境变量化

后端核心 Python 模块已经以 repo 相对路径 + `A2A_*` 环境变量为主，例如：

- `A2A_RAW_DIR`
- `A2A_DATA_DIR`
- `A2A_WIKI_DIR`
- `A2A_CLEANED_DIR`
- `A2A_DERIVED_DIR`
- `A2A_WAREHOUSE_DIR`
- `A2A_DUCKDB_PATH`
- `A2A_LIGHTRAG_DIR`
- `A2A_TASK_DIR`

这意味着业务逻辑层本身不依赖某台电脑上的固定盘符或用户目录。

### 2. 新增 Bash/macOS 脚本

已补齐：

- `scripts/start_backend.sh`
- `scripts/stop_backend.sh`
- `scripts/health_backend.sh`
- `scripts/start_frontend.sh`
- `scripts/stop_frontend.sh`
- `scripts/start_fullstack.sh`
- `scripts/stop_fullstack.sh`
- `scripts/start_lightrag_server.sh`
- `scripts/stop_lightrag_server.sh`
- `scripts/health_lightrag.sh`
- `scripts/sync_lightrag.sh`
- `scripts/register_fact_layer.sh`
- `scripts/query_fact_layer.sh`
- `scripts/verify_python.sh`
- `scripts/repair_thread_archives.sh`
- `scripts/reset_knowledge_state.sh`

### 3. Windows 启动脚本去掉了不必要的固定机器假设

已修复：

- `scripts/start_frontend.ps1` 不再写死 `<NODE_INSTALL_DIR>/node.exe`
- 前后端启动脚本会先读取根目录 `.env`

### 4. 前端本地归档路径支持环境变量

`agent-chat-ui/src/app/api/local-threads/route.ts` 现在支持：

- `A2A_DATA_DIR`
- `A2A_TASK_DIR`
- `A2A_THREAD_ARCHIVE_DIR`

这样 macOS 上如果你把 `data/` 放到自定义位置，前端侧边栏历史也不会丢。

## 当前仍然保留的 Windows 专属表面

这些是有意保留的，不影响 macOS 跑通：

- `scripts/*.ps1`
- 桌面 `.bat` 一键启动文件
- PowerShell 专属端口/进程处理方式

它们属于 Windows 运维层，不属于跨平台业务逻辑问题。

## 已收尾的 P7 路径/平台差异

### 1. 文档层历史路径已统一

README、TODO 和 docs 下的历史本机路径示例已统一成 `<A2A_PROJECT_ROOT>` 占位符。后续不要在 Markdown 文档里新增固定盘符、用户目录、固定 Node 安装目录或直接 `.venv` 内部可执行文件路径。

### 2. 运维脚本默认成对提供

启动、停止、健康检查、LightRAG、fact layer、verify、线程归档修复和知识状态重置脚本都已补齐两套入口：

- `*.ps1`
- `*.sh`

`tests/test_p7_engineering_guardrails.py` 会检查 `scripts/*.ps1` 和 `scripts/*.sh` 的 stem 是否成对，避免以后新增脚本只补一侧。

### 3. 桌面快捷入口仍是 Windows 方案

当前桌面一键启动是：

- `启动A2A工作台.bat`
- `停止A2A工作台.bat`

如果后续真要长期在 macOS 上用，建议再补：

- `启动A2A工作台.command`
- `停止A2A工作台.command`

## 后续新增代码时的排查命令

```bash
python -m unittest tests.test_p7_engineering_guardrails
```

## 建议的维护原则

1. 业务代码优先走 `pathlib.Path` / `node:path` / repo 相对路径。
2. 自定义数据目录优先走 `A2A_*` 环境变量。
3. OS 差异只放在 `scripts/*.ps1` 和 `scripts/*.sh`。
4. 新增运维入口时，默认同时补 Windows 和 macOS 两套脚本。
