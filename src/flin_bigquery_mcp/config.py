from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

REQUIRED_ENV_VARS = (
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
)
ACCOUNT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


def missing_required_env_vars(env: Mapping[str, str] | None = None) -> list[str]:
    source = os.environ if env is None else env
    if source.get("GOOGLE_BIGQUERY_AUTH_MODE", "oauth").strip() == "adc":
        return []
    return [key for key in REQUIRED_ENV_VARS if not source.get(key, "").strip()]


def default_token_path(
    *, home: Path | None = None, platform_name: str | None = None
) -> Path:
    resolved_home = home or Path.home()
    resolved_platform = platform_name or sys.platform

    if resolved_platform == "darwin":
        return (
            resolved_home
            / "Library"
            / "Application Support"
            / "flin-bigquery-mcp"
            / "token.json"
        )

    if resolved_platform.startswith("win"):
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "flin-bigquery-mcp" / "token.json"
        return (
            resolved_home / "AppData" / "Roaming" / "flin-bigquery-mcp" / "token.json"
        )

    return resolved_home / ".config" / "flin-bigquery-mcp" / "token.json"


def _parse_oauth_port(raw_value: str | None) -> int:
    if raw_value is None or not raw_value.strip():
        return 0

    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(
            f"Invalid GOOGLE_BIGQUERY_OAUTH_PORT value: {raw_value!r}."
        ) from exc

    if parsed < 0 or parsed > 65535:
        raise ConfigurationError(
            f"GOOGLE_BIGQUERY_OAUTH_PORT must be between 0 and 65535, got {parsed}."
        )

    return parsed


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    default_project: str | None
    token_path: Path
    token_dir: Path
    oauth_port: int
    auth_mode: str = "oauth"
    location: str | None = None
    max_bytes_billed: int = 1073741824


def resolve_token_path(*, settings: Settings, account: str | None = None) -> Path:
    if account is None:
        return settings.token_path

    normalized_account = account.strip()
    if (
        not normalized_account
        or normalized_account in {".", ".."}
        or not ACCOUNT_NAME_PATTERN.fullmatch(normalized_account)
    ):
        raise ConfigurationError(
            "Invalid account name. Use only letters, numbers, underscore, hyphen, and dot."
        )

    token_path = settings.token_dir / f"{normalized_account}.json"
    # Compare case-insensitively as well: macOS and Windows commonly use
    # case-insensitive filesystems, including before either file exists.
    aliases_default = (
        str(token_path.resolve()).casefold()
        == str(settings.token_path.resolve()).casefold()
    )
    if not aliases_default and token_path.exists() and settings.token_path.exists():
        aliases_default = token_path.samefile(settings.token_path)
    if aliases_default:
        raise ConfigurationError(
            "This account name conflicts with the default token file. "
            "Omit account to use the default account, or choose a different name."
        )

    return token_path


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env
    auth_mode = source.get("GOOGLE_BIGQUERY_AUTH_MODE", "oauth").strip()
    if auth_mode not in {"oauth", "adc"}:
        raise ConfigurationError("GOOGLE_BIGQUERY_AUTH_MODE must be oauth or adc.")
    missing = missing_required_env_vars(source)
    if missing:
        missing_fmt = ", ".join(missing)
        raise ConfigurationError(
            "Missing required environment variables: "
            f"{missing_fmt}. See README.md for setup instructions."
        )

    token_override = source.get("GOOGLE_BIGQUERY_TOKEN_PATH")
    token_path = (
        Path(token_override).expanduser() if token_override else default_token_path()
    )
    token_dir_override = source.get("GOOGLE_BIGQUERY_TOKEN_DIR")
    token_dir = (
        Path(token_dir_override).expanduser()
        if token_dir_override
        else token_path.parent
    )

    default_project = source.get("GOOGLE_BIGQUERY_PROJECT")
    default_project = default_project.strip() if default_project else None

    try:
        max_bytes_billed = int(
            source.get("GOOGLE_BIGQUERY_MAX_BYTES_BILLED", "1073741824")
        )
        if max_bytes_billed <= 0:
            raise ValueError
    except ValueError as exc:
        raise ConfigurationError(
            "GOOGLE_BIGQUERY_MAX_BYTES_BILLED must be a positive integer."
        ) from exc

    return Settings(
        client_id=source.get("GOOGLE_CLIENT_ID", "").strip(),
        client_secret=source.get("GOOGLE_CLIENT_SECRET", "").strip(),
        default_project=default_project,
        token_path=token_path,
        token_dir=token_dir,
        oauth_port=_parse_oauth_port(source.get("GOOGLE_BIGQUERY_OAUTH_PORT")),
        auth_mode=auth_mode,
        location=source.get("GOOGLE_BIGQUERY_LOCATION", "").strip() or None,
        max_bytes_billed=max_bytes_billed,
    )
