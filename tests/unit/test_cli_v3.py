"""Tests for project registry and prompt utilities."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from rich.console import Console

from repomind.cli.components.banner import show_banner
from repomind.cli.projects import ProjectRegistry, ProjectEntry
from repomind.cli.prompt_utils import (
    _levenshtein,
    suggest_command,
    CommandCompleter,
    prompt_string,
)
from repomind.cli.repl import RepoMindREPL
from repomind.cli.themes import REPOIND_THEME


def capture_console(width: int = 100) -> tuple[Console, StringIO]:
    """Create a deterministic Rich console for text assertions."""
    stream = StringIO()
    console = Console(
        file=stream,
        width=width,
        color_system=None,
        force_terminal=False,
        theme=REPOIND_THEME,
    )
    return console, stream


class TestStartupBanner:
    def test_indexed_banner_shows_brand_workspace_and_stats(self, tmp_path: Path):
        console, stream = capture_console()

        show_banner(
            console,
            tmp_path,
            stats={"files": 42, "symbols": 318, "classes": 12},
            project_name="RepoMind",
        )

        output = stream.getvalue()
        assert "RepoMind" in output
        assert "WORKSPACE" in output
        assert "index ready" in output
        assert "42 files" in output
        assert "318 symbols" in output

    def test_unindexed_banner_guides_user_to_index(self, tmp_path: Path):
        console, stream = capture_console()

        show_banner(console, tmp_path, stats=None, project_name="new-project")

        output = stream.getvalue()
        assert "new-project" in output
        assert "index required" in output
        assert "/index" in output

    def test_banner_renders_in_narrow_terminal(self, tmp_path: Path):
        console, stream = capture_console(width=60)

        show_banner(
            console,
            tmp_path,
            stats={"files": 1_234, "symbols": 56_789, "classes": 321},
            project_name="a-very-long-project-name",
        )

        assert "██" in stream.getvalue()

    def test_banner_is_centered_and_does_not_fill_wide_terminal(self, tmp_path: Path):
        console, stream = capture_console(width=100)

        show_banner(
            console,
            tmp_path,
            stats={"files": 42, "symbols": 318, "classes": 12},
            project_name="RepoMind",
        )

        lines = stream.getvalue().splitlines()
        brand_line = next(line for line in lines if "██" in line)
        panel_top = next(line for line in lines if "WORKSPACE" in line)
        assert len(brand_line) - len(brand_line.lstrip()) >= 10
        assert len(panel_top) - len(panel_top.lstrip()) >= 10
        assert len(panel_top.strip()) <= 76


class TestStartupDashboard:
    def test_dashboard_shows_primary_actions(self):
        console, stream = capture_console()
        repl = RepoMindREPL.__new__(RepoMindREPL)
        repl.console = console
        repl._is_indexed = lambda: True

        repl._show_dashboard()

        output = stream.getvalue()
        assert "Start here" in output
        assert "Ask a question" in output
        assert "/index" in output
        assert "/graph" in output
        assert "/help" in output

    def test_dashboard_uses_same_centered_content_column(self):
        console, stream = capture_console(width=100)
        repl = RepoMindREPL.__new__(RepoMindREPL)
        repl.console = console
        repl._is_indexed = lambda: True

        repl._show_dashboard()

        lines = stream.getvalue().splitlines()
        heading = next(line for line in lines if "Start here" in line)
        action = next(line for line in lines if "Ask a question" in line)
        assert len(heading) - len(heading.lstrip()) >= 10
        assert len(action) - len(action.lstrip()) >= 10


class TestProjectEntry:
    def test_default_values(self):
        entry = ProjectEntry(name="myproj", path="/tmp/myproj")
        assert entry.name == "myproj"
        assert entry.path == "/tmp/myproj"
        assert entry.indexed is False
        assert entry.file_count == 0
        assert entry.symbol_count == 0
        assert entry.last_used > 0

    def test_touch_updates_timestamp(self):
        entry = ProjectEntry(name="p", path="/p", last_used=1000)
        old = entry.last_used
        entry.touch()
        assert entry.last_used > old


class TestProjectRegistry:
    def test_add_new_project(self, tmp_path: Path):
        reg = ProjectRegistry(path=tmp_path / "reg.json")
        proj = tmp_path / "myproj"
        proj.mkdir()

        entry = reg.add(proj, indexed=True, file_count=10, symbol_count=100)

        assert entry.name == "myproj"
        assert entry.indexed is True
        assert entry.file_count == 10
        assert entry.symbol_count == 100
        assert len(reg) == 1
        assert proj.resolve() in reg or str(proj.resolve()) in reg._projects

    def test_add_updates_existing(self, tmp_path: Path):
        reg = ProjectRegistry(path=tmp_path / "reg.json")
        proj = tmp_path / "myproj"
        proj.mkdir()

        reg.add(proj, indexed=False)
        reg.add(proj, indexed=True, file_count=5)

        assert len(reg) == 1
        entry = reg.get(proj)
        assert entry is not None
        assert entry.indexed is True
        assert entry.file_count == 5

    def test_remove_project(self, tmp_path: Path):
        reg = ProjectRegistry(path=tmp_path / "reg.json")
        proj = tmp_path / "myproj"
        proj.mkdir()

        reg.add(proj)
        assert len(reg) == 1

        removed = reg.remove(proj)
        assert removed is True
        assert len(reg) == 0

        # Removing again returns False
        assert reg.remove(proj) is False

    def test_list_all_sorted_by_last_used(self, tmp_path: Path):
        reg = ProjectRegistry(path=tmp_path / "reg.json")
        p1 = tmp_path / "p1"
        p2 = tmp_path / "p2"
        p1.mkdir()
        p2.mkdir()

        reg.add(p1)
        reg.add(p2)

        projects = reg.list_all()
        assert len(projects) == 2
        # Most recently used first
        assert projects[0].path == str(p2.resolve())

    def test_find_by_name_case_insensitive(self, tmp_path: Path):
        reg = ProjectRegistry(path=tmp_path / "reg.json")
        proj = tmp_path / "MyProject"
        proj.mkdir()

        reg.add(proj, name="MyProject")

        entry = reg.find_by_name("myproject")
        assert entry is not None
        assert entry.name == "MyProject"

        assert reg.find_by_name("nonexistent") is None

    def test_persistence(self, tmp_path: Path):
        reg_path = tmp_path / "reg.json"
        reg = ProjectRegistry(path=reg_path)
        proj = tmp_path / "myproj"
        proj.mkdir()

        reg.add(proj, indexed=True, file_count=42)

        # New registry instance loads from disk
        reg2 = ProjectRegistry(path=reg_path)
        assert len(reg2) == 1
        entry = reg2.get(proj)
        assert entry is not None
        assert entry.indexed is True
        assert entry.file_count == 42

    def test_corrupt_registry_starts_fresh(self, tmp_path: Path):
        reg_path = tmp_path / "reg.json"
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text("not valid json", encoding="utf-8")

        reg = ProjectRegistry(path=reg_path)
        assert len(reg) == 0

    def test_max_projects_limit(self, tmp_path: Path):
        from repomind.cli.projects import MAX_PROJECTS

        reg = ProjectRegistry(path=tmp_path / "reg.json")
        # Add more than MAX_PROJECTS
        for i in range(MAX_PROJECTS + 5):
            p = tmp_path / f"p{i}"
            p.mkdir()
            reg.add(p)

        # Registry should cap at MAX_PROJECTS on save
        data = json.loads((tmp_path / "reg.json").read_text(encoding="utf-8"))
        assert len(data["projects"]) <= MAX_PROJECTS


class TestLevenshtein:
    def test_identical_strings(self):
        assert _levenshtein("hello", "hello") == 0

    def test_empty_strings(self):
        assert _levenshtein("", "") == 0
        assert _levenshtein("abc", "") == 3
        assert _levenshtein("", "abc") == 3

    def test_one_edit(self):
        assert _levenshtein("cat", "cats") == 1  # insertion
        assert _levenshtein("cats", "cat") == 1  # deletion
        assert _levenshtein("cat", "bat") == 1  # substitution

    def test_multiple_edits(self):
        assert _levenshtein("kitten", "sitting") == 3


class TestSuggestCommand:
    def test_exact_match(self):
        cmds = ["/index", "/query", "/show"]
        assert suggest_command("/index", cmds) == "/index"

    def test_close_typo(self):
        cmds = ["/index", "/query", "/show"]
        # /indx -> /index (1 edit)
        assert suggest_command("/indx", cmds) == "/index"

    def test_no_match_for_non_slash(self):
        cmds = ["/index", "/query"]
        # Non-slash input returns None
        assert suggest_command("index", cmds) is None

    def test_no_match_too_far(self):
        cmds = ["/index", "/query"]
        # /xyz is too far from any command
        assert suggest_command("/xyz", cmds) is None

    def test_case_insensitive(self):
        cmds = ["/Index", "/Query"]
        assert suggest_command("/index", cmds) == "/Index"


class TestCommandCompleter:
    def test_completes_slash_commands(self):
        from prompt_toolkit.document import Document

        completer = CommandCompleter(["/index", "/query", "/quit"])
        doc = Document("/in")
        completions = list(completer.get_completions(doc, None))
        assert len(completions) == 1
        assert completions[0].text == "/index"

    def test_no_completion_for_non_slash(self):
        from prompt_toolkit.document import Document

        completer = CommandCompleter(["/index"])
        doc = Document("index")
        completions = list(completer.get_completions(doc, None))
        assert len(completions) == 0

    def test_no_completion_after_space(self):
        from prompt_toolkit.document import Document

        completer = CommandCompleter(["/index"])
        doc = Document("/index arg")
        completions = list(completer.get_completions(doc, None))
        assert len(completions) == 0


class TestPromptString:
    def test_indexed_prompt(self):
        s = prompt_string("myproject", indexed=True)
        assert "myproject" in s
        assert "●" in s
        assert ">" in s

    def test_not_indexed_prompt(self):
        s = prompt_string("myproject", indexed=False)
        assert "myproject" in s
        assert "○" in s
        assert ">" in s
