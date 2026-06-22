"""Prompt utilities for RepoMind CLI.

Provides a context-aware prompt with:
- Tab completion for slash commands
- Command history (persisted to disk)
- Fuzzy command correction for typos
- Dynamic prompt text showing project name and index status
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.text import Text


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings.

    Args:
        a: First string
        b: Second string

    Returns:
        Edit distance (number of insertions/deletions/substitutions)
    """
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            insert = prev[j + 1] + 1
            delete = curr[j] + 1
            substitute = prev[j] + (ca != cb)
            curr.append(min(insert, delete, substitute))
        prev = curr
    return prev[-1]


def suggest_command(typed: str, valid_commands: Iterable[str]) -> Optional[str]:
    """Suggest the closest matching command for a typo.

    Args:
        typed: The mistyped command (e.g. "/idx")
        valid_commands: Iterable of valid command names (e.g. ["/index", "/query", ...])

    Returns:
        The closest matching command, or None if no good match found.
        A "good" match has edit distance <= 2 and is shorter than 8 chars,
        or distance <= 3 for longer commands.
    """
    if not typed.startswith("/"):
        return None
    best_match: Optional[str] = None
    best_distance = 999
    for cmd in valid_commands:
        distance = _levenshtein(typed.lower(), cmd.lower())
        # Tighter threshold for short commands
        threshold = 2 if len(cmd) <= 6 else 3
        if distance <= threshold and distance < best_distance:
            best_distance = distance
            best_match = cmd
    return best_match


class CommandCompleter(Completer):
    """Tab completer for slash commands."""

    def __init__(self, commands: list[str]) -> None:
        """Initialize the completer.

        Args:
            commands: List of valid command names (e.g. ["/index", "/query", ...])
        """
        self.commands = sorted(commands)

    def get_completions(self, document, complete_event):
        """Yield completions for the current input."""
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        # Only complete the command part (first word)
        if " " in text:
            return
        for cmd in self.commands:
            if cmd.startswith(text):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                )


def make_prompt_session(
    history_path: Path | None = None,
    commands: list[str] | None = None,
) -> PromptSession:
    """Create a configured PromptSession with history and completion.

    Args:
        history_path: Path to the history file (optional)
        commands: List of valid commands for tab completion

    Returns:
        Configured PromptSession
    """
    history = None
    if history_path is not None:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history = FileHistory(str(history_path))

    completer = CommandCompleter(commands) if commands else None

    style = Style.from_dict(
        {
            "prompt.text": "bold cyan",
            "prompt.char": "green",
        }
    )

    return PromptSession(
        history=history,
        completer=completer,
        style=style,
        complete_while_typing=True,
        enable_history_search=True,
    )


def render_prompt_text(project_name: str, indexed: bool) -> Text:
    """Render the dynamic prompt text showing project context.

    Args:
        project_name: Current project display name
        indexed: Whether the project is indexed

    Returns:
        Rich Text object for the prompt
    """
    text = Text()
    text.append(project_name, style="bold cyan")
    text.append(" ", style="")
    if indexed:
        text.append("●", style="green")
    else:
        text.append("○", style="yellow")
    text.append(" > ", style="green")
    return text


def prompt_string(project_name: str, indexed: bool) -> str:
    """Return a plain-string prompt (for prompt_toolkit).

    prompt_toolkit doesn't render Rich markup directly, so we use
    ANSI-style placeholders that the PromptSession style maps to colors.

    Args:
        project_name: Current project display name
        indexed: Whether the project is indexed

    Returns:
        Prompt string with style class markers
    """
    indicator = "●" if indexed else "○"
    return f"{project_name} {indicator} > "
