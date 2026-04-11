from __future__ import annotations

import copy
from typing import Any

from app.core.config import get_settings
from app.sandbox.base import SandboxAdapter, SandboxFileInfo, SandboxResult


class BlaxelSandboxAdapter(SandboxAdapter):
    """Thin adapter around the official Blaxel Python SDK.

    The SDK is imported lazily so local tests can run without the package installed.
    We defensively resolve both snake_case and camelCase variants used across docs/examples.
    """

    def __init__(self):
        self.settings = get_settings()
        self._snapshots: dict[str, dict[str, dict[str, str]]] = {}

    def _import_sdk(self):
        try:
            from blaxel.core import SandboxInstance  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on local env
            raise RuntimeError("The 'blaxel' package is required for real sandbox execution") from exc
        return SandboxInstance

    def _resolve_attr(self, obj: Any, *names: str) -> Any:
        for name in names:
            if hasattr(obj, name):
                return getattr(obj, name)
        raise AttributeError(f"Object {obj!r} does not expose any of {names!r}")

    async def _get_sandbox(self, sandbox_id: str):
        SandboxInstance = self._import_sdk()
        get_fn = self._resolve_attr(SandboxInstance, "get")
        return await get_fn(sandbox_id)

    async def create(self, sandbox_id: str) -> str:
        SandboxInstance = self._import_sdk()
        create_fn = self._resolve_attr(SandboxInstance, "create_if_not_exists", "createIfNotExists")
        await create_fn({
            "name": sandbox_id,
            "image": self.settings.blaxel_image,
            "memory": self.settings.blaxel_memory_mb,
            "region": self.settings.blaxel_region,
            "labels": {
                "app": "agent-black-box",
                "session": sandbox_id,
            },
        })
        return sandbox_id

    async def execute_command(
        self,
        sandbox_id: str,
        command: str,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
    ) -> SandboxResult:
        sandbox = await self._get_sandbox(sandbox_id)
        exec_fn = self._resolve_attr(sandbox.process, "exec")
        process = await exec_fn({
            "command": command,
            "workingDir": working_dir,
            "waitForCompletion": True,
            "timeout": min(timeout_ms or self.settings.command_timeout_ms, 60000),
        })
        logs = getattr(process, "logs", "") or ""
        exit_code = getattr(process, "exitCode", 0) or 0
        status = getattr(process, "status", "completed" if exit_code == 0 else "failed")
        stderr = logs if exit_code != 0 else ""
        stdout = logs if exit_code == 0 else ""
        return SandboxResult(
            exit_code=exit_code,
            command=command,
            status=status,
            stdout=stdout,
            stderr=stderr,
            duration_ms=min(timeout_ms or self.settings.command_timeout_ms, 60000),
        )

    async def read_file(self, sandbox_id: str, path: str) -> str:
        sandbox = await self._get_sandbox(sandbox_id)
        read_fn = self._resolve_attr(sandbox.fs, "read")
        return await read_fn(path)

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        sandbox = await self._get_sandbox(sandbox_id)
        write_fn = self._resolve_attr(sandbox.fs, "write")
        await write_fn(path, content)

    async def snapshot(self, sandbox_id: str) -> str:
        sandbox = await self._get_sandbox(sandbox_id)
        find_fn = self._resolve_attr(sandbox.fs, "find")
        read_fn = self._resolve_attr(sandbox.fs, "read")
        result = await find_fn("/", {"type": "file", "maxResults": self.settings.blaxel_max_list_files})
        matches = getattr(result, "matches", None) or result.get("matches", [])
        snapshot_ref = f"snap-{len(self._snapshots.get(sandbox_id, {})) + 1}"
        files: dict[str, str] = {}
        for match in matches:
            path = getattr(match, "path", None) or match.get("path")
            if not path:
                continue
            try:
                files[path] = await read_fn(path)
            except Exception:
                continue
        self._snapshots.setdefault(sandbox_id, {})[snapshot_ref] = copy.deepcopy(files)
        return snapshot_ref

    async def restore(self, sandbox_id: str, snapshot_ref: str) -> None:
        snapshot = self._snapshots.get(sandbox_id, {}).get(snapshot_ref)
        if not snapshot:
            return
        sandbox = await self._get_sandbox(sandbox_id)
        write_fn = self._resolve_attr(sandbox.fs, "write")
        for path, content in snapshot.items():
            await write_fn(path, content)

    async def pause(self, sandbox_id: str) -> None:
        return None

    async def resume(self, sandbox_id: str) -> None:
        return None

    async def destroy(self, sandbox_id: str) -> None:
        try:
            sandbox = await self._get_sandbox(sandbox_id)
            delete_fn = self._resolve_attr(sandbox, "delete")
            await delete_fn()
        except Exception:
            SandboxInstance = self._import_sdk()
            delete_fn = self._resolve_attr(SandboxInstance, "delete")
            await delete_fn(sandbox_id)

    async def list_files(self, sandbox_id: str) -> list[SandboxFileInfo]:
        sandbox = await self._get_sandbox(sandbox_id)
        find_fn = self._resolve_attr(sandbox.fs, "find")
        read_fn = self._resolve_attr(sandbox.fs, "read")
        result = await find_fn("/", {"type": "file", "maxResults": self.settings.blaxel_max_list_files})
        matches = getattr(result, "matches", None) or result.get("matches", [])
        files: list[SandboxFileInfo] = []
        for match in matches:
            path = getattr(match, "path", None) or match.get("path")
            if not path:
                continue
            try:
                content = await read_fn(path)
            except Exception:
                content = ""
            files.append(SandboxFileInfo(path=path, content=content[: self.settings.max_artifact_preview_chars], size=len(content)))
        return files
