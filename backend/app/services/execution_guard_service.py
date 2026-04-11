from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from app.core.config import get_settings


class ExecutionGuardError(ValueError):
    pass


@dataclass
class GuardedRepo:
    normalized_url: str
    clone_url: str
    host: str


class ExecutionGuardService:
    SAFE_COMMAND_PREFIXES = (
        "mkdir -p ",
        "git clone ",
        "git checkout ",
        "git fetch ",
        "git status",
        "git diff",
        "find ",
        "ls",
        "cat ",
        "sed -n ",
        "grep ",
        "pytest",
        "python -m pytest",
        "python -m unittest",
        "npm install",
        "npm test",
        "npm run ",
        "pnpm install",
        "pnpm test",
        "pnpm run ",
        "yarn install",
        "yarn test",
        "yarn run ",
        "pip install -r ",
        "uv pip install -r ",
        "poetry install",
        "cargo test",
        "go test",
    )
    BLOCKED_TOKENS = ("&&", "||", ";", "|", ">", "<", "`", "$(", "sudo ", "ssh ", "scp ", "curl ", "wget ", "rm -rf /")

    def __init__(self):
        self.settings = get_settings()

    def configuration_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.settings.real_execution_enabled:
            errors.append("Real execution is disabled")
        if not self.settings.openai_api_key:
            errors.append("ABB_OPENAI_API_KEY is not configured")
        if not self.settings.blaxel_api_key:
            errors.append("ABB_BLAXEL_API_KEY is not configured")
        if not self.settings.bl_workspace:
            errors.append("ABB_BL_WORKSPACE is not configured")
        if not self.settings.redis_url.startswith(("redis://", "rediss://")):
            errors.append("ABB_REDIS_URL must be a full redis:// or rediss:// URL")
        return errors

    def validate_repo_url(self, repo_url: str) -> GuardedRepo:
        parsed = urlparse(repo_url)
        if parsed.scheme != "https":
            raise ExecutionGuardError("Only https:// repository URLs are allowed in real mode")
        if not parsed.netloc:
            raise ExecutionGuardError("Repository URL must include a host")
        allowed_hosts = {host.lower() for host in self.settings.allowed_repo_hosts}
        if allowed_hosts and parsed.netloc.lower() not in allowed_hosts:
            raise ExecutionGuardError(f"Repository host '{parsed.netloc}' is not in ABB_ALLOWED_REPO_HOSTS")

        clone_netloc = parsed.netloc
        if self.settings.git_access_token and "@" not in clone_netloc:
            clone_netloc = f"x-access-token:{self.settings.git_access_token}@{clone_netloc}"
        clone_url = urlunparse((parsed.scheme, clone_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        normalized_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        return GuardedRepo(normalized_url=normalized_url, clone_url=clone_url, host=parsed.netloc.lower())

    def validate_command(self, command: str) -> str:
        clean = command.strip()
        if not clean:
            raise ExecutionGuardError("Empty commands are not allowed")
        for token in self.BLOCKED_TOKENS:
            if token in clean:
                raise ExecutionGuardError(f"Blocked command token detected: {token}")
        if not clean.startswith(self.SAFE_COMMAND_PREFIXES):
            raise ExecutionGuardError("Command is outside the allowed execution allowlist")
        return clean

    def validate_write_target(self, path: str, content: str) -> None:
        if not path or path.startswith(".."):
            raise ExecutionGuardError("Invalid write target path")
        if len(content) > self.settings.max_command_output_chars:
            raise ExecutionGuardError("Generated file content exceeded the configured size limit")

    def truncate_output(self, text: str) -> str:
        if len(text) <= self.settings.max_command_output_chars:
            return text
        return text[: self.settings.max_command_output_chars] + "\n...[truncated]"
