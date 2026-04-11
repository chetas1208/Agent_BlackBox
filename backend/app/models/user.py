from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    hashed_password: str
    name: str = ""
    github_token: str | None = None
    github_username: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
