from __future__ import annotations
from abc import ABC, abstractmethod
from pydantic import BaseModel


class SandboxResult(BaseModel):
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0


class SandboxFileInfo(BaseModel):
    path: str
    content: str = ""
    size: int = 0


class SandboxAdapter(ABC):
    @abstractmethod
    async def create(self, sandbox_id: str) -> str:
        ...

    @abstractmethod
    async def execute_command(self, sandbox_id: str, command: str) -> SandboxResult:
        ...

    @abstractmethod
    async def read_file(self, sandbox_id: str, path: str) -> str:
        ...

    @abstractmethod
    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        ...

    @abstractmethod
    async def snapshot(self, sandbox_id: str) -> str:
        ...

    @abstractmethod
    async def restore(self, sandbox_id: str, snapshot_ref: str) -> None:
        ...

    @abstractmethod
    async def pause(self, sandbox_id: str) -> None:
        ...

    @abstractmethod
    async def resume(self, sandbox_id: str) -> None:
        ...

    @abstractmethod
    async def destroy(self, sandbox_id: str) -> None:
        ...

    @abstractmethod
    async def list_files(self, sandbox_id: str) -> list[SandboxFileInfo]:
        ...
