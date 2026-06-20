# RepoMind

> 本地优先的代码仓库智能外脑，让百万行代码一目了然。

RepoMind 是一款面向大型代码仓库的 **Repository Intelligence Platform**，通过静态分析、图谱检索和 AI 推理的深度融合，帮助开发者快速理解代码架构、精准定位问题根因。

## 核心特性

- **极速索引** — 基于 Tree-sitter 的纳秒级语法解析，10 万行项目 15 秒内完成全量索引
- **混合检索** — BM25 关键字检索 + 向量语义检索 + 图拓扑 2-hop 扩展，精准召回率远超纯向量 RAG
- **渐进式类型推断** — 6 策略级联推断算法，无需编译即可实现 70%+ 的 Python 类型推断准确率
- **智能根因分析** — Stack Trace 逆向对齐 + 沙箱自愈验证，自动生成修复补丁并回归测试
- **架构可视化** — 自动生成 Mermaid 调用图/依赖图，一行命令看清模块关系
- **Token 节省 90%+** — 单次查询仅消耗 ~5,000 Tokens，相比传统文件遍历节省 40 万 Tokens
- **100% 本地运行** — 零配置开箱即用，无需联网，数据不离开本机

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
```

## 命令概览

| 命令 | 说明 | 示例 |
|------|------|------|
| `repomind index <path>` | 构建代码仓库索引 | `repomind index ./src` |
| `repomind query <question>` | 混合检索查询 | `repomind query "支付处理" --expand 2` |
| `repomind rca` | 根因分析 | `repomind rca --trace error.log` |
| `repomind visualize <symbol>` | 架构可视化 | `repomind visualize UserService --format mermaid` |
| `repomind stats` | 显示索引统计 | `repomind stats` |

## 项目结构

```
RepoMind/
├── README.md                   # 项目说明
├── CLAUDE.md                   # Claude Code 项目指引
├── pyproject.toml              # 项目配置与依赖
├── .env.example                # 环境变量模板
├── .gitignore
├── CHANGELOG.md                # 版本变更记录
├── CONTRIBUTING.md             # 贡献指南
├── src/
│   └── repomind/
│       ├── __init__.py
│       ├── cli/                # CLI 命令层 (Typer)
│       │   ├── __init__.py
│       │   ├── app.py          # 主入口
│       │   ├── index_cmd.py    # index 命令
│       │   ├── query_cmd.py    # query 命令
│       │   ├── rca_cmd.py      # rca 命令
│       │   └── visualize_cmd.py # visualize 命令
│       ├── services/           # 应用服务层
│       │   ├── index_service.py
│       │   ├── query_service.py
│       │   ├── rca_service.py
│       │   └── visualization_service.py
│       ├── core/               # 核心引擎层
│       │   ├── parser/         # Tree-sitter 解析引擎
│       │   ├── type_inference/ # 渐进式类型推断
│       │   ├── call_graph/     # 调用图构建
│       │   └── retrieval/      # 混合检索引擎
│       ├── models/             # 数据模型
│       ├── storage/            # 存储层 (SQLite + LanceDB + NetworkX)
│       ├── sandbox/            # 沙箱执行器
│       └── utils/              # 工具函数
├── tests/                      # 测试目录
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── CHANGELOG.md                # 版本变更记录
├── CONTRIBUTING.md             # 贡献指南
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
    ├── vectors.lance           # LanceDB 向量存储
    └── cache/                  # 缓存
```

## 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 语言 | Python 3.13 | AI 生态最佳兼容 |
| 语法解析 | py-tree-sitter | 纳秒级解析，语法容错 |
| 类型推断 | Jedi | Python 静态分析引擎 |
| 结构存储 | SQLite | 零配置单文件 |
| 向量存储 | LanceDB | 无服务器，磁盘存储 |
| 图计算 | NetworkX | PageRank、Louvain、BFS |
| LLM 接口 | LiteLLM | 一行切换本地/云端模型 |
| CLI | Typer | 生产级命令行界面 |
| 终端美化 | Rich | 彩色面板与进度条 |

## 文档

**需求与产品** (`docs/requirements/`)：
- [问题定义](docs/requirements/问题定义.md) — 核心技术冲突与目标用户痛点
- [需求分析](docs/requirements/需求分析.md) — 功能/非功能需求、MVP 边界、验收标准
- [产品设计文档](docs/requirements/产品设计文档.md) — 用户画像、功能设计、交互设计、竞品分析

**技术设计** (`docs/design/`)：
- [技术架构文档](docs/design/技术架构文档.md) — 分层架构、数据架构、接口设计、安全架构
- [架构决策记录](docs/design/架构决策记录.md) — 10 项关键技术选型的决策过程与理由
- [数据库设计文档](docs/design/数据库设计文档.md) — SQLite 表结构、LanceDB Schema、NetworkX 图设计
- [API 接口文档](docs/design/API接口文档.md) — 核心服务接口定义、数据模型、使用示例
- [安全设计文档](docs/design/安全设计文档.md) — 沙箱隔离、命令过滤、Prompt 注入防御

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
