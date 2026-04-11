from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.models.user import User
from app.repositories.redis_repo import RedisRepository

SECRET_KEY = "abb-secret-key-change-in-production-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

NS = "users"
NS_EMAIL = "users_by_email"


class AuthService:
    def __init__(self, repo: RedisRepository):
        self.repo = repo

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify_password(self, plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False

    def create_token(self, user_id: str) -> str:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

    def decode_token(self, token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub")
        except JWTError:
            return None

    async def register(self, email: str, password: str, name: str = "") -> User | None:
        # Check if email already exists
        existing_id = await self.repo.r.get(f"abb:{NS_EMAIL}:{email}")
        if existing_id:
            return None
        user = User(email=email, hashed_password=self.hash_password(password), name=name)
        await self.repo.save_model(NS, user.id, user)
        # Store email → id mapping
        await self.repo.r.set(f"abb:{NS_EMAIL}:{email}", user.id)
        return user

    async def login(self, email: str, password: str) -> User | None:
        user_id = await self.repo.r.get(f"abb:{NS_EMAIL}:{email}")
        if not user_id:
            return None
        if isinstance(user_id, bytes):
            user_id = user_id.decode()
        user = await self.repo.get_model(NS, user_id, User)
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user

    async def get_user(self, user_id: str) -> User | None:
        return await self.repo.get_model(NS, user_id, User)

    async def update_github_token(self, user_id: str, token: str, username: str) -> User | None:
        user = await self.get_user(user_id)
        if not user:
            return None
        user.github_token = token
        user.github_username = username
        user.updated_at = datetime.utcnow()
        await self.repo.save_model(NS, user.id, user)
        return user
