# AGENTS.md

This file provides guidance to Antigravity when working with this repository.

## Project Overview

RepoMind 是一款**面向代码仓库的智能诊断与证据构建智能体（Agentic Debugging & Evidence System）**。它聚焦于解决代码智能体工作流中最为核心的“问题定位、上下文压缩、调用链扩展与诊断证据链（Evidence Report）生成”问题。

### 定位与对标（为什么不是另一个 Claude Code）
RepoMind 的定位并非一个大而全的通用 Coding Agent（如 Claude Code 或 Cursor Agent 等商业化通用软件工程智能体，它们涵盖完整的代码编辑、测试运行和 PR 提交）。

相反，RepoMind 聚焦于**问题诊断与证据检索**：
- **定位**：代码仓库智能诊断 Agent / 智能体工作流的“诊断及上下文增强层”。
- **核心任务**：输入报错日志、测试失败信息或自然语言问题，自动在代码仓库中定位到最相关的符号，并通过静态调用图进行拓扑扩展，为 LLM 生成一份带有文件路径、函数名、行号及原因分析的可解释诊断报告（Evidence Report）。
- **生态接入**：RepoMind 可作为 **MCP Server** 接入外部成熟智能体工作流（如 Claude Code、Cursor 或自研主 Agent），为它们提供更精准的代码库检索与诊断证据。

## Package Management

本项目使用 **uv** 作为包管理器，不使用 pip。

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows

# 创建虚拟环境（Python 3.13）
uv venv --python 3.13

# 激活虚拟环境
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 安装项目（开发模式）
uv pip install -e ".[dev]"

# 添加新依赖
uv add <package>

# 添加开发依赖
uv add --dev <package>

# 同步依赖（等价于 pip install -r requirements.txt）
uv pip sync requirements.txt

# 锁定依赖
uv lock

# 运行命令
uv run python -m repomind
uv run pytest
```

## Virtual Environment

- 虚拟环境位于项目根目录 `.venv/`
- Python 版本：**3.13**
- 所有开发操作必须在虚拟环境中进行

## Environment Variables

所有系统级配置 and 密钥通过 `.env` 文件注入，**不要在代码或文档中硬编码密钥**。

`.env` 文件示例（从 `.env.example` 复制）：

```bash
# LLM 配置
REPOMIND_LLM_PROVIDER=litellm
REPOMIND_LLM_MODEL=claude-sonnet-4-6
REPOMIND_LLM_API_KEY=sk-xxx
REPOMIND_LLM_BASE_URL=

# Ollama 本地模型（离线模式）
# REPOMIND_LLM_PROVIDER=ollama
# REPOMIND_LLM_MODEL=deepseek-coder:6.7b
# REPOMIND_LLM_BASE_URL=http://localhost:11434

# 沙箱配置
REPOMIND_SANDBOX_MODE=docker
REPOMIND_SANDBOX_TIMEOUT=60

# 存储配置
REPOMIND_INDEX_DIR=.repomind

# 日志配置
REPOMIND_LOG_LEVEL=INFO

# 性能配置
REPOMIND_MAX_WORKERS=4
```

- `.env` 已在 `.gitignore` 中，不会被提交
- `.env.example` 作为模板提交到仓库

## Common Commands

```bash
# 运行测试
uv run pytest
uv run pytest tests/unit/
uv run pytest --cov=src/repomind --cov-report=term-missing

# 代码格式化
uv run ruff format src/ tests/

# Lint 检查
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/

# 类型检查
uv run mypy src/repomind/

# 运行 CLI
uv run repomind index ./my-project
uv run repomind query "认证流程"
uv run repomind rca --trace error.log
uv run repomind stats
```

## Architecture

```
src/repomind/
├── cli/                # CLI 命令与交互式 REPL (Typer)
├── indexer/            # 仓库扫描与 AST 解析 (Tree-sitter)
├── retriever/          # 混合检检索 (BM25 + sqlite-vec 语义 + RRF)
├── graph/              # 静态调用图构建与拓扑分析 (NetworkX)
├── context/            # 上下文拼接与骨架化压缩
├── agent/              # 诊断 Reasoner (LiteLLM 调用)
├── reporter/           # 结构化 Evidence Report (Markdown/JSON)
├── sandbox/            # 安全沙箱代码执行器 (Docker / 受限 subprocess)
├── models/             # 统一数据模型与 Pydantic 约束
├── storage/            # 本地嵌入式数据持久化 (SQLite + JSON)
├── mcp/                # Model Context Protocol 工具服务接口
└── utils/              # 路径、环境配置等通用工具
```

### 核心数据/控制流

```
报错日志 / 用户 Query
         ↓
  [Query Analyzer]
         ↓
  [Code Indexer] (AST 物理文件结构抽取)
         ↓
  [Hybrid Retriever] (BM25 词频匹配 + 向量嵌入 + RRF 排序)
         ↓
  [Call Graph Expander] (NetworkX 图拓扑 BFS 2-hop 关系蔓延)
         ↓
  [Context Builder] (包含文件、类、函数名与物理代码行的上下文)
         ↓
  [LLM Reasoner] (利用 LiteLLM 进行根因推理与修复方案决策)
         ↓
  [Evidence Reporter] (生成带诊断链依据的 Markdown/JSON 报告)
```

## Key Technical Decisions

- **定位在“检索与分析依据”而非“通用代码生成”**：不以自动写 PR 为唯一归宿，而是为 LLM 与开发者提供清晰的、可复核的代码关联证据（Evidence Report），从而降低代码幻觉与上下文冗余。
- **Tree-sitter 静态解析**：保持语法高容错性，无需配置运行依赖即可提取精确的代码结构和依赖。
- **SQLite + NetworkX**：提供零部署摩擦、极佳本地响应时间的内存图网络运算，支持微秒级拓扑遍历。
- **可插拔的 MCP Server 接口**：暴露出 `repomind.diagnose_issue` 和 `repomind.expand_call_chain` 等标准工具，使 RepoMind 可以轻量集成进任何外部 Coding Agent 流程。
- **受限沙箱与自动降级**：默认支持 Docker 沙箱执行测试和排错脚本，并能向 Subprocess 级别的资源与网络受限环境自动优雅降级，保障系统安全性。

## Evaluation & Benchmarking

RepoMind 内建小型 Bug 评估测试集（`tests/` 下与 `eval/benchmark_cases.json`），通过以下指标自动度量代码诊断准确度：
- **Top-1 / Top-3 File Hit Rate**：第一顺位/前三顺位代码文件定位准确率。
- **Function Hit Rate**：错误源函数定位命中率。
- **Evidence Coverage**：诊断报告中引用关键代码块的覆盖率。

## Lessons Learned — 代码审查与重构反思

重构与测试闭环后总结的根因模式，编写代码时必须严格遵守：

### 1. 细粒度调用关系维护
在解析和构建调用边时，必须明确记录调用者函数的具体限定名（`caller_qname`），严禁将其模糊折叠或归属为父类（`caller_class`）或模块级别，以确保图计算和影响面分析的精准。

### 2. 真实大模型对齐与优雅退避
在 `QueryService` 和 `RCAService` 中必须切实通过 `litellm` 调用大模型进行问题解答与修复代码生成；若 API 密钥缺失或网络异常，系统必须提供高容错的本地规则降级退避，绝不能让整个服务崩溃。

### 3. 类型推断兼容内置类型与复合法
推断引擎在处理显式类型提示时，不能仅以首字母大写筛选，必须兼容小写内置类型（如 `str`, `list`）及复合类型（如 `dict[str, int]`），同时使用 Python 的 `keyword` 库排除系统关键字。

### 4. 增量更新与幂等性设计
同一目录重复索引时必须保证幂等，通过文件 Hash 比较避免数据库条目无限累加。对于已在磁盘上被物理删除的文件，在增量扫描时必须主动级联清理 SQLite 符号表和 GraphStore 节点，保持数据纯净度。

### 5. 绝对路径剥离
qualified name 的生成必须完全剥离开发机本地的绝对路径盘符，统一向后使用 project-relative path，保证索引数据库能够跨环境/跨机器稳定移植。
