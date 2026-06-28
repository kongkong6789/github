# Google Stitch Creative UI Prompt: A2A 电商经营大脑

> 用途：把本文件完整复制到 https://stitch.withgoogle.com/ ，让 Stitch 重新生成一套全新的 Web UI 原型。  
> 核心目标：让 Stitch 尽可能发挥想象力，重做视觉、布局、动效、内容表达和交互体验，同时保持现有产品逻辑、路由、接口和页面跳转不变。

## 1. 给 Stitch 的总指令

请为「A2A 电商经营大脑」设计一套全新的 Web App UI。

这不是对当前界面的美化，也不是照着旧页面重新排版。请把当前项目当作「业务逻辑地图」，而不是视觉参考。你可以完全重新想象它的界面形态、视觉语言、组件结构、页面动线、特效和内容表达。

唯一需要保留的是：

- 现有路由不变
- 页面跳转关系不变
- API endpoint 不变
- API method / action 不变
- 表单和操作背后的业务意义不变
- 用户通过对话输入经营目标后，仍然进入可追踪任务流程
- 任务、数据、证据链、权限、SkillHub、MCP/API、日志这些模块仍然存在

除此之外，请大胆创作。

## 2. 语言输出要求

所有可见 UI 内容都使用简体中文。

请把页面标题、导航、按钮、表单 label、placeholder、空状态、错误提示、加载提示、筛选项、排序项、状态说明、卡片标题、表格字段名、弹窗文案、toast 文案、移动端文案全部生成为中文。

英文只保留在这些必须使用英文的地方：

- API endpoint，例如 `/api/workbench`
- route，例如 `/tasks/[taskId]`
- method 或 action，例如 `task.list`、`install_skill`
- 技术名词，例如 DuckDB、LightRAG、SkillHub、MCP、API、Agent、LLM Wiki
- 文件路径、task_id、thread_id、tool_name、代码片段和 JSON 字段

如果需要表达英文概念，请优先使用中文主文案，英文作为括号内补充。例如：

```text
任务执行轨迹（Agent Trace）
技能市场（SkillHub）
数据事实层（DuckDB Facts）
```

请避免生成英文营销文案、英文导航、英文按钮、英文空状态和英文示例用户姓名。示例业务内容也使用中文电商场景。

## 3. 创意自由范围

你可以自由决定：

- 页面布局是侧边栏、顶部栏、指挥舱、画布、抽屉、分屏、浮层还是其他结构
- 首页是否像 Command Center、Agent Console、Data Studio、Mission Control 或其他概念
- 是否使用动态图谱、数据流线、分层玻璃、3D 纵深、仪表盘、悬浮操作台、命令面板
- 是否重写按钮文案、空状态文案、提示文案，让它们更自然
- 是否重组信息层级，让用户更快理解下一步
- 是否使用电影感页面转场、列表瀑布出现、任务进度动画、证据链路径动画、SkillHub 市场动效
- 是否使用更强的视觉资产，例如抽象数据地形、任务流轨迹、仓储/电商数据符号、技能图标系统

请尽量输出一套有记忆点、有完成度、有真实产品感的 UI，而不是普通后台模板。

## 4. 产品理解

产品名：A2A 电商经营大脑

产品一句话：

```text
把电商经营资料变成可执行、可追踪、可复盘的 Agent 任务链路。
```

底层能力：

```text
LLM Wiki + DuckDB 事实层 + LightRAG 检索 + 多 Agent + ERP 实时兜底 + 权限审计
```

使用者：

- 电商运营
- PM
- 经营分析人员
- 本地 Agent 操作者
- 需要看结果、看证据、看风险的业务负责人

核心工作流：

```text
用户提出经营目标
  -> 系统判断需要的数据和工具
  -> 检查资料、知识库、DuckDB、LightRAG、ERP 连接
  -> 拆成可追踪任务
  -> Agent 执行
  -> 生成证据链、报告、风险提示、下一步动作
  -> 用户可查看任务、日志、数据状态和工具权限
```

设计感方向可以大胆，但产品本质要让用户感到：

- 我知道现在系统在做什么
- 我知道哪些数据可用、哪些数据不可用
- 我知道结论来自哪里
- 我知道任务执行到哪一步
- 我知道什么时候需要我确认
- 我知道如何回到对话继续工作

## 5. 创意方向

请优先考虑一种「智能经营指挥舱」的体验，而不是传统 SaaS 后台。

可以参考这些关键词组合，它们只是灵感方向，不是视觉限制：

- Command Workspace
- Agent Mission Control
- Data Flow Studio
- Evidence Graph Console
- Local-first AI Operations
- Ecommerce Intelligence Desk
- Skill Market Operating System

视觉氛围可以更高级、更有想象力：

- 精密
- 深度
- 有速度感
- 有数据生命力
- 可信但不沉闷
- 科技感但不廉价
- 有动效但不影响阅读
- 既像工作台，也像一个可以操控 Agent 的操作系统

可以加入的特效方向：

- 首页背景有轻微的数据流动层，像经营数据正在被编排
- 用户输入框出现时有命令面板式聚焦动效
- 任务启动后，输入框周围出现流程节点生成动画
- 任务列表进入页面时按状态分组轻微瀑布出现
- 任务详情的阶段进度可以像一条可展开的执行轨迹
- 证据链页面可以有节点连线、路径高亮、来源追踪动画
- 数据健康页面可以有服务心跳、连接状态、数据表同步脉冲
- SkillHub 市场可以像技能库、插件商店或能力地图
- MCP/API 策略可以用「通道」「权限开关」「风险层级」表达
- 运行日志可以像实时事件流，支持折叠和过滤

动效要求是“帮助理解系统状态”，不是单纯装饰。

## 6. 需要解决的体验问题

旧 UI 只是问题参考，不是视觉参考。请重新设计时解决这些体验问题：

- 首页打开后应立刻能开始输入业务目标
- 首页首屏直接呈现核心输入区，用户打开页面就能开始工作
- 对话内容始终可读，底部输入区和消息流之间保持清晰距离
- 历史对话可以作为独立视图、抽屉或沉浸列表，但选中某条历史后应进入该线程，不再额外叠加历史浮层
- 「治理中心」这个词对用户不直观，前台更建议表达为「权限与工具」
- 「注册表」这个词对业务用户不直观，可以根据语境表达为「已配置技能」「工具清单」「数据源清单」「配置文件路径」
- SkillHub 更像完整技能市场，支持类目、排序、筛选、安装动作
- 知识库不可用时，展示可能原因和下一步，而不是单一技术错误文本
- 无真实任务上下文的装饰说明卡、模拟人物身份、固定建议卡都可以被完全重构或移除

## 7. 全局路由和页面跳转

这些路由需要保留。你可以重新设计显示名称、导航形态和页面布局，跳转目标保持一致。

| 当前页面 | 路由 | 功能 |
| --- | --- | --- |
| 新建任务 / 对话工作台 | `/` | 用户输入经营目标，发起 Agent 任务 |
| 历史对话 | `/?chatHistoryOpen=true` | 查看本地归档聊天记录 |
| 指定线程 | `/?threadId=...` | 打开某条线程内容 |
| 本地归档线程 | `/?threadId=local-archive-...` | 只读查看本地归档内容 |
| 任务中心 | `/tasks` | 查看任务列表、进度、异常、可恢复任务 |
| 任务详情 | `/tasks/[taskId]` | 查看单个任务的阶段、证据、日志、恢复动作 |
| 资料接入 | `/data-sources` | 登记数据源、同步快照、查看配置 |
| 数据状态 | `/data-health` | 查看 DuckDB、LightRAG、知识库、连接器健康 |
| 证据链 | `/evidence-graph` | 查看结论、数据、工具调用之间的关系 |
| 权限与工具 - 技能 | `/governance?tab=skills` | 管理本地 Skill、SkillHub 市场和安装状态 |
| 权限与工具 - MCP/API | `/governance?tab=mcp` | 管理 MCP/API 策略、权限和确认规则 |
| 运行日志 | `/logs` | 查看排错日志和执行事件流 |

页面关系：

```text
/
  -> /?chatHistoryOpen=true
  -> /?threadId=...
  -> /tasks
  -> /data-sources
  -> /data-health
  -> /governance?tab=skills
  -> /governance?tab=mcp
  -> /logs

/tasks
  -> /tasks/[taskId]
  -> /
  -> /data-health

/tasks/[taskId]
  -> /tasks
  -> /
  -> /data-health
  -> /evidence-graph?taskId=...
  -> /api/agent-traces?taskId=...

/data-sources
  -> /data-health
  -> /

/data-health
  -> /data-sources
  -> /logs
  -> /

/governance?tab=skills
  -> /governance?tab=mcp
  -> /logs

/logs
  -> /tasks
  -> /data-health
```

## 8. 页面创意 brief

### 6.1 首页 / 对话工作台 `/`

这是整个产品的第一印象。请把它设计成一个可以立即开工的「经营目标输入台」。

可自由发挥：

- 输入框可以像命令面板、任务发射台、经营 Brief 编辑器或 Agent 控制台
- 快捷任务可以是 chips、能力磁贴、命令行推荐、悬浮工具条、能力环、横向滑动区
- 知识库状态可以是顶部状态、输入框旁边的连接指示、或者工作区状态胶囊
- 上传资料、本地工作区、隐藏执行细节这些能力可以重新组合为更自然的操作区
- 空状态可以加入数据流、任务流、业务资料整理过程的动态图形

需要支持的动作：

- 输入业务目标并发送
- 上传 PDF 或图片
- 隐藏或显示工具调用细节
- 查看知识库连接状态
- 打开历史对话
- 进入任务中心
- 进入资料接入、数据状态、权限与工具、日志
- 使用快捷任务 prompt

快捷任务语义需要保留，可重新命名：

- 整理资料
- 清洗表格
- 库存风险
- 经营分析
- 同步知识库
- 广告诊断
- 商品内容优化
- 供应商风险
- 财务分析
- 老板报告

### 6.2 对话线程 `/?threadId=...`

这是用户和 Agent 协作的主场景。

可自由发挥：

- 消息可以是传统气泡，也可以是任务时间线、报告段落、Agent 卡片、执行记录混合流
- 工具调用可以折叠成 trace 节点
- Agent trace 可以是右侧可展开轨迹、消息内嵌路径、底部执行面板
- 归档线程可以用只读状态、档案封面、时间标记表达
- 输入框可以固定、浮动或吸附到底部，并和消息内容保持清晰空间关系

需要支持：

- 展示历史消息
- 展示用户消息和助手消息
- 展示工具调用 / Agent trace
- 支持继续输入
- 支持只读归档线程
- 支持回到底部
- 支持错误提示

### 6.3 历史对话 `/?chatHistoryOpen=true`

请重新设计成更自然的历史归档体验。

可自由发挥：

- 独立页面
- 全屏归档视图
- 可搜索列表
- 时间线视图
- 右侧预览
- 分组归档
- 可从历史记录进入线程

需要支持：

- 展示本地线程归档
- 点击记录进入 `/?threadId=...`
- 删除归档
- 清空归档
- 显示只读归档状态

### 6.4 任务中心 `/tasks`

任务中心是后台执行的控制台。

可自由发挥：

- 任务可以按运行中、可恢复、已完成、异常分组
- 可以用表格、密集列表、任务轨道、状态泳道
- 可以设计进度条、阶段指示、风险提示、报告入口
- 可以有顶部统计区，但不必像普通卡片

需要支持：

- 调用 `task.list`
- 搜索 task_id、goal、报告名、wiki 页面
- 筛选状态、时间范围、类型
- 进入 `/tasks/[taskId]`
- 展示任务状态、进度、风险、产物、更新时间

### 6.5 任务详情 `/tasks/[taskId]`

任务详情是“为什么系统这么做”的解释页面。

可自由发挥：

- 可以设计成任务执行轨迹
- 可以设计成 Agent 作战记录
- 可以用阶段线、证据节点、风险面板、报告产物区组合
- 原始 JSON 可以作为开发者折叠区

需要支持：

- 调用 `task.show`
- 展示任务摘要、状态、原始目标、阶段进度
- 展示 Agent 交接、QA Gate、步骤明细
- 展示错误和恢复线索
- 支持 `cancel`
- 支持 `recover`
- 跳转数据健康、证据链、调用轨迹、报告、Wiki

### 6.6 资料接入 `/data-sources`

资料接入是把本地文件、业务目录和数据源登记进系统的页面。

可自由发挥：

- 可以像数据仓库控制台
- 可以像文件接入流水线
- 可以像多源同步面板
- 可以用 schema diff、快照版本、连接状态动画

需要支持：

- 调用 `source.list`
- 显示数据源、快照、架构漂移、暂停状态、配置文件、原始区
- 筛选全部、启用、失败、过期
- 选择某个数据源查看详情
- 动作：sync、register、status、rebind
- 跳转 `/data-health` 和 `/`

### 6.7 数据状态 `/data-health`

数据状态展示系统当前是否可靠工作。

可自由发挥：

- 服务心跳图
- 连接拓扑
- DuckDB / LightRAG / ERP / 文件区状态仪表
- 风险诊断面板
- 修复建议路径

需要支持：

- 调用 `data.health`
- 展示 DuckDB、facts/marts、LightRAG、知识库、ERP、connector、raw files 状态
- 展示可用、预警、失败、不可用
- 给出下一步动作
- 跳转资料接入、日志、对话页

### 6.8 证据链 `/evidence-graph`

证据链用于解释结论来自哪里。

可自由发挥：

- 可以做成动态图谱
- 可以做成报告证据路径
- 可以做成节点网络、时间线、引用链路、数据血缘图
- 可以有路径高亮、节点展开、风险标记

需要支持：

- 调用 `evidence.graph`
- 支持 `taskId`
- 支持 `reportPath`
- 展示 report、fact、dataset、wiki、tool、decision 等节点
- 展示边、来源、置信度、风险
- 支持查看节点详情

### 6.9 权限与工具 `/governance?tab=skills`

这是技能、工具、审批和策略的统一管理区。

可自由发挥：

- 可以像能力市场
- 可以像 Agent 操作系统设置
- 可以像技能图谱
- 可以让本地技能和 SkillHub 市场出现在同一个体验中

技能管理需要包含：

- 技能市场
- 已安装技能
- 已配置技能 / 技能配置清单
- SkillHub 安装入口
- 搜索
- 类目
- 排序
- 安装到项目
- 启用 / 暂停 / 禁用 / 归档
- 更新
- 删除配置

SkillHub 市场体验需要更完整：

- 推荐
- SkillHub
- 套件
- 类目筛选
- 综合评分
- 下载量
- 最近更新
- 安装量
- 每页数量选择
- 安装动作
- CLI 状态检查

### 6.10 MCP/API `/governance?tab=mcp`

MCP/API 是工具权限、策略和风险确认区。

可自由发挥：

- 可以用权限通道
- 可以用策略矩阵
- 可以用工具风险层级
- 可以用“读 / 写 / 需要确认”三层表达

需要支持：

- 读取 MCP/API 策略
- 展示只读、写入、人工确认、高风险
- 编辑策略
- 启用 / 暂停 / 禁用
- 查看审计
- 跳转日志

### 6.11 运行日志 `/logs`

日志页面用于排错。

可自由发挥：

- 实时事件流
- 命令行风格日志
- 筛选面板
- 错误聚合
- Agent 执行 trace
- 开发者诊断模式

需要支持：

- 调用 `logs.tail`
- 按 level、source、task_id、thread_id 筛选
- 展示时间、级别、来源、消息、上下文
- 支持复制错误
- 支持跳转任务、数据状态

## 9. API 合同

请在 UI 原型中保持这些接口语义。你可以自由设计调用入口、按钮形态、加载状态和错误状态。

### 7.1 Workbench API

Endpoint:

```text
POST /api/workbench
```

请求结构：

```json
{
  "method": "task.list",
  "params": {}
}
```

响应结构：

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

支持 method：

| method | 用途 |
| --- | --- |
| `task.list` | 任务列表 |
| `task.show` | 任务详情 |
| `agent.trace` | Agent 执行 trace |
| `data.health` | 数据健康 |
| `governance.policy` | 权限、策略、工具 |
| `approval.submit` | 人工确认 |
| `logs.tail` | 日志 |
| `evidence.graph` | 证据链 |
| `source.list` | 数据源列表 |
| `source.show` | 数据源详情 |
| `source.sync` | 数据源同步 |

### 7.2 独立 API

| API | Method | 用途 |
| --- | --- | --- |
| `/api/local-threads` | `GET` | 获取历史对话 |
| `/api/local-threads` | `POST` | 归档当前对话 |
| `/api/local-threads` | `DELETE` | 删除或清空历史 |
| `/api/tasks/[taskId]` | `GET` | 获取任务详情 |
| `/api/tasks/[taskId]` | `PATCH` | `cancel` / `recover` |
| `/api/data-sources` | `GET` | 获取资料接入列表 |
| `/api/data-sources` | `POST` | `sync` / `register` / `status` / `rebind` |
| `/api/governance` | `GET` | 获取技能、工具、策略 |
| `/api/governance` | `POST` | 新增或导入配置 |
| `/api/governance` | `PATCH` | 更新启用、暂停、禁用、归档 |
| `/api/governance` | `DELETE` | 删除配置 |
| `/api/skillhub` | `GET` | SkillHub catalog / search |
| `/api/skillhub` | `POST` | `install_skill` |
| `/api/data-health` | `GET` | 数据健康 |
| `/api/logs` | `GET` | 运行日志 |
| `/api/evidence-graph` | `GET` | 证据链 |
| `/api/agent-traces` | `GET` | Agent trace |

## 10. 状态设计

请为所有页面设计完整状态，覆盖动态和异常场景。

需要覆盖：

- 默认状态
- 加载状态
- 空状态
- 成功状态
- 预警状态
- 失败状态
- 不可用状态
- 只读归档状态
- 人工确认状态
- 高风险动作状态

知识库不可用时，可以表达为：

```text
知识库暂时不可用
可能原因：LightRAG 服务未启动、端口不可访问或模型配置缺失。
下一步：前往数据状态或运行日志查看。
```

## 11. Stitch 输出要求

请生成一套完整 Web App UI，而不是单张首页。

至少包含这些页面或画面：

1. 首页空状态 `/`
2. 对话线程状态 `/?threadId=...`
3. 历史对话视图 `/?chatHistoryOpen=true`
4. 任务中心 `/tasks`
5. 任务详情 `/tasks/[taskId]`
6. 资料接入 `/data-sources`
7. 数据状态 `/data-health`
8. 证据链 `/evidence-graph`
9. 权限与工具 - SkillHub `/governance?tab=skills`
10. 权限与工具 - MCP/API `/governance?tab=mcp`
11. 运行日志 `/logs`

每个页面请尽量给出：

- 桌面版
- 移动版
- 加载状态
- 空状态
- 错误状态
- 关键交互动效
- 主要按钮和二级按钮
- 页面跳转入口
- 数据字段展示方式

## 12. 最终设计目标

请把它设计成一个让人愿意每天打开使用的 AI 经营工作台。

它应该有足够强的视觉想象力，让人一眼知道这不是普通后台；也要有足够清晰的工作逻辑，让运营、PM 和业务负责人能真正完成任务。

创意可以尽可能大胆。  
业务逻辑保持完整。  
页面跳转和 API 按本文档延续。  
其他视觉、内容、动效、组件形态都交给 Stitch 自由发挥。
