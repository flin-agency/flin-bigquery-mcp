from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from .config import Settings, load_settings, resolve_token_path

BIGQUERY_SCOPES = ("https://www.googleapis.com/auth/bigquery",)


class AuthenticationError(RuntimeError):
    """Raised when credential loading or refresh fails."""


class AuthenticationRequiredError(AuthenticationError):
    """Raised when interactive OAuth is required to continue."""


def _load_token_info(token_path: Path) -> dict[str, Any]:
    try:
        _ensure_private_token_dir(token_path, create=False)
        before = token_path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise AuthenticationError(
                "Token storage must be a regular file, not a symlink."
            )
        # O_NOFOLLOW prevents a final-component symlink swap; O_NONBLOCK avoids
        # hanging if a regular file is replaced with a FIFO before open().
        flags = (
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        fd = os.open(token_path, flags)
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            current = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(current.st_mode)
                or (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)
                or current.st_nlink != 1
            ):
                raise AuthenticationError(
                    "Token file changed or has multiple hard links."
                )
            if os.name != "nt" and (
                current.st_uid != os.getuid() or current.st_mode & 0o077
            ):
                raise AuthenticationError(
                    "Token file must be owned by the current user with private permissions (0600)."
                )
            data = handle.read(65537)
            if len(data) > 65536:
                raise AuthenticationError("Token file exceeds the size limit.")
        info = json.loads(data)
        if not isinstance(info, dict):
            raise AuthenticationError("Token file must contain a JSON object.")
        return info
    except FileNotFoundError as exc:
        raise AuthenticationRequiredError("No token file found.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AuthenticationError("Token file is not valid JSON.") from exc
    except OSError as exc:
        raise AuthenticationError("Token file could not be read securely.") from exc


def _build_credentials_from_info(info: dict[str, Any], scopes: tuple[str, ...]) -> Any:
    try:
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise AuthenticationError(
            "Google auth dependencies are not installed. Install project dependencies first."
        ) from exc

    try:
        return Credentials.from_authorized_user_info(info, scopes=scopes)
    except Exception as exc:
        raise AuthenticationError(
            "Failed to load credentials from token data."
        ) from exc


def _refresh_credentials(credentials: Any) -> None:
    try:
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise AuthenticationError(
            "Google auth transport dependency is not installed. Install project dependencies first."
        ) from exc

    credentials.refresh(Request())


def _run_installed_app_flow(settings: Settings) -> Any:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise AuthenticationError(
            "google-auth-oauthlib is not installed. Install project dependencies first."
        ) from exc

    client_config = {
        "installed": {
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(
        client_config, BIGQUERY_SCOPES, autogenerate_code_verifier=True
    )
    return flow.run_local_server(
        host="127.0.0.1",
        port=settings.oauth_port,
        timeout_seconds=180,
        open_browser=True,
        access_type="offline",
        prompt="consent select_account",
        authorization_prompt_message="",
        success_message=(
            "BigQuery authorization complete. You can close this tab and return to Claude Desktop."
        ),
    )


def _ensure_private_token_dir(token_path: Path, *, create: bool = True) -> None:
    token_dir = token_path.parent
    if token_dir.is_symlink():
        raise AuthenticationError(
            "Refusing to store credentials in a symlinked directory."
        )

    if create:
        try:
            token_dir.mkdir(mode=0o700, parents=True)
        except FileExistsError:
            pass

    directory_stat = token_dir.lstat()
    if not stat.S_ISDIR(directory_stat.st_mode):
        raise AuthenticationError("Token storage must be a regular directory.")
    if os.name != "nt":
        # Never chmod a caller-provided existing directory. It may be shared
        # with other applications; only newly created storage is private by default.
        if directory_stat.st_uid != os.getuid() or directory_stat.st_mode & 0o022:
            raise AuthenticationError(
                "Token storage must be owned by the current user and must not "
                "be writable by other users. Choose a dedicated private directory."
            )


def _write_credentials_atomically(token_json: str, token_path: Path) -> None:
    if token_path.is_symlink():
        raise AuthenticationError(
            "Refusing to write credentials through a symlinked token path."
        )

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{token_path.name}.",
        dir=token_path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token_json)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(tmp_path, token_path)
        if os.name != "nt":
            os.chmod(token_path, 0o600)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def save_credentials(credentials: Any, token_path: Path) -> None:
    _ensure_private_token_dir(token_path)
    _write_credentials_atomically(credentials.to_json(), token_path)


def get_credentials(
    *,
    settings: Settings | None = None,
    account: str | None = None,
    interactive: bool = True,
) -> Any:
    resolved_settings = settings or load_settings()
    if resolved_settings.auth_mode == "adc":
        if account is not None:
            raise AuthenticationError("Named accounts require OAuth mode.")
        import google.auth

        try:
            credentials, _ = google.auth.default(scopes=BIGQUERY_SCOPES)
            return credentials
        except google.auth.exceptions.DefaultCredentialsError as exc:
            raise AuthenticationRequiredError(
                "Configure Application Default Credentials."
            ) from exc
    token_path = resolve_token_path(settings=resolved_settings, account=account)

    try:
        info = _load_token_info(token_path)
    except AuthenticationRequiredError:
        if not interactive:
            raise
        credentials = _run_installed_app_flow(resolved_settings)
        save_credentials(credentials, token_path)
        return credentials

    credentials = _build_credentials_from_info(info, BIGQUERY_SCOPES)

    if getattr(credentials, "valid", False):
        return credentials

    if getattr(credentials, "expired", False) and getattr(
        credentials, "refresh_token", None
    ):
        try:
            _refresh_credentials(credentials)
        except Exception as exc:
            if not interactive:
                raise AuthenticationRequiredError(
                    "Stored credentials could not be refreshed and interactive OAuth is required."
                ) from exc
            credentials = _run_installed_app_flow(resolved_settings)

        save_credentials(credentials, token_path)
        return credentials

    if not interactive:
        raise AuthenticationRequiredError(
            "Interactive OAuth is required to obtain BigQuery credentials."
        )

    credentials = _run_installed_app_flow(resolved_settings)
    save_credentials(credentials, token_path)
    return credentials


def describe_auth_state(
    *,
    settings: Settings | None = None,
    account: str | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or load_settings()
    if resolved_settings.auth_mode == "adc":
        if account is not None:
            raise AuthenticationError("Named accounts require OAuth mode.")
        return {"status": "adc_not_checked", "has_token_file": False}
    token_path = resolve_token_path(settings=resolved_settings, account=account)

    try:
        info = _load_token_info(token_path)
        credentials = _build_credentials_from_info(info, BIGQUERY_SCOPES)
    except AuthenticationRequiredError:
        return {"status": "oauth_required", "has_token_file": False}
    except AuthenticationError as exc:
        return {
            "status": "invalid_token_file",
            "has_token_file": True,
            "error": str(exc),
        }

    if getattr(credentials, "valid", False):
        status = "ready"
    elif getattr(credentials, "expired", False) and getattr(
        credentials, "refresh_token", None
    ):
        status = "refreshable"
    else:
        status = "oauth_required"

    return {
        "status": status,
        "has_token_file": True,
    }
