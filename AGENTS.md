# AGENTS.md

This file provides guidance to Antigravity when working with this repository.

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

## Lessons Learned — 代码审查反思

两轮审查共修复 38 个问题。以下是反复出现的根因模式，编写代码时必须避免。

### 1. 修一条线，不修一个点

修 bug 时不能只改眼前的那一行。必须：
- **grep 全项目**找所有同类代码（如 `.replace("/", ".")` 在 4 处出现）
- **检查所有调用点**是否需要同步修改（如 `safe_symbol_type` 需要放在公共位置）
- **检查数据流上下游**（如 symbol_index 类型从 `dict[str,str]` 改为 `dict[str,list[str]]`，resolver 和测试必须同步更新）

### 2. 设计假设必须考虑最坏情况

- 键是否可能重复？→ `__init__`、`get`、`parse` 在大项目中随处可见，不能用短名作唯一键
- 输入是否可能有噪声？→ 源码正则匹配必须排除注释 and 字符串
- 边界是否做了类型转换？→ NetworkX 存 `str`，Pydantic 要 `SymbolType`，必须在边界处显式转换

### 3. 字符串分割是脆弱的解析策略

tree-sitter 已提供精确的 AST 节点边界，应该利用它而不是 `split(":")` / `split("->")`：
- 签名提取 → 用 `body_node.start_byte` 精确切取
- 返回类型 → 用正则 `->\s*([\w\[\],\s\.]+)\s*:` 匹配

### 4. 异常捕获必须精确

`except Exception` 会掩盖真正的错误。明确"什么异常表示什么情况"，只捕获预期的异常类型：
- LanceDB 表不存在 → `(ValueError, KeyError, OSError)`
- SQLite 连接失败 → `sqlite3.OperationalError`
- 文件被删除 → `OSError`

### 5. 代码搜索/检索需要领域适配

BM25 为自然语言设计，用于代码搜索必须适配：
- 分词：按 `_.\s` 分割，`get_user_info` → `["get", "user", "info"]`
- 噪声：排除注释和字符串中的匹配
- 融合：不同 source 的 score 量纲不同，必须用 RRF 而非直接比较

### 6. 端到端测试不可或缺

单元测试保证每个零件合格，但不能保证组装后能用。关键路径必须有端到端测试：
- 索引 → 查询 → 图扩展 → 结果非空
- 索引 → RCA → 符号查找 → 匹配成功
- 索引 → 搜索 "user" → 能找到 `get_user_info`

## Important Files

- `pyproject.toml` — 项目元数据、依赖、构建配置
- `.env.example` — 环境变量模板
- `.ruff.toml` — Ruff 格式化和 Lint 配置
- `AGENTS.md` — 本文件，Antigravity 项目指引
