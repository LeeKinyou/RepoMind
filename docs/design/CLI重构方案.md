# RepoMind CLI 重构方案 — Claude Code 风格

## 一、设计目标

将现有 CLI 重构为类似 Claude Code 的交互体验：
- `/` 前缀触发命令
- 自然语言对话式查询
- 美观的 Rich 终端界面
- 流式输出效果

## 二、交互设计

### 2.1 启动界面

```
╭──────────────────────────────────────────────────────────────────────────────╮
│                                                                              │
│   ██████╗ ███████╗██████╗  ██████╗ ███╗   ███╗██╗███╗   ██╗██████╗         │
│   ██╔══██╗██╔════╝██╔══██╗██╔═══██╗████╗ ████║██║████╗  ██║██╔══██╗        │
│   ██████╔╝█████╗  ██████╔╝██║   ██║██╔████╔██║██║██╔██╗ ██║██║  ██║        │
│   ██╔══██╗██╔══╝  ██╔═══╝ ██║   ██║██║╚██╔╝██║██║██║╚██╗██║██║  ██║        │
│   ██║  ██║███████╗██║     ╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██████╔╝        │
│   ╚═╝  ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝       │
│                                                                              │
│                    Repository Intelligence Platform                          │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯

  项目: F:\VScode Workspace\Python_workspace\RepoMind
  索引: 4,114 files | 263,004 symbols | 35,199 classes

  💡 输入自然语言查询，或使用 / 命令
  📖 输入 /help 查看帮助

>
```

### 2.2 命令系统

#### 斜杠命令

| 命令 | 别名 | 说明 | 示例 |
|------|------|------|------|
| `/index` | `/i` | 索引项目 | `/index ./src` |
| `/query` | `/q` | 精确查询 | `/query IndexService` |
| `/show` | `/s` | 查看符号详情 | `/show IndexService` |
| `/graph` | `/g` | 调用图可视化 | `/graph IndexService --depth 3` |
| `/callers` | `/c` | 查看调用者 | `/callers index_directory` |
| `/callees` | `/cl` | 查看被调用者 | `/callees IndexService` |
| `/rca` | `/r` | 根因分析 | `/rca` (进入粘贴模式) |
| `/stats` | `/st` | 索引统计 | `/stats` |
| `/clear` | `/x` | 清除索引 | `/clear` |
| `/config` | `/cf` | 查看/修改配置 | `/config` |
| `/help` | `/?` | 显示帮助 | `/help` |
| `/quit` | `/q` | 退出 | `/quit` |

#### 自然语言查询

直接输入文本会被视为自然语言查询：

```
> 用户认证流程是怎样的？
> 哪些函数调用了数据库？
> IndexService 的依赖关系
> 找出所有处理支付的类
```

### 2.3 输出样式

#### 查询结果

```
╭─ 🔍 查询结果: "用户认证" ─────────────────────────────────────────────────────╮
│                                                                               │
│  找到 12 个相关符号 (0.234s)                                                  │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │  1. AuthService (class)                                                 │  │
│  │     📄 src/services/auth_service.py:15-89                               │  │
│  │     📝 处理用户认证和授权的核心服务                                       │  │
│  ├─────────────────────────────────────────────────────────────────────────┤  │
│  │  2. authenticate (method)                                               │  │
│  │     📄 src/services/auth_service.py:25-45                               │  │
│  │     📝 验证用户凭据并返回 JWT token                                      │  │
│  ├─────────────────────────────────────────────────────────────────────────┤  │
│  │  3. verify_token (method)                                               │  │
│  │     📄 src/services/auth_service.py:50-65                               │  │
│  │     📝 验证 JWT token 的有效性                                           │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  💡 使用 /show <name> 查看详情，/graph <name> 查看调用图                      │
╰───────────────────────────────────────────────────────────────────────────────╯
```

#### 符号详情

```
╭─ 📦 AuthService ──────────────────────────────────────────────────────────────╮
│                                                                               │
│  类型: class                                                                  │
│  模块: src.services.auth_service                                              │
│  位置: src/services/auth_service.py:15-89                                     │
│                                                                               │
│  📝 文档                                                                      │
│  ─────────────────────────────────────────────────────────────────────────── │
│  处理用户认证和授权的核心服务                                                  │
│  支持 JWT token 和 OAuth2.0 认证方式                                          │
│                                                                               │
│  📄 源代码                                                                    │
│  ─────────────────────────────────────────────────────────────────────────── │
│  15 │ class AuthService:                                                      │
│  16 │     """处理用户认证和授权的核心服务"""                                   │
│  17 │                                                                        │
│  18 │     def __init__(self, db: Database):                                   │
│  19 │         self.db = db                                                    │
│  20 │         self.secret_key = os.getenv("SECRET_KEY")                       │
│                                                                               │
│  🔗 调用关系                                                                  │
│  ─────────────────────────────────────────────────────────────────────────── │
│  调用者 (3):                                                                  │
│    ← LoginController.login                                                   │
│    ← UserController.get_profile                                              │
│    ← Middleware.authenticate                                                  │
│                                                                               │
│  被调用 (5):                                                                  │
│    → Database.query                                                          │
│    → JWT.encode                                                              │
│    → PasswordHasher.verify                                                   │
│    → Cache.get                                                               │
│    → Logger.info                                                             │
╰───────────────────────────────────────────────────────────────────────────────╯
```

#### 调用图

```
╭─ 🌐 调用图: AuthService (depth=2) ────────────────────────────────────────────╮
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                          ┌──────────────┐                               │  │
│  │                          │ AuthService  │                               │  │
│  │                          └──────┬───────┘                               │  │
│  │                                 │                                       │  │
│  │           ┌─────────────────────┼─────────────────────┐                 │  │
│  │           │                     │                     │                 │  │
│  │           ▼                     ▼                     ▼                 │  │
│  │    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐            │  │
│  │    │   Database   │    │   JWT Lib    │    │  Password    │            │  │
│  │    │    .query    │    │    .encode   │    │  Hasher      │            │  │
│  │    └──────────────┘    └──────────────┘    └──────────────┘            │  │
│  │                                                                         │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  📊 统计: 5 个节点, 7 条边                                                    │
╰───────────────────────────────────────────────────────────────────────────────╯
```

#### RCA 结果

```
╭─ 🔴 根因分析 ─────────────────────────────────────────────────────────────────╮
│                                                                               │
│  ❌ TypeError: 'NoneType' object is not subscriptable                        │
│                                                                               │
│  📍 位置: src/services/user_service.py:45                                     │
│  🎯 置信度: 85%                                                               │
│                                                                               │
│  📋 调用链                                                                    │
│  ─────────────────────────────────────────────────────────────────────────── │
│    → main()                                                                   │
│    → process_request()                                                        │
│    → get_user_data()                                                          │
│    ✗ get_user_profile()  ← 错误发生位置                                       │
│                                                                               │
│  💡 分析                                                                      │
│  ─────────────────────────────────────────────────────────────────────────── │
│  函数 get_user_profile() 尝试对 None 值进行索引操作。                          │
│  可能原因:                                                                    │
│  1. 数据库查询返回空结果                                                      │
│  2. 用户 ID 不存在                                                            │
│                                                                               │
│  🔧 建议修复                                                                  │
│  ─────────────────────────────────────────────────────────────────────────── │
│  ```python                                                                   │
│  def get_user_profile(user_id):                                              │
│      user = db.query(User).get(user_id)                                      │
│      if user is None:                                                        │
│          raise UserNotFoundError(f"User {user_id} not found")                │
│      return user["profile"]                                                  │
│  ```                                                                          │
╰───────────────────────────────────────────────────────────────────────────────╯
```

### 2.4 进度指示

```
⏳ 正在索引项目...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  75% | 3,084/4,114 files | ETA: 2s

⏳ 正在查询...
⠋ Analyzing code structure...
```

### 2.5 自动补全

输入 `/` 后显示命令列表：

```
> /
  /index     索引项目
  /query     精确查询
  /show      查看符号详情
  /graph     调用图可视化
  /callers   查看调用者
  /callees   查看被调用者
  /rca       根因分析
  /stats     索引统计
  /clear     清除索引
  /config    查看/修改配置
  /help      显示帮助
  /quit      退出
```

## 三、技术实现

### 3.1 文件结构

```
src/repomind/cli/
├── __init__.py
├── main.py              # 入口点
├── app.py               # Typer 应用定义
├── repl.py              # REPL 主循环
├── commands/
│   ├── __init__.py
│   ├── index.py         # /index 命令
│   ├── query.py         # /query 命令
│   ├── show.py          # /show 命令
│   ├── graph.py         # /graph 命令
│   ├── callers.py       # /callers 命令
│   ├── callees.py       # /callees 命令
│   ├── rca.py           # /rca 命令
│   ├── stats.py         # /stats 命令
│   └── config.py        # /config 命令
├── components/
│   ├── __init__.py
│   ├── banner.py        # 启动横幅
│   ├── prompt.py        # 输入提示符
│   ├── progress.py      # 进度指示器
│   ├── table.py         # 表格组件
│   ├── tree.py          # 树形组件
│   ├── panel.py         # 面板组件
│   └── syntax.py        # 代码高亮
├── themes/
│   ├── __init__.py
│   └── repomind.py      # 自定义主题
└── utils/
    ├── __init__.py
    ├── completer.py     # 自动补全
    └── history.py       # 命令历史
```

### 3.2 核心依赖

```toml
# pyproject.toml
dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "prompt_toolkit>=3.0.0",  # 新增：命令行交互
    "pygments>=2.0.0",        # 新增：语法高亮
]
```

### 3.3 REPL 核心代码

```python
# src/repomind/cli/repl.py
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.theme import Theme

class RepoMindREPL:
    def __init__(self, project_path: Path):
        self.project = project_path
        self.console = Console(theme=REPOIND_THEME)
        self.session = PromptSession(
            history=FileHistory('.repomind/history'),
            completer=self._create_completer(),
        )
        
    def run(self):
        self._show_banner()
        while True:
            try:
                user_input = self.session.prompt(
                    "\n> ",
                    multiline=False,
                )
                self._handle_input(user_input)
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
    
    def _handle_input(self, text: str):
        text = text.strip()
        if not text:
            return
        
        if text.startswith('/'):
            self._handle_command(text)
        else:
            self._handle_query(text)
    
    def _handle_command(self, text: str):
        cmd, *args = text.split(maxsplit=1)
        cmd = cmd.lower()
        arg = args[0] if args else ""
        
        commands = {
            '/index': self._cmd_index,
            '/i': self._cmd_index,
            '/query': self._cmd_query,
            '/q': self._cmd_query,
            '/show': self._cmd_show,
            '/s': self._cmd_show,
            '/graph': self._cmd_graph,
            '/g': self._cmd_graph,
            '/help': self._cmd_help,
            '/?': self._cmd_help,
            '/quit': self._cmd_quit,
            '/exit': self._cmd_quit,
        }
        
        handler = commands.get(cmd)
        if handler:
            handler(arg)
        else:
            self.console.print(f"[red]未知命令: {cmd}[/]")
            self.console.print("输入 [cyan]/help[/] 查看可用命令")
    
    def _handle_query(self, query: str):
        """处理自然语言查询"""
        with self.console.status("[bold blue]正在查询..."):
            results = self.query_service.search(query)
        self._display_results(query, results)
```

### 3.4 命令注册

```python
# src/repomind/cli/commands/__init__.py
from typing import Protocol, Callable

class Command(Protocol):
    """命令协议"""
    name: str
    aliases: list[str]
    description: str
    
    def execute(self, args: str) -> None: ...

class CommandRegistry:
    """命令注册表"""
    def __init__(self):
        self._commands: dict[str, Command] = {}
    
    def register(self, command: Command):
        self._commands[command.name] = command
        for alias in command.aliases:
            self._commands[alias] = command
    
    def get(self, name: str) -> Command | None:
        return self._commands.get(name)
    
    def list_all(self) -> list[Command]:
        seen = set()
        result = []
        for cmd in self._commands.values():
            if cmd.name not in seen:
                seen.add(cmd.name)
                result.append(cmd)
        return result
```

## 四、实施计划

### Phase 1: 基础框架 (1-2天)
- [ ] 创建新的文件结构
- [ ] 实现 REPL 核心循环
- [ ] 实现 `/` 命令解析
- [ ] 添加命令历史

### Phase 2: 命令迁移 (2-3天)
- [ ] 迁移现有命令到新结构
- [ ] 实现命令注册系统
- [ ] 添加命令别名

### Phase 3: UI 美化 (2-3天)
- [ ] 设计自定义主题
- [ ] 实现启动横幅
- [ ] 美化输出组件
- [ ] 添加进度指示器

### Phase 4: 高级功能 (3-5天)
- [ ] 实现自动补全
- [ ] 添加自然语言查询优化
- [ ] 实现流式输出效果
- [ ] 添加快捷键支持

## 五、示例对话

```
╭──────────────────────────────────────────────────────────────────────────────╮
│   ██████╗ ███████╗██████╗  ██████╗ ███╗   ███╗██╗███╗   ██╗██████╗         │
│   ██╔══██╗██╔════╝██╔══██╗██╔═══██╗████╗ ████║██║████╗  ██║██╔══██╗        │
│   ██████╔╝█████╗  ██████╔╝██║   ██║██╔████╔██║██║██╔██╗ ██║██║  ██║        │
│   ██╔══██╗██╔══╝  ██╔═══╝ ██║   ██║██║╚██╔╝██║██║██║╚██╗██║██║  ██║        │
│   ██║  ██║███████╗██║     ╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██████╔╝        │
│   ╚═╝  ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝       │
│                                                                              │
│                    Repository Intelligence Platform                          │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯

  📁 项目: F:\VScode Workspace\Python_workspace\RepoMind
  📊 索引: 4,114 files | 263,004 symbols

> 用户认证流程是怎样的？

╭─ 🔍 查询结果 ─────────────────────────────────────────────────────────────────╮
│                                                                               │
│  找到 8 个相关符号 (0.156s)                                                   │
│                                                                               │
│   1. AuthService (class)                                                      │
│      📄 src/services/auth_service.py:15                                       │
│                                                                               │
│   2. authenticate (method)                                                    │
│      📄 src/services/auth_service.py:25                                       │
│                                                                               │
│   3. verify_token (method)                                                    │
│      📄 src/services/auth_service.py:50                                       │
╰───────────────────────────────────────────────────────────────────────────────╯

> /show AuthService

╭─ 📦 AuthService ──────────────────────────────────────────────────────────────╮
│                                                                               │
│  类型: class | 模块: src.services.auth_service                                │
│  位置: src/services/auth_service.py:15-89                                     │
│                                                                               │
│  📝 处理用户认证和授权的核心服务                                               │
╰───────────────────────────────────────────────────────────────────────────────╯

> /graph AuthService --depth 2

╭─ 🌐 调用图: AuthService ──────────────────────────────────────────────────────╮
│                                                                               │
│                        ┌──────────────┐                                       │
│                        │ AuthService  │                                       │
│                        └──────┬───────┘                                       │
│                               │                                               │
│           ┌───────────────────┼───────────────────┐                           │
│           ▼                   ▼                   ▼                           │
│    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                    │
│    │   Database   │   │   JWT Lib    │   │  Password    │                    │
│    └──────────────┘   └──────────────┘   └──────────────┘                    │
│                                                                               │
╰───────────────────────────────────────────────────────────────────────────────╯

> 帮我找出所有处理支付的类

╭─ 🔍 查询结果 ─────────────────────────────────────────────────────────────────╮
│  找到 5 个相关符号 (0.098s)                                                   │
╰───────────────────────────────────────────────────────────────────────────────╯

> /quit
👋 再见！
```
