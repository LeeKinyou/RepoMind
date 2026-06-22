"""Tests for SandboxExecutor."""

from __future__ import annotations

from repomind.sandbox.executor import SandboxExecutor


class TestSandboxExecutorSubprocess:
    def test_run_python_code_success(self):
        executor = SandboxExecutor(mode="subprocess", timeout=5)
        code = "print('hello from sandbox')"
        result = executor.run_python_code(code)
        assert result.success is True
        assert result.exit_code == 0
        assert "hello from sandbox" in result.stdout.strip()

    def test_run_python_code_error(self):
        executor = SandboxExecutor(mode="subprocess", timeout=5)
        code = "raise ValueError('oops')"
        result = executor.run_python_code(code)
        assert result.success is False
        assert result.exit_code != 0
        assert "ValueError: oops" in result.stderr

    def test_run_command_success(self):
        executor = SandboxExecutor(mode="subprocess", timeout=5)
        # Using a universal command available in python env
        result = executor.run_command(
            ["python", "-c", "import sys; print(sys.version)"]
        )
        assert result.success is True
        assert result.exit_code == 0
        assert len(result.stdout) > 0

    def test_timeout_expired(self):
        executor = SandboxExecutor(mode="subprocess", timeout=1)
        code = "import time; time.sleep(3)"
        result = executor.run_python_code(code)
        assert result.success is False
        assert result.exit_code == -1
        assert "Timeout expired" in result.error_message


class TestSandboxExecutorDockerFallback:
    def test_docker_fallback_when_docker_missing(self, monkeypatch):
        # Force docker command to fail to trigger fallback
        import subprocess

        original_run = subprocess.run

        def mock_run(cmd, *args, **kwargs):
            if cmd[0] == "docker" and cmd[1] == "--version":
                raise FileNotFoundError("docker command not found")
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)

        executor = SandboxExecutor(mode="docker", timeout=5)
        code = "print('docker fallback works')"
        result = executor.run_python_code(code)
        assert result.success is True
        assert "docker fallback works" in result.stdout.strip()
