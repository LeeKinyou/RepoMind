"""Sandbox executor for safe code execution."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SandboxResult(BaseModel):
    """Result of sandbox execution."""

    success: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0
    error_message: str | None = None


class SandboxExecutor:
    """Safely executes code or commands within a sandboxed environment (Docker or Subprocess)."""

    def __init__(self, mode: str = "docker", timeout: int = 60):
        self.mode = mode
        self.timeout = timeout

    def run_python_code(self, code_str: str) -> SandboxResult:
        """Write Python code to a temp file and execute it in the sandbox."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "run.py"
            file_path.write_text(code_str, encoding="utf-8")

            if self.mode == "docker":
                return self._run_docker("python /sandbox/run.py", mount_path=tmp_dir)
            else:
                return self._run_subprocess(["python", str(file_path)])

    def run_command(self, cmd: list[str], cwd: str | None = None) -> SandboxResult:
        """Run a command directly in the sandbox."""
        if self.mode == "docker":
            workspace = cwd or os.getcwd()
            return self._run_docker(" ".join(cmd), mount_path=workspace)
        else:
            return self._run_subprocess(cmd, cwd=cwd)

    def _run_subprocess(self, cmd: list[str], cwd: str | None = None) -> SandboxResult:
        """Execute command in an isolated local subprocess with strict timeout."""
        start_time = time.time()
        # Clean environment variables to prevent leakage of credentials
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        }
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                env=safe_env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            elapsed = time.time() - start_time
            return SandboxResult(
                success=(res.returncode == 0),
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                elapsed_seconds=round(elapsed, 2),
            )
        except subprocess.TimeoutExpired as e:
            elapsed = time.time() - start_time
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                elapsed_seconds=round(elapsed, 2),
                error_message=f"Timeout expired after {self.timeout} seconds",
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return SandboxResult(
                success=False,
                exit_code=-2,
                elapsed_seconds=round(elapsed, 2),
                error_message=f"Subprocess execution failed: {e}",
            )

    def _run_docker(self, command_str: str, mount_path: str) -> SandboxResult:
        """Execute command in a Docker container with resource constraints and no network."""
        # Check if Docker is available
        try:
            subprocess.run(["docker", "--version"], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning(
                "Docker daemon is not available. Falling back to subprocess sandbox."
            )
            # Graceful fallback to subprocess mode
            if "/sandbox/run.py" in command_str:
                local_file = Path(mount_path) / "run.py"
                return self._run_subprocess(["python", str(local_file)])
            import shlex

            cmd_parts = shlex.split(command_str.replace("/sandbox/", ""))
            return self._run_subprocess(cmd_parts, cwd=mount_path)

        start_time = time.time()
        container_name = f"repomind_sandbox_{int(time.time())}"
        abs_mount = os.path.abspath(mount_path)
        docker_cmd = [
            "docker",
            "run",
            "--name",
            container_name,
            "--network",
            "none",
            "-v",
            f"{abs_mount}:/sandbox:ro",
            "--cpus",
            "1.0",
            "--memory",
            "512m",
            "--workdir",
            "/sandbox",
            "python:3.10-slim",
            "sh",
            "-c",
            command_str,
        ]

        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            elapsed = time.time() - start_time
            return SandboxResult(
                success=(res.returncode == 0),
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                elapsed_seconds=round(elapsed, 2),
            )
        except subprocess.TimeoutExpired:
            # Kill the container if it timed out
            subprocess.run(["docker", "kill", container_name], capture_output=True)
            elapsed = time.time() - start_time
            return SandboxResult(
                success=False,
                exit_code=-1,
                elapsed_seconds=round(elapsed, 2),
                error_message=f"Docker execution timed out after {self.timeout} seconds",
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return SandboxResult(
                success=False,
                exit_code=-2,
                elapsed_seconds=round(elapsed, 2),
                error_message=f"Docker sandbox failure: {e}",
            )
