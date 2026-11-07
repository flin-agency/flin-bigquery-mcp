import json
import os

import google.auth
import pytest

from flin_bigquery_mcp import auth, server


@pytest.fixture
def configured(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith("GOOGLE_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sensitive-test-secret")
    monkeypatch.setenv("GOOGLE_BIGQUERY_AUTH_MODE", "oauth")
    monkeypatch.setenv("GOOGLE_BIGQUERY_MAX_BYTES_BILLED", "1073741824")
    monkeypatch.setenv("GOOGLE_BIGQUERY_TOKEN_PATH", str(tmp_path / "token.json"))
    monkeypatch.setenv("GOOGLE_BIGQUERY_TOKEN_DIR", str(tmp_path))

    def forbidden(*args, **kwargs):
        pytest.fail("connection_status must not use network, refresh, browser or jobs")

    monkeypatch.setattr(server, "create_client", forbidden)
    monkeypatch.setattr(auth, "_refresh_credentials", forbidden)
    monkeypatch.setattr(auth, "_run_installed_app_flow", forbidden)
    monkeypatch.setattr(google.auth, "default", forbidden)
    return tmp_path / "token.json"


def check_payload(result):
    assert set(result) == {
        "server_version",
        "configuration_status",
        "auth_status",
        "live_access",
        "next_step",
    }
    assert result["server_version"] == server.__version__
    assert result["live_access"] == "not_checked"
    assert result["next_step"]
    assert "sensitive" not in json.dumps(result)


def test_no_token_is_unauthenticated_and_does_not_create_storage(configured):
    result = server.connection_status()
    check_payload(result)
    assert result["configuration_status"] == "configured"
    assert result["auth_status"] == "unauthenticated"
    assert not configured.exists()


@pytest.mark.parametrize("expiry", ["2000-01-01T00:00:00Z", "2099-01-01T00:00:00Z"])
def test_saved_tokens_never_claim_verified_authentication(configured, expiry):
    configured.write_text(
        json.dumps(
            {
                "token": "sensitive-token",
                "refresh_token": "sensitive-refresh",
                "client_id": "test-client",
                "client_secret": "sensitive-test-secret",
                "expiry": expiry,
            }
        )
    )
    configured.chmod(0o600)
    before = configured.read_bytes()
    result = server.connection_status()
    check_payload(result)
    assert result["auth_status"] == "unknown"
    assert configured.read_bytes() == before


def test_corrupt_token_is_sanitized(configured):
    configured.write_text("sensitive-not-json")
    configured.chmod(0o600)
    result = server.connection_status()
    check_payload(result)
    assert result["auth_status"] == "unauthenticated"


@pytest.mark.parametrize(
    "key,value",
    [
        ("GOOGLE_CLIENT_ID", ""),
        ("GOOGLE_BIGQUERY_MAX_BYTES_BILLED", "0"),
        ("GOOGLE_BIGQUERY_AUTH_MODE", "sensitive-invalid"),
    ],
)
def test_invalid_settings_have_a_structured_result(configured, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    result = server.connection_status()
    check_payload(result)
    assert result["configuration_status"] == "incomplete"


def test_adc_is_not_discovered_or_refreshed(configured, monkeypatch):
    monkeypatch.setenv("GOOGLE_BIGQUERY_AUTH_MODE", "adc")
    monkeypatch.delenv("GOOGLE_CLIENT_ID")
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET")
    result = server.connection_status()
    check_payload(result)
    assert result["configuration_status"] == "configured"
    assert result["auth_status"] == "unknown"


def test_invalid_account_is_sanitized(configured):
    result = server.connection_status(account="../sensitive-account")
    check_payload(result)
    assert result["configuration_status"] == "incomplete"
