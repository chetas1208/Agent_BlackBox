"""Authentication endpoints: register, login, me, GitHub OAuth."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.api.deps import get_repo
from app.services.auth_service import AuthService
from app.repositories.redis_repo import RedisRepository

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class GitHubTokenRequest(BaseModel):
    token: str
    username: str


def _svc(repo: RedisRepository) -> AuthService:
    return AuthService(repo)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    repo: RedisRepository = Depends(get_repo),
) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    svc = _svc(repo)
    user_id = svc.decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


async def get_current_user_id_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    repo: RedisRepository = Depends(get_repo),
) -> str | None:
    if not credentials:
        return None
    svc = _svc(repo)
    return svc.decode_token(credentials.credentials)


@router.post("/register")
async def register(req: RegisterRequest, repo: RedisRepository = Depends(get_repo)):
    svc = _svc(repo)
    user = await svc.register(req.email, req.password, req.name)
    if not user:
        raise HTTPException(status_code=400, detail="Email already registered")
    token = svc.create_token(user.id)
    return {
        "token": token,
        "user": {"id": user.id, "email": user.email, "name": user.name,
                 "github_username": user.github_username}
    }


@router.post("/login")
async def login(req: LoginRequest, repo: RedisRepository = Depends(get_repo)):
    svc = _svc(repo)
    user = await svc.login(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = svc.create_token(user.id)
    return {
        "token": token,
        "user": {"id": user.id, "email": user.email, "name": user.name,
                 "github_username": user.github_username}
    }


@router.get("/me")
async def me(
    user_id: str = Depends(get_current_user_id),
    repo: RedisRepository = Depends(get_repo),
):
    svc = _svc(repo)
    user = await svc.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user.id, "email": user.email, "name": user.name,
            "github_username": user.github_username}


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, repo: RedisRepository = Depends(get_repo)):
    """Generate a reset token. In production this would be emailed; here we return it directly."""
    svc = _svc(repo)
    token = await svc.create_reset_token(req.email)
    if not token:
        # Don't reveal whether email exists — but for hackathon UX, we do
        raise HTTPException(status_code=404, detail="No account found with that email")
    return {
        "message": "Reset token generated",
        "reset_token": token,   # In production: send via email, don't return here
        "expires_in": "1 hour",
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, repo: RedisRepository = Depends(get_repo)):
    svc = _svc(repo)
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    success = await svc.reset_password(req.token, req.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    return {"message": "Password updated successfully"}


@router.post("/github-token")
async def save_github_token(
    req: GitHubTokenRequest,
    user_id: str = Depends(get_current_user_id),
    repo: RedisRepository = Depends(get_repo),
):
    svc = _svc(repo)
    user = await svc.update_github_token(user_id, req.token, req.username)
    return {"github_username": user.github_username if user else None}


@router.get("/github/repos")
async def list_github_repos(
    user_id: str = Depends(get_current_user_id),
    repo: RedisRepository = Depends(get_repo),
):
    """List repos accessible via user's GitHub token."""
    svc = _svc(repo)
    user = await svc.get_user(user_id)
    if not user or not user.github_token:
        raise HTTPException(status_code=400, detail="GitHub token not connected")
    try:
        from github import Github
        g = Github(user.github_token)
        gh_user = g.get_user()
        repos = []
        for r in gh_user.get_repos(sort="updated", type="all"):
            repos.append({
                "full_name": r.full_name,
                "name": r.name,
                "description": r.description or "",
                "private": r.private,
                "html_url": r.html_url,
                "clone_url": r.clone_url,
                "default_branch": r.default_branch,
                "language": r.language,
            })
            if len(repos) >= 50:
                break
        return repos
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"GitHub error: {e}")
