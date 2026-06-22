"""RepoMind custom theme for Rich."""

from rich.theme import Theme

REPOIND_THEME = Theme(
    {
        # Brand and startup surface
        "brand": "bold bright_cyan",
        "tagline": "italic grey70",
        "muted": "grey58",
        "workspace.name": "bold white",
        "workspace.path": "grey66",
        "status.ready": "bold green",
        "status.pending": "bold yellow",
        "command": "bold bright_cyan",
        "panel.title": "bold bright_cyan",
        "panel.border": "grey35",
        # Base colors
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        # Commands
        "cmd": "bold cyan",
        "cmd.arg": "cyan",
        "cmd.desc": "dim white",
        # Symbol types
        "symbol.class": "bold cyan",
        "symbol.function": "bold green",
        "symbol.method": "bold yellow",
        "symbol.variable": "white",
        "symbol.module": "dim cyan",
        # Code
        "code.file": "dim white",
        "code.line": "dim cyan",
        "code.snippet": "white",
        # Query
        "query.text": "bold white",
        "query.count": "bold cyan",
        "query.time": "dim cyan",
        # Graph
        "graph.node": "bold cyan",
        "graph.edge": "dim white",
        "graph.stats": "dim cyan",
        # RCA
        "rca.error": "bold red",
        "rca.location": "cyan",
        "rca.confidence": "bold yellow",
        "rca.suggestion": "green",
        # Prompt
        "prompt": "bold green",
        "prompt.char": "green",
    }
)
