from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.sandbox.base import SandboxAdapter, SandboxFileInfo, SandboxResult

logger = logging.getLogger(__name__)

MANAGEMENT_BASE = "https://api.blaxel.ai/v0"


class BlaxelSandboxAdapter(SandboxAdapter):

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        # sandbox_id -> sandbox_name mapping (the name used in URLs)
        self._sandboxes: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _settings(self):
        return get_settings()

    def _headers(self) -> Dict[str, str]:
        s = self._settings()
        return {
            "Authorization": f"Bearer {s.blaxel_api_key}",
            "Content-Type": "application/json",
        }

    def _sandbox_url(self, sandbox_name: str) -> str:
        s = self._settings()
        workspace = s.bl_workspace or ""
        region = s.blaxel_region
        return f"https://sbx-{sandbox_name}-{workspace}.{region}.bl.run"

    def _workspace_ok(self) -> bool:
        s = self._settings()
        if not s.bl_workspace:
            logger.warning("BL_WORKSPACE is not set — skipping Blaxel operation")
            return False
        if not s.blaxel_api_key:
            logger.warning("BLAXEL_API_KEY is not set — skipping Blaxel operation")
            return False
        return True

    async def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        return self._client

    def _error_result(self, command: str, err: Exception) -> SandboxResult:
        return SandboxResult(
            exit_code=1,
            command=command,
            status="error",
            stdout="",
            stderr=str(err),
        )

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def create(self, sandbox_id: str) -> str:
        if not self._workspace_ok():
            return sandbox_id

        s = self._settings()
        client = await self._client_instance()
        url = f"{MANAGEMENT_BASE}/workspaces/{s.bl_workspace}/sandboxes"
        body = {
            "metadata": {"name": sandbox_id},
            "spec": {
                "image": s.blaxel_image,
                "memory": s.blaxel_memory_mb,
                "region": s.blaxel_region,
                "ports": [],
            },
        }

        try:
            resp = await client.post(url, headers=self._headers(), json=body)
            resp.raise_for_status()
            data = resp.json()
            name = data.get("metadata", {}).get("name", sandbox_id)
            self._sandboxes[sandbox_id] = name
            logger.info("Created Blaxel sandbox %s", name)
            return name
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Blaxel create failed (%s): %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("Blaxel create HTTP error: %s", exc)
            raise

    async def destroy(self, sandbox_id: str) -> None:
        if not self._workspace_ok():
            return

        s = self._settings()
        name = self._sandboxes.pop(sandbox_id, sandbox_id)
        client = await self._client_instance()
        url = f"{MANAGEMENT_BASE}/workspaces/{s.bl_workspace}/sandboxes/{name}"

        try:
            resp = await client.delete(url, headers=self._headers())
            resp.raise_for_status()
            logger.info("Destroyed Blaxel sandbox %s", name)
        except httpx.HTTPError as exc:
            logger.error("Blaxel destroy error for %s: %s", name, exc)

    async def pause(self, sandbox_id: str) -> None:
        if not self._workspace_ok():
            return

        name = self._sandboxes.get(sandbox_id, sandbox_id)
        logger.info("Pause requested for sandbox %s (no-op for Blaxel)", name)

    async def resume(self, sandbox_id: str) -> None:
        if not self._workspace_ok():
            return

        name = self._sandboxes.get(sandbox_id, sandbox_id)
        logger.info("Resume requested for sandbox %s (no-op for Blaxel)", name)

    # ------------------------------------------------------------------
    # command execution
    # ------------------------------------------------------------------

    async def execute_command(
        self,
        sandbox_id: str,
        command: str,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
    ) -> SandboxResult:
        if not self._workspace_ok():
            return SandboxResult(
                exit_code=1,
                command=command,
                status="skipped",
                stderr="BL_WORKSPACE not configured",
            )

        name = self._sandboxes.get(sandbox_id, sandbox_id)
        base = self._sandbox_url(name)
        client = await self._client_instance()

        body: Dict[str, Any] = {"command": command}
        if working_dir:
            body["working_dir"] = working_dir
        else:
            body["working_dir"] = "/home/user"

        timeout_sec = (timeout_ms / 1000.0) if timeout_ms else 60.0
        start = time.monotonic()

        try:
            resp = await client.post(
                f"{base}/process",
                headers=self._headers(),
                json=body,
                timeout=httpx.Timeout(timeout_sec),
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            data = resp.json()

            return SandboxResult(
                exit_code=data.get("exit_code", resp.status_code if resp.status_code != 200 else 0),
                command=command,
                status="completed",
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                duration_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            result = self._error_result(command, exc)
            result.duration_ms = elapsed_ms
            return result

    # ------------------------------------------------------------------
    # file operations
    # ------------------------------------------------------------------

    async def read_file(self, sandbox_id: str, path: str) -> str:
        if not self._workspace_ok():
            return ""

        name = self._sandboxes.get(sandbox_id, sandbox_id)
        base = self._sandbox_url(name)
        client = await self._client_instance()

        try:
            resp = await client.get(
                f"{base}/filesystem/read",
                params={"path": path},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            logger.error("read_file error (%s): %s", path, exc)
            return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        if not self._workspace_ok():
            return

        name = self._sandboxes.get(sandbox_id, sandbox_id)
        base = self._sandbox_url(name)
        client = await self._client_instance()

        try:
            resp = await client.post(
                f"{base}/filesystem/write",
                headers=self._headers(),
                json={"path": path, "content": content},
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("write_file error (%s): %s", path, exc)

    async def list_files(self, sandbox_id: str) -> list[SandboxFileInfo]:
        if not self._workspace_ok():
            return []

        name = self._sandboxes.get(sandbox_id, sandbox_id)
        base = self._sandbox_url(name)
        client = await self._client_instance()
        s = self._settings()

        try:
            resp = await client.get(
                f"{base}/filesystem/ls",
                params={"path": "/home/user"},
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

            entries: List[Dict[str, Any]] = data if isinstance(data, list) else data.get("files", [])
            results: list[SandboxFileInfo] = []
            for entry in entries[: s.blaxel_max_list_files]:
                results.append(
                    SandboxFileInfo(
                        path=entry.get("path", entry.get("name", "")),
                        size=entry.get("size", 0),
                    )
                )
            return results
        except Exception as exc:
            logger.error("list_files error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # snapshot / restore
    # ------------------------------------------------------------------

    async def snapshot(self, sandbox_id: str) -> str:
        """Capture the current sandbox state by reading all listed files."""
        if not self._workspace_ok():
            return ""

        ref = f"snap-{uuid.uuid4().hex[:12]}"
        files = await self.list_files(sandbox_id)

        file_data: List[Dict[str, str]] = []
        for f in files:
            content = await self.read_file(sandbox_id, f.path)
            file_data.append({"path": f.path, "content": content})

        name = self._sandboxes.get(sandbox_id, sandbox_id)
        base = self._sandbox_url(name)
        client = await self._client_instance()

        try:
            snapshot_payload = json.dumps(file_data)
            await client.post(
                f"{base}/filesystem/write",
                headers=self._headers(),
                json={
                    "path": f"/tmp/.snapshots/{ref}.json",
                    "content": snapshot_payload,
                },
            )
            logger.info("Snapshot %s saved for sandbox %s (%d files)", ref, sandbox_id, len(file_data))
        except Exception as exc:
            logger.error("snapshot write error: %s", exc)

        return ref

    async def restore(self, sandbox_id: str, snapshot_ref: str) -> None:
        """Restore sandbox state from a previously saved snapshot."""
        if not self._workspace_ok():
            return

        name = self._sandboxes.get(sandbox_id, sandbox_id)
        base = self._sandbox_url(name)
        client = await self._client_instance()

        try:
            resp = await client.get(
                f"{base}/filesystem/read",
                params={"path": f"/tmp/.snapshots/{snapshot_ref}.json"},
                headers=self._headers(),
            )
            resp.raise_for_status()
            file_data: List[Dict[str, str]] = json.loads(resp.text)

            for entry in file_data:
                await self.write_file(sandbox_id, entry["path"], entry["content"])

            logger.info(
                "Restored snapshot %s for sandbox %s (%d files)",
                snapshot_ref,
                sandbox_id,
                len(file_data),
            )
        except Exception as exc:
            logger.error("restore error for %s: %s", snapshot_ref, exc)
