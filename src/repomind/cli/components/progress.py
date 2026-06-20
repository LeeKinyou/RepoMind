"""Progress indicator component for RepoMind CLI."""
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from contextlib import contextmanager


@contextmanager
def show_progress(console: Console, description: str = "处理中..."):
    """显示进度指示器。

    Args:
        console: Rich 控制台实例
        description: 进度描述

    Yields:
        Progress 对象，可用于更新进度
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(description, total=None)
        yield progress


@contextmanager
def show_spinner(console: Console, message: str = "处理中..."):
    """显示简单的旋转动画。

    Args:
        console: Rich 控制台实例
        message: 显示消息

    Yields:
        None
    """
    with console.status(f"[bold blue]{message}"):
        yield
