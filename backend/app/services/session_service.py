from __future__ import annotations
from datetime import datetime
from app.models.session import Session, SessionStatus, SessionStage
from app.schemas.session import CreateSessionRequest, SessionSummary
from app.repositories.redis_repo import RedisRepository

NS = "sessions"


class SessionService:
    def __init__(self, repo: RedisRepository):
        self.repo = repo

    async def create(self, req: CreateSessionRequest) -> Session:
        session = Session(
            title=req.title,
            description=req.description,
            goal=req.goal,
            task_type=req.task_type,
            auto_checkpoint=req.auto_checkpoint,
            safety_policy=req.safety_policy,
            memory_strategy=req.memory_strategy,
        )
        await self.repo.save_model(NS, session.id, session)
        return session

    async def get(self, session_id: str) -> Session | None:
        return await self.repo.get_model(NS, session_id, Session)

    async def list_all(self) -> list[Session]:
        sessions = await self.repo.list_models(NS, Session)
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    async def update(self, session: Session) -> Session:
        session.updated_at = datetime.utcnow()
        await self.repo.save_model(NS, session.id, session)
        return session

    async def start(self, session_id: str) -> Session | None:
        s = await self.get(session_id)
        if not s:
            return None
        s.status = SessionStatus.RUNNING
        s.stage = SessionStage.PLANNING
        s.started_at = datetime.utcnow()
        return await self.update(s)

    async def pause(self, session_id: str) -> Session | None:
        s = await self.get(session_id)
        if not s:
            return None
        s.status = SessionStatus.PAUSED
        s.stage = SessionStage.IDLE
        return await self.update(s)

    async def resume(self, session_id: str) -> Session | None:
        s = await self.get(session_id)
        if not s:
            return None
        s.status = SessionStatus.RUNNING
        s.stage = SessionStage.EXECUTING
        return await self.update(s)

    async def cancel(self, session_id: str) -> Session | None:
        s = await self.get(session_id)
        if not s:
            return None
        s.status = SessionStatus.CANCELLED
        s.stage = SessionStage.IDLE
        s.ended_at = datetime.utcnow()
        return await self.update(s)

    async def summary(self) -> SessionSummary:
        sessions = await self.list_all()
        return SessionSummary(
            total=len(sessions),
            active=sum(1 for s in sessions if s.status == SessionStatus.RUNNING),
            paused=sum(1 for s in sessions if s.status == SessionStatus.PAUSED),
            failed=sum(1 for s in sessions if s.status == SessionStatus.FAILED),
            completed=sum(1 for s in sessions if s.status == SessionStatus.COMPLETED),
            recovered=sum(1 for s in sessions if s.status == SessionStatus.RECOVERED),
        )
