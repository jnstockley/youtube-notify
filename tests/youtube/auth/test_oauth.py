from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests
import youtube.auth.oauth as oauth_module
from google.oauth2.credentials import Credentials


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, *, json_error: Exception | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self._json_error = json_error

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        if self._json_error is not None:
            raise self._json_error
        return self._payload


def test_device_code_flow_success(monkeypatch: pytest.MonkeyPatch) -> None:
    device_data = {
        "device_code": "device-123",
        "user_code": "user-123",
        "verification_url": "https://example.com/verify",
        "interval": 1,
        "expires_in": 10,
    }
    token_data = {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "expires_in": 60,
    }
    monkeypatch.setattr(oauth_module, "__fetch_device_code", lambda *_: device_data)
    monkeypatch.setattr(oauth_module, "__poll_for_tokens", lambda *args: token_data)

    creds = oauth_module.device_code_flow("client-id", "client-secret", scopes=["s1"])

    assert isinstance(creds, Credentials)
    assert creds.token == "access-token"
    assert creds.refresh_token == "refresh-token"
    assert creds.scopes == ["s1"]
    assert creds.expiry is not None


def test_device_code_flow_uses_default_scopes_and_no_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_data = {
        "device_code": "device-123",
        "user_code": "user-123",
        "verification_uri": "https://example.com/verify",
    }
    token_data = {"access_token": "access-token"}
    monkeypatch.setattr(oauth_module, "__fetch_device_code", lambda *_: device_data)
    monkeypatch.setattr(oauth_module, "__poll_for_tokens", lambda *args: token_data)

    creds = oauth_module.device_code_flow("client-id", "client-secret")

    assert creds.token == "access-token"
    assert creds.expiry is None
    assert creds.scopes == oauth_module.__DEFAULT_SCOPES


def test_device_code_flow_wraps_device_code_request_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch_device_code(*args):
        raise requests.RequestException("boom")

    monkeypatch.setattr(oauth_module, "__fetch_device_code", fake_fetch_device_code)

    with pytest.raises(oauth_module.DeviceCodeRequestError, match="Failed to obtain"):
        oauth_module.device_code_flow("client-id", "client-secret", scopes=["s1"])


def test_fetch_device_code_success(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(
        200,
        {
            "device_code": "device-123",
            "user_code": "user-123",
            "verification_url": "https://example.com/verify",
        },
    )
    post = Mock(return_value=response)
    monkeypatch.setattr(oauth_module.requests, "post", post)

    result = oauth_module.__fetch_device_code("client-id", ["scope-1", "scope-2"])

    assert result["device_code"] == "device-123"
    post.assert_called_once_with(
        "https://oauth2.googleapis.com/device/code",
        data={"client_id": "client-id", "scope": "scope-1 scope-2"},
        timeout=15,
    )


def test_fetch_device_code_rejects_missing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(200, {"device_code": "device-123"})
    monkeypatch.setattr(oauth_module.requests, "post", Mock(return_value=response))

    with pytest.raises(oauth_module.DeviceCodeRequestError, match="missing required"):
        oauth_module.__fetch_device_code("client-id", ["scope-1"])


def test_authenticate_refreshes_expired_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creds = Credentials(
        token="token",
        refresh_token="refresh-token",
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
        expiry=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    refreshed = Credentials(
        token="new-token",
        refresh_token="refresh-token",
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    build = Mock(return_value={"client": "youtube"})
    monkeypatch.setattr(oauth_module, "__is_expired", lambda _: True)
    monkeypatch.setattr(oauth_module, "__refresh_credentials", lambda _: refreshed)
    monkeypatch.setattr(oauth_module.googleapiclient.discovery, "build", build)

    result = oauth_module.authenticate(creds)

    assert result == {"client": "youtube"}
    build.assert_called_once_with("youtube", "v3", credentials=refreshed)


def test_authenticate_skips_refresh_for_valid_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creds = Credentials(
        token="token",
        refresh_token="refresh-token",
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    build = Mock(return_value={"client": "youtube"})
    monkeypatch.setattr(oauth_module, "__is_expired", lambda _: False)
    monkeypatch.setattr(oauth_module.googleapiclient.discovery, "build", build)

    result = oauth_module.authenticate(creds)

    assert result == {"client": "youtube"}
    build.assert_called_once_with("youtube", "v3", credentials=creds)


def test_is_expired_handles_all_cases() -> None:
    now = datetime.now(timezone.utc)
    valid = Credentials(
        token="token",
        refresh_token=None,
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
        expiry=now + timedelta(hours=1),
    )
    near_expiry = Credentials(
        token="token",
        refresh_token=None,
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
        expiry=now + timedelta(minutes=4),
    )
    naive_expiry = Credentials(
        token="token",
        refresh_token=None,
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
        expiry=(datetime.now(timezone.utc) - timedelta(minutes=1)).replace(tzinfo=None)
        + timedelta(minutes=4),
    )
    no_expiry = Credentials(
        token="token",
        refresh_token=None,
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
    )

    assert oauth_module.__is_expired(valid) is False
    assert oauth_module.__is_expired(near_expiry) is True
    assert oauth_module.__is_expired(naive_expiry) is True
    assert oauth_module.__is_expired(no_expiry) is False


def test_refresh_credentials_raises_without_refresh_token() -> None:
    creds = Credentials(
        token="token",
        refresh_token=None,
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
    )

    with pytest.raises(ValueError, match="No refresh token provided"):
        oauth_module.__refresh_credentials(creds)


def test_refresh_credentials_calls_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    creds = Credentials(
        token="token",
        refresh_token="refresh-token",
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
    )
    refresh = Mock()
    monkeypatch.setattr(creds, "refresh", refresh)
    request = Mock(return_value=object())
    monkeypatch.setattr(oauth_module, "Request", request)

    result = oauth_module.__refresh_credentials(creds)

    assert result is creds
    refresh.assert_called_once()
    request.assert_called_once_with()


def test_refresh_credentials_propagates_refresh_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    creds = Credentials(
        token="token",
        refresh_token="refresh-token",
        token_uri="https://example.com/token",
        client_id="client-id",
        client_secret="client-secret",
        scopes=["scope"],
    )

    def boom(*args, **kwargs):
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(creds, "refresh", boom)
    monkeypatch.setattr(oauth_module, "Request", Mock(return_value=object()))

    with pytest.raises(RuntimeError, match="refresh failed"):
        oauth_module.__refresh_credentials(creds)


def test_poll_for_tokens_handles_pending_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            FakeResponse(428, {"error": "authorization_pending"}),
            FakeResponse(200, {"access_token": "access-token"}),
        ]
    )
    post = Mock(side_effect=lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(oauth_module.requests, "post", post)
    monkeypatch.setattr(oauth_module, "sleep", lambda seconds: None)
    monkeypatch.setattr(oauth_module, "monotonic", lambda: 0)

    result = oauth_module.__poll_for_tokens("client-id", "client-secret", "device", 1, 10)

    assert result == {"access_token": "access-token"}


@pytest.mark.parametrize(
    ("response", "error_type", "message"),
    [
        (
            FakeResponse(403, {"error": "access_denied"}),
            oauth_module.DeviceCodeDeniedError,
            "denied",
        ),
        (
            FakeResponse(400, {"error": "expired_token"}),
            oauth_module.DeviceCodeExpiredError,
            "expired",
        ),
        (
            FakeResponse(400, {"error": "bad_request"}),
            oauth_module.DeviceCodePollingError,
            "Unexpected",
        ),
        (
            FakeResponse(500, {}),
            oauth_module.DeviceCodePollingError,
            "unexpected HTTP status",
        ),
        (
            FakeResponse(200, json_error=ValueError("bad json")),
            oauth_module.DeviceCodePollingError,
            "invalid JSON",
        ),
    ],
)
def test_poll_for_tokens_raises_for_error_conditions(
    monkeypatch: pytest.MonkeyPatch,
    response: FakeResponse,
    error_type: type[Exception],
    message: str,
) -> None:
    monkeypatch.setattr(oauth_module.requests, "post", Mock(return_value=response))
    monkeypatch.setattr(oauth_module, "sleep", lambda seconds: None)
    monkeypatch.setattr(oauth_module, "monotonic", lambda: 0)

    with pytest.raises(error_type, match=message):
        oauth_module.__poll_for_tokens("client-id", "client-secret", "device", 1, 10)


def test_poll_for_tokens_handles_slow_down_then_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            FakeResponse(403, {"error": "slow_down"}),
            FakeResponse(200, {"access_token": "access-token"}),
        ]
    )
    post = Mock(side_effect=lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(oauth_module.requests, "post", post)
    monkeypatch.setattr(oauth_module, "sleep", lambda seconds: None)
    monkeypatch.setattr(oauth_module, "monotonic", lambda: 0)

    result = oauth_module.__poll_for_tokens("client-id", "client-secret", "device", 1, 10)

    assert result == {"access_token": "access-token"}


def test_poll_for_tokens_expires_when_deadline_is_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter([FakeResponse(428, {"error": "authorization_pending"})])
    times = iter([0, 0, 20])
    monkeypatch.setattr(oauth_module.requests, "post", Mock(side_effect=lambda *a, **k: next(responses)))
    monkeypatch.setattr(oauth_module, "sleep", lambda seconds: None)
    monkeypatch.setattr(oauth_module, "monotonic", lambda: next(times))

    with pytest.raises(oauth_module.DeviceCodeExpiredError, match="expired before"):
        oauth_module.__poll_for_tokens("client-id", "client-secret", "device", 1, 10)
