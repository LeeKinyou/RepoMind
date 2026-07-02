# RepoMind

> 本地优先的代码仓库智能外脑，让百万行代码一目了然。

RepoMind 是一款面向大型代码仓库的 **Repository Intelligence Platform**，通过静态分析、图谱检索和 AI 推理的深度融合，帮助开发者快速理解代码架构、精准定位问题根因。

## 核心特性

- **极速索引** — 基于 Tree-sitter 的纳秒级语法解析，10 万行项目 15 秒内完成全量索引
- **混合检索** — BM25 关键字检索 + 静态调用图拓扑 2-hop 扩展 + sqlite-vec 向量语义检索 + 多维 RRF 融合，支持基于 Token 重叠度、路径特征与 AST 符号的全方位重排（Rerank）
- **渐进式类型推断** — 6 策略级联推断算法，无需编译即可实现 70%+ 的 Python 类型推断准确率
- **智能根因分析** — Stack Trace 逆向对齐 + 沙箱自愈验证，自动生成修复补丁并回归测试
- **架构可视化** — 自动生成 Mermaid 调用图/依赖图，支持自定义展示层数，轻松理清调用脉络
- **双模式诊断** — 提供 Deterministic Evidence 模式（无需 LLM）和 Agent 模式（基于 LangGraph 状态机工作流与 ReAct 环路）供不同场景选择
- **MCP 协议对接** — 提供标准 Stdio 协议的官方 FastMCP Server，能无缝集成至 Claude Desktop、Cursor 等外部 AI 智能体工作流
- **结构化证据报告** — 支持一键将 RCA 根因定位结果导出为包含详细诊断链、修复补丁和影响面评估的 Markdown / JSON 证据报告
- **动态索引一致性** — 查询与 RCA 前自动执行 freshness gate，代码变更后通过增量刷新、`index_version`、文件 hash snapshot 和 Evidence 校验避免旧索引解释新代码
- **实时监听更新** — 提供 `repomind watch`，基于 `watchdog` 文件系统事件监听 Python 文件变更并自动刷新索引，事件不可用时回退到轮询
- **基准性能评估** — 内置评估框架与 Bug 基准用例，自动运行并统计 Top-1/Top-3 文件命中率、函数定位率等诊断效率指标
- **100% 本地运行** — 零配置开箱即用，支持离线退避策略，数据不离开本机

## 诊断双模式

- **Evidence Mode** (`--mode evidence`): 纯检索增强。通过对输入的报错日志进行词法分割与精准匹配，配合 1-hop 静态图遍历，在不请求大模型的前提下快速召回报错相关的代码片段和调用证据。
- **Agent Mode** (`--mode agent`): 主动诊断智能体。基于大模型与 LangGraph 状态图驱动的 ReAct 工作流（最多 5 轮）。它可以根据当前查找到的证据动态决定下一步是使用 `search_code` 还是 `expand_call_chain` 工具，直至得出高置信度的假设并输出最终诊断报告。

## MCP 快速配置

你可以将 RepoMind 作为 MCP Server 接入你的智能体开发流：

### Claude Code 接入

在你的项目中执行：
```bash
claude mcp add repomind uv run repomind mcp
```

### Cursor 接入

在 Cursor 的 MCP 选项卡中，添加新 Server：
- Type: `command`
- Command: `uv run repomind mcp`

### MCP 动态索引工具

RepoMind MCP Server 额外暴露动态一致性工具，方便外部智能体在修改代码后刷新和校验证据：

| 工具 | 作用 |
|---|---|
| `repomind.refresh_index` | 工作区 stale 时执行增量刷新 |
| `repomind.validate_index_freshness` | 校验当前磁盘代码是否仍匹配索引 snapshot |
| `repomind.validate_evidence` | 校验 Evidence Report 绑定的文件 hash 是否仍 current |
| `repomind.changed_files_since` | 基于 Git working tree 返回变更的 Python 文件 |

## 快速开始

### 安装

```bash
# 从源码安装
git clone git@github.com:LeeKinyou/RepoMind.git
cd RepoMind

# 使用 uv 创建虚拟环境并安装依赖
uv venv --python 3.13
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\Activate.ps1  # Windows PowerShell

# 安装项目（开发模式）
uv pip install -e ".[dev]"

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM API Key
```

### 基本用法

```bash
# 1. 索引你的项目
repomind index ./my-project

# 2. 智能查询
repomind query "用户认证流程" --expand 2

# 3. 根因分析
repomind rca --trace error.log

# 4. 架构可视化
repomind visualize AuthService --depth 3 --format mermaid

# 5. 监听代码变更并自动刷新索引
repomind watch --project ./my-project
```

## 动态索引与一致性

RepoMind 面向智能体修改代码后的连续诊断场景，不再假设仓库是静态的。每次成功索引都会推进 `index_version`，并将文件 `path + hash` 作为 snapshot 写入索引。查询、符号查看、调用图扩展和 RCA 分析前会自动检查 freshness；如果检测到文件被修改、新增或删除，会先执行增量刷新，再基于当前 snapshot 检索和生成证据。

Evidence Report 的 Markdown/JSON 输出会绑定：

- `index_version`
- `freshness_status`
- 参与证据文件的 hash

因此，外部智能体或用户可以通过 MCP 的 `repomind.validate_evidence` 判断旧报告是否仍适用于当前代码。

## 命令概览

| 命令 | 说明 | 示例 |
|------|------|------|
| `repomind index <path>` | 构建代码仓库索引 | `repomind index ./src` |
| `repomind query <question>` | 混合检索查询 | `repomind query "支付处理"` |
| `repomind rca` | 交互式/文件根因分析 | `repomind rca --trace error.log` |
| `repomind diagnose <trace_file>` | 根因分析并输出 Markdown/JSON 诊断证据报告 | `repomind diagnose error.log --mode agent -o report.md` |
| `repomind visualize <symbol>` | 架构可视化 | `repomind visualize UserService --format mermaid` |
| `repomind watch` | 监听 Python 文件变更并自动刷新索引 | `repomind watch --project .` |
| `repomind stats` | 显示索引统计 | `repomind stats` |
| `repomind mcp` | 启动 Stdio 模式的 MCP Server 服务端口 | `repomind mcp` |
| `repomind eval` | 运行基准评测 | `repomind eval --project .` |

## 基准评测

RepoMind 内置了针对仓库级代码检索和堆栈轨迹定位的严谨基准评测。

### 评测指标

- **Top-1 文件命中率**：目标文件被排在第一位的比例。
- **Top-3 文件命中率**：目标文件在前三个候选结果中被召回的比例。
- **函数命中率**：与文件绑定的目标函数精准匹配的比例。
- **平均延迟**：每个测试用例检索的平均响应时间。

### 当前评测结果

我们针对 50 个仓库理解与报错堆栈定位用例，对比评估了不同检索配置下的性能表现：

| 检索模式 | Top-1 文件命中率 | Top-3 文件命中率 | 函数命中率 | 平均延迟 |
|---|---:|---:|---:|---:|
| `keyword_only` | 70.0% | 96.0% | 88.3% | 0.021s |
| `symbol_only` | 80.0% | 96.0% | 98.0% | 0.038s |
| `hybrid` (RRF Fuse) | 56.0% | 94.0% | 94.0% | 0.194s |
| **`full` (Rerank + AST + Boost)** | **92.0%** | **98.0%** | **96.0%** | **0.037s** |

### 核心结论

评测结果表明，利用基于 AST 的符号索引、结构化堆栈轨迹解析以及多维得分加权的 **`full` 模式**，其性能显著优于原始的双向互惠排名融合（`hybrid`）和纯关键字基线。Top-1 文件命中率从 **56.0% 提升至 92.0%**，函数命中率从 **94.0% 提升至 96.0%**（其中 `symbol_only` 模式在针对结构化符号的目标查询中达到了 **98.0%**）。

### 失败案例分析

RepoMind 会在 `eval/reports/` 目录下自动生成失败案例和延迟分析报告：
- [latest_failure_report.md](file:///f:/VScode%20Workspace/Python_workspace/RepoMind/eval/reports/latest_failure_report.md)
- [latest_failure_report.json](file:///f:/VScode%20Workspace/Python_workspace/RepoMind/eval/reports/latest_failure_report.json)

评测器将错误分类为召回遗漏（missed recall）、排序错误（ranking errors）、函数缺失（function misses）、堆栈解析失败（stack trace parsing failures）以及警告异常，以便于进行快速定位和迭代优化。

运行对比基准评测：
```bash
uv run python eval/run_host_comparison.py --compare-modes
```

### 评测模式

RepoMind 支持多种检索模式进行对比：

| 模式 | 描述 |
|---|---|
| keyword_only | 基于关键字/Token 重叠度的检索基线 |
| symbol_only | 基于 AST 符号索引的诊断基线 |
| hybrid | 朴素的混合检索模式 |
| full | 完整管道：包含堆栈轨迹解析、路径感知得分、符号感知信号和二次重排 |

`symbol_only` 此前作为诊断基线时由于路径映射问题得分为 0%。在修复了 AST 符号索引、对齐了 `RetrievalResult` 数据结构并改进了文件级结果聚合逻辑后，`symbol_only` 现在能够成功解析符号引用，在针对结构化符号的目标查询中达到了 **80.0% 的 Top-1 文件命中率** 和 **98.0% 的函数命中率**。

### 沙箱模式

RepoMind 支持三种沙箱执行模式：

| 模式 | 运行行为 |
|---|---|
| auto | 若 Docker 可用则使用 Docker，否则自动降级为受限子进程模式 |
| docker | 强制要求 Docker 守护进程，如果不可用则快速报错失败 |
| subprocess | 在本地直接运行，不使用 Docker 隔离 |

对于本地基准评测，使用子进程模式通常已经足够：

```bash
uv run python eval/run_host_comparison.py --compare-modes --sandbox subprocess
```

如需进行隔离的补丁验证，请启动 Docker Desktop 并运行：

```bash
uv run python eval/run_host_comparison.py --sandbox docker
```

在 Windows 系统上，使用 Docker 沙箱前请确保 Docker Desktop 正在运行。

详细的测试方法和智能体模式对比报告请参阅 [智能体基准评测](docs/testing/agent_benchmark.md)。

## 项目结构

```
RepoMind/
├── README.md                   # 项目说明
├── CLAUDE.md                   # Claude Code 项目指引
├── AGENTS.md                   # Agentic 开发规范与架构指引
├── pyproject.toml              # 项目配置与依赖
├── .env.example                # 环境变量模板
├── .gitignore
├── CHANGELOG.md                # 版本变更记录
├── CONTRIBUTING.md             # 贡献指南
├── src/
│   └── repomind/
│       ├── __init__.py
│       ├── cli/                # CLI 命令与交互式 REPL (Typer)
│       ├── indexer/            # 仓库扫描与 AST 解析 (Tree-sitter)
│       ├── retriever/          # 混合检索 (BM25 + sqlite-vec 语义 + RRF)
│       ├── graph/              # 静态调用图构建与拓扑分析 (NetworkX)
│       ├── context/            # 上下文拼接与骨架化压缩
│       ├── agent/              # 诊断 Reasoner (LiteLLM / LangGraph 调用)
│       ├── reporter/           # 结构化 Evidence Report (Markdown/JSON)
│       ├── sandbox/            # 安全沙箱代码执行器 (Docker / 受限 subprocess)
│       ├── models/             # 统一数据模型与 Pydantic 约束
│       ├── storage/            # 本地嵌入式数据持久化 (SQLite + sqlite-vec)
│       ├── mcp/                # Model Context Protocol 工具服务接口
│       └── utils/              # 路径、环境配置等通用工具
├── tests/                      # 测试目录
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/                       # 文档目录
│   ├── requirements/           # 需求与产品
│   │   ├── 问题定义.md
│   │   ├── 需求分析.md
│   │   └── 产品设计文档.md
│   ├── design/                 # 技术设计
│   │   ├── 技术架构文档.md
│   │   ├── 架构决策记录.md
│   │   ├── 数据库设计文档.md
│   │   ├── API接口文档.md
│   │   └── 安全设计文档.md
│   ├── dev/                    # 开发相关
│   │   ├── 技术可行性调研.md
│   │   ├── 开发环境搭建指南.md
│   │   └── 代码审查报告.md
│   └── testing/                # 测试与使用
│       ├── 测试计划文档.md
│       └── 用户使用手册.md
└── .repomind/                  # 索引数据（运行时生成）
    ├── index.db                # SQLite 索引
    └── cache/                  # 缓存
```

## 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 语言 | Python 3.13 | AI 生态最佳兼容 |
| 语法解析 | py-tree-sitter | 纳秒级解析，语法容错 |
| 类型推断 | Jedi | Python 静态分析引擎 |
| 结构存储 | SQLite | 零配置单文件 |
| 向量存储 | sqlite-vec | 轻量内嵌向量检索，无需独立服务 |
| 图计算 | NetworkX | PageRank、Louvain、BFS |
| LLM 接口 | LiteLLM | 一行切换本地/云端模型 |
| CLI | Typer | 生产级命令行界面 |
| 终端美化 | Rich | 彩色面板与进度条 |
| 文件监听 | watchdog | 事件驱动监听代码变更并触发增量刷新 |

## 文档

**需求与产品** (`docs/requirements/`)：
- [问题定义](docs/requirements/问题定义.md) — 核心技术冲突与目标用户痛点
- [需求分析](docs/requirements/需求分析.md) — 功能/非功能需求、MVP 边界、验收标准
- [产品设计文档](docs/requirements/产品设计文档.md) — 用户画像、功能设计、交互设计、竞品分析

**技术设计** (`docs/design/`)：
- [技术架构文档](docs/design/技术架构文档.md) — 分层架构、数据架构、接口设计、安全架构
- [架构决策记录](docs/design/架构决策记录.md) — 10 项关键技术选型的决策过程与理由
- [数据库设计文档](docs/design/数据库设计文档.md) — SQLite 表结构、sqlite-vec 向量设计、NetworkX 图设计
- [API 接口文档](docs/design/API接口文档.md) — 核心服务接口定义、数据模型、使用示例
- [安全设计文档](docs/design/安全设计文档.md) — 沙箱隔离、命令过滤、Prompt 注入防御
- [动态索引一致性与时效性方案](docs/design/动态索引一致性与时效性方案.md) — 代码变更后的 freshness gate、增量刷新、Evidence snapshot 与 MCP 校验设计

**开发相关** (`docs/dev/`)：
- [技术可行性调研](docs/dev/技术可行性调研.md) — 工具选型对比与关键技术算法
- [开发环境搭建指南](docs/dev/开发环境搭建指南.md) — 环境配置、依赖安装、开发工具
- [代码审查报告](docs/dev/代码审查报告.md) — 代码审查发现的问题与修复方案

**测试与使用** (`docs/testing/`)：
- [测试计划文档](docs/testing/测试计划文档.md) — 测试策略、用例设计、覆盖率目标
- [用户使用手册](docs/testing/用户使用手册.md) — 面向最终用户的详细操作手册
- [贡献指南](CONTRIBUTING.md) — 代码规范、提交规范、PR 流程

## License

MIT
