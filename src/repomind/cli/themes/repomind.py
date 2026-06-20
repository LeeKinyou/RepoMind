"""RepoMind custom theme for Rich."""
from rich.theme import Theme

REPOIND_THEME = Theme({
    # 基础颜色
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",

    # 命令相关
    "cmd": "bold cyan",
    "cmd.arg": "cyan",
    "cmd.desc": "dim white",

    # 符号类型
    "symbol.class": "bold cyan",
    "symbol.function": "bold green",
    "symbol.method": "bold yellow",
    "symbol.variable": "white",
    "symbol.module": "dim cyan",

    # 代码相关
    "code.file": "dim white",
    "code.line": "dim cyan",
    "code.snippet": "white",

    # 查询相关
    "query.text": "bold white",
    "query.count": "bold cyan",
    "query.time": "dim cyan",

    # 图相关
    "graph.node": "bold cyan",
    "graph.edge": "dim white",
    "graph.stats": "dim cyan",

    # RCA 相关
    "rca.error": "bold red",
    "rca.location": "cyan",
    "rca.confidence": "bold yellow",
    "rca.suggestion": "green",

    # 提示符
    "prompt": "bold green",
    "prompt.char": "green",
})
