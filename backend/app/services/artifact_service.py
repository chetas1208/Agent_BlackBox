from __future__ import annotations

from app.models.artifact import Artifact, ArtifactType
from app.repositories.redis_repo import RedisRepository

NS = "artifacts"


class ArtifactService:
    def __init__(self, repo: RedisRepository):
        self.repo = repo

    def _ns(self, session_id: str) -> str:
        return f"{NS}:{session_id}"

    async def create(
        self,
        session_id: str,
        artifact_type: ArtifactType,
        title: str,
        content: str,
        path: str | None = None,
        metadata: dict | None = None,
        content_type: str = "text/plain",
    ) -> Artifact:
        artifact = Artifact(
            session_id=session_id,
            artifact_type=artifact_type,
            title=title,
            content=content,
            path=path,
            metadata=metadata or {},
            content_type=content_type,
        )
        await self.repo.save_model(self._ns(session_id), artifact.id, artifact)
        return artifact

    async def list_by_session(self, session_id: str) -> list[Artifact]:
        artifacts = await self.repo.list_models(self._ns(session_id), Artifact)
        artifacts.sort(key=lambda item: item.created_at, reverse=True)
        return artifacts
