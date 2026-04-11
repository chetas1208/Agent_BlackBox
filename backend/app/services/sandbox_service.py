from __future__ import annotations
from app.sandbox.base import SandboxAdapter, SandboxResult, SandboxFileInfo
from app.sandbox.local_mock import LocalMockSandbox

_adapters: dict[str, SandboxAdapter] = {}


def get_sandbox_adapter(profile: str = "local_mock") -> SandboxAdapter:
    if profile not in _adapters:
        if profile == "local_mock":
            _adapters[profile] = LocalMockSandbox()
        else:
            _adapters[profile] = LocalMockSandbox()
    return _adapters[profile]


class SandboxService:
    def __init__(self, adapter: SandboxAdapter | None = None):
        self.adapter = adapter or get_sandbox_adapter()

    async def create(self, sandbox_id: str) -> str:
        return await self.adapter.create(sandbox_id)

    async def execute(self, sandbox_id: str, command: str) -> SandboxResult:
        return await self.adapter.execute_command(sandbox_id, command)

    async def read_file(self, sandbox_id: str, path: str) -> str:
        return await self.adapter.read_file(sandbox_id, path)

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        await self.adapter.write_file(sandbox_id, path, content)

    async def snapshot(self, sandbox_id: str) -> str:
        return await self.adapter.snapshot(sandbox_id)

    async def restore(self, sandbox_id: str, snapshot_ref: str) -> None:
        await self.adapter.restore(sandbox_id, snapshot_ref)

    async def list_files(self, sandbox_id: str) -> list[SandboxFileInfo]:
        return await self.adapter.list_files(sandbox_id)

    async def destroy(self, sandbox_id: str) -> None:
        await self.adapter.destroy(sandbox_id)
