from __future__ import annotations
from app.sandbox.base import SandboxAdapter, SandboxResult, SandboxFileInfo
from app.sandbox.local_mock import LocalMockSandbox

_adapters: dict[str, SandboxAdapter] = {}


def get_sandbox_adapter(profile: str = "local_mock") -> SandboxAdapter:
    if profile not in _adapters:
        if profile == "local_mock":
            _adapters[profile] = LocalMockSandbox()
        elif profile == "blaxel":
            from app.sandbox.blaxel_adapter import BlaxelSandboxAdapter
            _adapters[profile] = BlaxelSandboxAdapter()
        else:
            _adapters[profile] = LocalMockSandbox()
    return _adapters[profile]


class SandboxService:
    def __init__(self, adapter: SandboxAdapter | None = None, default_profile: str = "local_mock"):
        self.adapter = adapter
        self.default_profile = default_profile

    def _adapter(self, profile: str | None = None) -> SandboxAdapter:
        return self.adapter or get_sandbox_adapter(profile or self.default_profile)

    async def create(self, sandbox_id: str, profile: str | None = None) -> str:
        return await self._adapter(profile).create(sandbox_id)

    async def execute(
        self,
        sandbox_id: str,
        command: str,
        profile: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
    ) -> SandboxResult:
        return await self._adapter(profile).execute_command(
            sandbox_id,
            command,
            working_dir=working_dir,
            timeout_ms=timeout_ms,
        )

    async def read_file(self, sandbox_id: str, path: str, profile: str | None = None) -> str:
        return await self._adapter(profile).read_file(sandbox_id, path)

    async def write_file(self, sandbox_id: str, path: str, content: str, profile: str | None = None) -> None:
        await self._adapter(profile).write_file(sandbox_id, path, content)

    async def snapshot(self, sandbox_id: str, profile: str | None = None) -> str:
        return await self._adapter(profile).snapshot(sandbox_id)

    async def restore(self, sandbox_id: str, snapshot_ref: str, profile: str | None = None) -> None:
        await self._adapter(profile).restore(sandbox_id, snapshot_ref)

    async def list_files(self, sandbox_id: str, profile: str | None = None) -> list[SandboxFileInfo]:
        return await self._adapter(profile).list_files(sandbox_id)

    async def destroy(self, sandbox_id: str, profile: str | None = None) -> None:
        await self._adapter(profile).destroy(sandbox_id)
