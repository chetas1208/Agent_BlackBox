"""Blaxel sandbox adapter — real persistent execution environments."""
from __future__ import annotations

import asyncio
import copy
import json
import time
from uuid import uuid4

from blaxel.core import SandboxInstance

from app.sandbox.base import SandboxAdapter, SandboxResult, SandboxFileInfo


class BlaxelSandbox(SandboxAdapter):
    """
    Uses Blaxel SandboxInstance for real command execution and file I/O.
    Snapshots are implemented by serialising the working-dir file tree and
    storing it in an in-process dict (sufficient for a single-server setup;
    swap for Redis-backed storage in production).
    """

    def __init__(self) -> None:
        self._instances: dict[str, SandboxInstance] = {}
        self._snapshots: dict[str, dict[str, str]] = {}  # snap_id → {path: content}

    # ──────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────

    async def create(self, sandbox_id: str) -> str:
        sandbox = await SandboxInstance.create_if_not_exists({
            "name": sandbox_id,
            "image": "blaxel/py-app:latest",
            "memory": 2048,
            "region": "us-was-1",
            "ttl": "4h",
        })
        self._instances[sandbox_id] = sandbox
        # Ensure working directories exist
        await sandbox.fs.mkdir("/workspace")
        return sandbox_id

    async def _get(self, sandbox_id: str) -> SandboxInstance:
        if sandbox_id not in self._instances:
            self._instances[sandbox_id] = await SandboxInstance.get(sandbox_id)
        return self._instances[sandbox_id]

    async def destroy(self, sandbox_id: str) -> None:
        try:
            sandbox = await self._get(sandbox_id)
            await sandbox.delete()
        except Exception:
            pass
        self._instances.pop(sandbox_id, None)

    async def pause(self, sandbox_id: str) -> None:
        pass  # Blaxel sandboxes auto-pause on idle

    async def resume(self, sandbox_id: str) -> None:
        pass  # Blaxel sandboxes auto-resume

    # ──────────────────────────────────────────────────────────────
    # Command execution
    # ──────────────────────────────────────────────────────────────

    async def execute_command(self, sandbox_id: str, command: str) -> SandboxResult:
        sandbox = await self._get(sandbox_id)
        start = time.monotonic()

        # Write output to a temp file so we can retrieve it
        run_id = uuid4().hex[:8]
        stdout_path = f"/tmp/stdout_{run_id}.txt"
        stderr_path = f"/tmp/stderr_{run_id}.txt"
        exit_path = f"/tmp/exit_{run_id}.txt"

        wrapped = (
            f"sh -c '{command} >{stdout_path} 2>{stderr_path}; "
            f"echo $? >{exit_path}'"
        )

        try:
            await sandbox.process.exec({
                "name": f"cmd-{run_id}",
                "command": wrapped,
                "working_dir": "/workspace",
                "wait_for_completion": True,
                "timeout": 120000,
            })
        except Exception as exc:
            return SandboxResult(
                exit_code=1,
                stderr=str(exc),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        duration_ms = int((time.monotonic() - start) * 1000)

        async def _read_safe(path: str) -> str:
            try:
                return await sandbox.fs.read(path)
            except Exception:
                return ""

        stdout = await _read_safe(stdout_path)
        stderr = await _read_safe(stderr_path)
        exit_raw = await _read_safe(exit_path)

        try:
            exit_code = int(exit_raw.strip())
        except (ValueError, AttributeError):
            exit_code = 0

        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            duration_ms=duration_ms,
        )

    # ──────────────────────────────────────────────────────────────
    # Filesystem
    # ──────────────────────────────────────────────────────────────

    async def read_file(self, sandbox_id: str, path: str) -> str:
        sandbox = await self._get(sandbox_id)
        try:
            return await sandbox.fs.read(f"/workspace/{path.lstrip('/')}")
        except Exception:
            return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        sandbox = await self._get(sandbox_id)
        full_path = f"/workspace/{path.lstrip('/')}"
        # Ensure parent directory exists
        parent = "/".join(full_path.split("/")[:-1])
        if parent and parent != "/workspace":
            try:
                await sandbox.fs.mkdir(parent)
            except Exception:
                pass
        await sandbox.fs.write(full_path, content)

    async def list_files(self, sandbox_id: str) -> list[SandboxFileInfo]:
        sandbox = await self._get(sandbox_id)
        try:
            listing = await sandbox.fs.ls("/workspace")
            files: list[SandboxFileInfo] = []
            for f in listing.files:
                try:
                    content = await sandbox.fs.read(f"/workspace/{f}")
                    files.append(SandboxFileInfo(path=f, content=content, size=len(content)))
                except Exception:
                    files.append(SandboxFileInfo(path=f, content="", size=0))
            return files
        except Exception:
            return []

    # ──────────────────────────────────────────────────────────────
    # Snapshot / Restore
    # ──────────────────────────────────────────────────────────────

    async def snapshot(self, sandbox_id: str) -> str:
        """Capture all /workspace files into an in-memory dict."""
        sandbox = await self._get(sandbox_id)
        snap_id = uuid4().hex[:12]
        try:
            file_map: dict[str, str] = {}
            results = await sandbox.fs.find("/workspace", type="file", max_results=500)
            paths = [r.path for r in results] if hasattr(results, "__iter__") else []
            await asyncio.gather(*[
                self._capture_file(sandbox, path, file_map) for path in paths
            ])
            self._snapshots[snap_id] = copy.deepcopy(file_map)
        except Exception:
            self._snapshots[snap_id] = {}
        return snap_id

    async def _capture_file(self, sandbox: SandboxInstance, path: str, dest: dict) -> None:
        try:
            dest[path] = await sandbox.fs.read(path)
        except Exception:
            pass

    async def restore(self, sandbox_id: str, snapshot_ref: str) -> None:
        """Restore /workspace from a previously taken snapshot."""
        if snapshot_ref not in self._snapshots:
            return
        sandbox = await self._get(sandbox_id)
        file_map = self._snapshots[snapshot_ref]
        await asyncio.gather(*[
            sandbox.fs.write(path, content)
            for path, content in file_map.items()
        ])
