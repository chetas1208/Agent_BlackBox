"""Mock sandbox for development and demos.

Simulates a local filesystem sandbox with command execution, file I/O,
snapshots, and restore. All state is held in memory.
"""
from __future__ import annotations

import asyncio
import random
import copy
from datetime import datetime
from uuid import uuid4
from app.sandbox.base import SandboxAdapter, SandboxResult, SandboxFileInfo

SIMULATED_COMMANDS: dict[str, tuple[int, str, str]] = {
    "pytest tests/": (0, "===== 4 passed in 1.23s =====", ""),
    "pytest tests/ --failing": (1, "", "FAILED tests/test_auth.py::test_login - AssertionError"),
    "git status": (0, "On branch main\nnothing to commit, working tree clean", ""),
    "git log --oneline -5": (0, "a1b2c3d Fix auth module\ne4f5g6h Add retry logic\ni7j8k9l Initial commit", ""),
    "cat README.md": (0, "# Project Alpha\n\nA sample project for debugging.", ""),
    "grep -r 'TODO' src/": (0, "src/auth.py:12: # TODO: fix token refresh\nsrc/api.py:45: # TODO: add rate limiting", ""),
    "python -c 'print(1+1)'": (0, "2", ""),
    "ls -la": (0, "total 48\ndrwxr-xr-x  8 user staff  256 Jan 1 00:00 .\n-rw-r--r--  1 user staff  1024 Jan 1 00:00 README.md\ndrwxr-xr-x  4 user staff  128 Jan 1 00:00 src\ndrwxr-xr-x  3 user staff   96 Jan 1 00:00 tests", ""),
    "pip install -r requirements.txt": (0, "Successfully installed all packages", ""),
    "flake8 src/": (0, "src/auth.py:15:1: E302 expected 2 blank lines\nsrc/api.py:8:80: E501 line too long", ""),
}


class LocalMockSandbox(SandboxAdapter):
    def __init__(self):
        self._sandboxes: dict[str, dict] = {}

    async def create(self, sandbox_id: str) -> str:
        self._sandboxes[sandbox_id] = {
            "files": {
                "README.md": "# Project Alpha\n\nA sample project for debugging.",
                "src/auth.py": "def login(user, password):\n    # TODO: fix token refresh\n    token = generate_token(user)\n    return token\n",
                "src/api.py": "from flask import Flask\napp = Flask(__name__)\n\n@app.route('/health')\ndef health():\n    return {'status': 'ok'}\n",
                "tests/test_auth.py": "def test_login():\n    result = login('user', 'pass')\n    assert result is not None\n",
                "requirements.txt": "flask==3.0.0\npytest==7.4.0\n",
            },
            "snapshots": {},
            "status": "running",
            "created_at": datetime.utcnow().isoformat(),
        }
        return sandbox_id

    async def execute_command(self, sandbox_id: str, command: str) -> SandboxResult:
        sb = self._sandboxes.get(sandbox_id)
        if not sb:
            return SandboxResult(exit_code=1, stderr="Sandbox not found")

        await asyncio.sleep(random.uniform(0.1, 0.4))

        for pattern, (code, stdout, stderr) in SIMULATED_COMMANDS.items():
            if pattern in command:
                return SandboxResult(
                    exit_code=code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=random.randint(50, 2000),
                )

        return SandboxResult(
            exit_code=0,
            stdout=f"[mock] executed: {command}",
            duration_ms=random.randint(10, 500),
        )

    async def read_file(self, sandbox_id: str, path: str) -> str:
        sb = self._sandboxes.get(sandbox_id, {})
        return sb.get("files", {}).get(path, "")

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        sb = self._sandboxes.get(sandbox_id)
        if sb:
            sb["files"][path] = content

    async def snapshot(self, sandbox_id: str) -> str:
        sb = self._sandboxes.get(sandbox_id)
        if not sb:
            return ""
        snap_id = str(uuid4())[:8]
        sb["snapshots"][snap_id] = copy.deepcopy(sb["files"])
        return snap_id

    async def restore(self, sandbox_id: str, snapshot_ref: str) -> None:
        sb = self._sandboxes.get(sandbox_id)
        if sb and snapshot_ref in sb.get("snapshots", {}):
            sb["files"] = copy.deepcopy(sb["snapshots"][snapshot_ref])

    async def pause(self, sandbox_id: str) -> None:
        sb = self._sandboxes.get(sandbox_id)
        if sb:
            sb["status"] = "paused"

    async def resume(self, sandbox_id: str) -> None:
        sb = self._sandboxes.get(sandbox_id)
        if sb:
            sb["status"] = "running"

    async def destroy(self, sandbox_id: str) -> None:
        self._sandboxes.pop(sandbox_id, None)

    async def list_files(self, sandbox_id: str) -> list[SandboxFileInfo]:
        sb = self._sandboxes.get(sandbox_id, {})
        files = sb.get("files", {})
        return [
            SandboxFileInfo(path=p, content=c, size=len(c))
            for p, c in files.items()
        ]
