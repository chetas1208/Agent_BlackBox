from __future__ import annotations

from pydantic import BaseModel

from app.models.session import Session
from app.services.execution_guard_service import ExecutionGuardService
from app.services.sandbox_service import SandboxService


class RepoBootstrapResult(BaseModel):
    working_dir: str
    repo_url: str
    repo_ref: str | None = None
    git_status: str = ""
    file_listing: str = ""


class RepoBootstrapService:
    def __init__(
        self,
        sandbox_svc: SandboxService,
        guard_svc: ExecutionGuardService,
    ):
        self.sandbox_svc = sandbox_svc
        self.guard_svc = guard_svc

    async def bootstrap(self, session: Session) -> RepoBootstrapResult:
        if not session.repo_url:
            raise ValueError("repo_url is required for real execution")

        guarded_repo = self.guard_svc.validate_repo_url(session.repo_url)
        if not session.sandbox_id:
            raise ValueError("sandbox_id must exist before bootstrapping a repo")

        profile = session.sandbox_profile
        working_dir = "/workspace/repo"

        await self.sandbox_svc.execute(
            session.sandbox_id,
            self.guard_svc.validate_command("mkdir -p /workspace"),
            profile=profile,
        )
        clone_result = await self.sandbox_svc.execute(
            session.sandbox_id,
            self.guard_svc.validate_command(f"git clone --depth 1 {guarded_repo.clone_url} {working_dir}"),
            profile=profile,
        )
        if clone_result.exit_code != 0:
            raise RuntimeError(clone_result.stderr or clone_result.stdout or "Failed to clone repository")

        if session.repo_ref:
            checkout = await self.sandbox_svc.execute(
                session.sandbox_id,
                self.guard_svc.validate_command(f"git checkout {session.repo_ref}"),
                profile=profile,
                working_dir=working_dir,
            )
            if checkout.exit_code != 0:
                fetch = await self.sandbox_svc.execute(
                    session.sandbox_id,
                    self.guard_svc.validate_command(f"git fetch --depth 1 origin {session.repo_ref}"),
                    profile=profile,
                    working_dir=working_dir,
                )
                if fetch.exit_code != 0:
                    raise RuntimeError(fetch.stderr or fetch.stdout or "Failed to fetch requested ref")
                checkout = await self.sandbox_svc.execute(
                    session.sandbox_id,
                    self.guard_svc.validate_command("git checkout FETCH_HEAD"),
                    profile=profile,
                    working_dir=working_dir,
                )
                if checkout.exit_code != 0:
                    raise RuntimeError(checkout.stderr or checkout.stdout or "Failed to checkout requested ref")

        git_status = await self.sandbox_svc.execute(
            session.sandbox_id,
            self.guard_svc.validate_command("git status --short"),
            profile=profile,
            working_dir=working_dir,
        )
        file_listing = await self.sandbox_svc.execute(
            session.sandbox_id,
            self.guard_svc.validate_command("find . -maxdepth 3 -type f"),
            profile=profile,
            working_dir=working_dir,
        )
        return RepoBootstrapResult(
            working_dir=working_dir,
            repo_url=guarded_repo.normalized_url,
            repo_ref=session.repo_ref,
            git_status=self.guard_svc.truncate_output(git_status.stdout or git_status.stderr),
            file_listing=self.guard_svc.truncate_output(file_listing.stdout or file_listing.stderr),
        )
