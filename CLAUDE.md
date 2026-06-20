# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

RepoMind 是一款面向大型代码仓库的 Repository Intelligence Platform，通过静态分析（Tree-sitter）、图谱检索（SQLite + NetworkX + LanceDB）和 AI 推理（LiteLLM）的深度融合，帮助开发者快速理解代码架构、精准定位问题根因。

首期仅支持 Python 语言。

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

所有系统级配置和密钥通过 `.env` 文件注入，**不要在代码或文档中硬编码密钥**。

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
├── cli/                # CLI 命令层 (Typer)
├── services/           # 应用服务层
│   ├── index_service.py
│   ├── query_service.py
│   ├── rca_service.py
│   └── visualization_service.py
├── core/               # 核心引擎层
│   ├── parser/         # Tree-sitter 解析引擎
│   ├── type_inference/ # 渐进式类型推断（6 策略级联）
│   ├── call_graph/     # 调用图构建
│   └── retrieval/      # 混合检索引擎（BM25 + 向量 + 图扩展）
├── models/             # 数据模型（Pydantic）
├── storage/            # 存储层（SQLite + LanceDB + NetworkX）
├── sandbox/            # 沙箱执行器（Docker / 子进程）
└── utils/              # 工具函数
```

### 核心数据流

```
源代码 → Tree-sitter 解析 → 符号提取 → 类型推断 → 调用图构建
                                                        │
                    ┌───────────────────────────────────┤
                    v                                   v
              SQLite（结构化存储）              LanceDB（向量存储）
                    │                                   │
                    └───────────────┬───────────────────┘
                                    v
                          混合检索（BM25 + 向量 + RRF 融合）
                                    │
                                    v
                          图拓扑 BFS 2-hop 扩展（NetworkX）
                                    │
                                    v
                            上下文骨架化剪枝 → LLM
```

## Key Technical Decisions

- **Tree-sitter** 而非完整编译器：语法容错，无需配置依赖即可解析
- **SQLite + NetworkX** 而非 Neo4j：零配置、本地优先、微秒级查询
- **LanceDB** 而非 FAISS/Milvus：无服务器、磁盘存储、嵌入式
- **渐进式类型推断** 而非完整类型检查：开箱即用，6 策略级联（0.95 → 0.40 置信度）
- **Explorer-Solver 双 Agent + 线性管道** 而非多 Agent 自由协商：避免死锁，Token 可控
- **Docker 沙箱** 作为默认安全方案：网络禁用、只读挂载、资源限制

## Conventions

- Commit Message 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范
- 代码风格遵循 PEP 8，使用 Ruff 格式化
- 类型注解：所有公开函数必须有完整的类型注解
- Docstring：使用 Google 风格
- 测试：pytest，使用 Arrange-Act-Assert 模式
- 分支命名：`feat/`、`fix/`、`docs/`、`refactor/`、`test/`、`chore/`

## Important Files

- `pyproject.toml` — 项目元数据、依赖、构建配置
- `.env.example` — 环境变量模板
- `.ruff.toml` — Ruff 格式化和 Lint 配置
- `CLAUDE.md` — 本文件，Claude Code 项目指引
