import time
from datetime import datetime, timezone
from time import monotonic, sleep

import requests

from util.logging import logger

import googleapiclient.discovery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

__DEVICE_AUTH_URL = "https://oauth2.googleapis.com/device/code"
__TOKEN_URL = "https://oauth2.googleapis.com/token"
__USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
__REVOKE_URL = "https://oauth2.googleapis.com/revoke"

__DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


class DeviceCodeFlowError(RuntimeError):
    """Base exception for device code OAuth failures."""


class DeviceCodeRequestError(DeviceCodeFlowError):
    """Raised when the device code request cannot be completed."""


class DeviceCodeExpiredError(DeviceCodeFlowError):
    """Raised when the device code expires before authorization completes."""


class DeviceCodeDeniedError(DeviceCodeFlowError):
    """Raised when the user denies device authorization."""


class DeviceCodePollingError(DeviceCodeFlowError):
    """Raised when polling the token endpoint fails unexpectedly."""


def device_code_flow(
    client_id: str, client_secret: str, scopes: list[str] | None = None
) -> Credentials:
    """Run the OAuth device code flow and return OAuth credentials.

    The flow requests a device code, instructs the user to authorize access,
    then polls the token endpoint until the authorization completes.

    Args:
        client_id: OAuth client ID used to request the device code.
        client_secret: OAuth client secret used when exchanging the token.
        scopes: Optional OAuth scopes to request; defaults are used when omitted.

    Returns:
        OAuth credentials containing the access token and refresh token when available.

    Raises:
        DeviceCodeFlowError: Raised when the device code or token exchange fails.
    """
    if scopes is None:
        logger.debug("OAuth scopes not provided, using default scopes")
        scopes = __DEFAULT_SCOPES

    logger.info("Starting device code OAuth flow...")

    try:
        device_data = __fetch_device_code(client_id, scopes)
    except requests.RequestException as exc:
        logger.error("Failed to obtain device code: %s", exc)
        raise DeviceCodeRequestError("Failed to obtain device code") from exc

    device_code = device_data["device_code"]
    user_code = device_data["user_code"]
    verification_url = device_data.get("verification_url") or device_data.get(
        "verification_uri"
    )
    interval = int(device_data.get("interval", 5))
    expires_in = int(device_data.get("expires_in", 1800))
    logger.debug(
        "Received OAuth device code metadata: interval=%s, expires_in=%s",
        interval,
        expires_in,
    )

    print(
        f"\n{'=' * 60}\n"
        f"  To authorise this application, visit:\n"
        f"    {verification_url}\n"
        f"  and enter the code:  {user_code}\n"
        f"{'=' * 60}\n",
        flush=True,
    )
    logger.info(
        "Waiting for user to complete device authorisation (code: %s)...", user_code
    )

    token_data = __poll_for_tokens(
        client_id, client_secret, device_code, interval, expires_in
    )

    # Build a Credentials object so we can use the standard helper.
    expiry_dt: datetime | None = None
    expires_in_secs = token_data.get("expires_in")
    if expires_in_secs is not None:
        expiry_dt = datetime.fromtimestamp(
            time.time() + int(expires_in_secs), tz=timezone.utc
        ).replace(tzinfo=None)  # store as naive UTC to match SQLAlchemy convention

    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=__TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        expiry=expiry_dt,
    )
    logger.debug("OAuth credentials built successfully from device flow")

    return creds


def authenticate(creds: Credentials) -> googleapiclient.Resource:
    """Build and return a YouTube Data API client from OAuth credentials.

    If the credentials are close to expiry, they are refreshed before the
    YouTube client is created.

    Args:
        creds: OAuth credentials used to authenticate the YouTube client.

    Returns:
        A configured Google API client for the YouTube Data API v3.
    """
    if __is_expired(creds):
        logger.debug("OAuth credentials expiring soon; refreshing before client build")
        creds = __refresh_credentials(creds)
    else:
        logger.debug("OAuth credentials valid; skipping refresh")

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def __refresh_credentials(creds: Credentials) -> Credentials:
    """Refresh OAuth credentials using the stored refresh token.

    Args:
        creds: The expired or near-expiry credentials to refresh.

    Returns:
        The refreshed credentials object.

    Raises:
        ValueError: Raised when no refresh token is available.
    """
    if creds.refresh_token:
        logger.debug("Refreshing OAuth credentials using stored refresh token")
        try:
            creds.refresh(Request())
        except Exception as exc:
            logger.error("OAuth credential refresh failed: %s", exc)
            raise
        logger.debug("OAuth credentials refreshed successfully")
        return creds
    logger.warning("OAuth refresh requested but no refresh token is available")
    raise ValueError("No refresh token provided.")


def __is_expired(creds: Credentials) -> bool:
    """Return True when credentials are expired or within the refresh window.

    Credentials without expiry metadata are treated as valid. A 5-minute
    safety window is used so tokens are refreshed before they actually expire.

    Args:
        creds: OAuth credentials to inspect.

    Returns:
        True when the credentials should be refreshed, otherwise False.
    """
    if creds.expiry is None:
        # No expiry information – treat as valid (server will reject if not).
        logger.debug("OAuth credentials have no expiry metadata; treating as valid")
        return False

    expiry = creds.expiry
    # Normalize to UTC-aware datetime for comparison.
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    now = datetime.now(tz=timezone.utc)
    seconds_remaining = (expiry - now).total_seconds()
    logger.debug(
        "OAuth credential expiry check: expiry=%s, seconds_remaining=%.0f",
        expiry,
        seconds_remaining,
    )
    return seconds_remaining <= 300


def __fetch_device_code(client_id: str, scopes: list[str]) -> dict:
    """Request a device code from Google's OAuth device endpoint.

    Args:
        client_id: OAuth client ID used for the device authorization request.
        scopes: OAuth scopes to request.

    Returns:
        The decoded JSON payload from the device authorization response.

    Raises:
        requests.HTTPError: Raised when the device authorization request fails.
        DeviceCodeRequestError: Raised when the response payload is missing required fields.
    """
    response = requests.post(
        __DEVICE_AUTH_URL,
        data={"client_id": client_id, "scope": " ".join(scopes)},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if "device_code" not in payload or "user_code" not in payload:
        raise DeviceCodeRequestError(
            "Device authorization response was missing required fields"
        )
    return payload


def __poll_for_tokens(
    client_id: str,
    client_secret: str,
    device_code: str,
    interval: int,
    expires_in: int,
) -> dict[str, object]:
    """Poll the token endpoint until the device flow completes or expires.

    Args:
        client_id: OAuth client ID used to poll for tokens.
        client_secret: OAuth client secret used to poll for tokens.
        device_code: Device code returned by the authorization request.
        interval: Polling interval in seconds.
        expires_in: Maximum time in seconds to keep polling.

    Returns:
        A token response payload when authorization succeeds.

    Raises:
        DeviceCodeDeniedError: Raised when the user denies authorization.
        DeviceCodeExpiredError: Raised when the device code expires before authorization completes.
        DeviceCodePollingError: Raised when the token endpoint returns an unexpected error.
    """
    deadline = monotonic() + expires_in
    while monotonic() < deadline:
        sleep(interval)
        resp = requests.post(
            __TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=15,
        )
        try:
            payload = resp.json()
        except ValueError as exc:
            logger.error("Token endpoint returned a non-JSON response")
            raise DeviceCodePollingError(
                "Token endpoint returned invalid JSON"
            ) from exc

        error = payload.get("error")
        if resp.status_code == 428 or error == "authorization_pending":
            logger.debug("OAuth device authorization still pending")
            continue
        if resp.status_code == 403 and error == "slow_down":
            logger.debug("OAuth token polling requested to slow down")
            interval += 5
            continue
        if resp.status_code == 403 and error == "access_denied":
            logger.error("Device authorization was denied by the user")
            raise DeviceCodeDeniedError("Device authorization was denied")
        if error == "expired_token":
            logger.error("Device code expired before the user completed authorisation.")
            raise DeviceCodeExpiredError(
                "Device code expired before authorization completed"
            )
        if error:
            logger.error("Device code polling error: %s", error)
            raise DeviceCodePollingError(f"Unexpected token endpoint error: {error}")

        if resp.status_code >= 400:
            logger.error(
                "Token endpoint returned unexpected HTTP status: %s", resp.status_code
            )
            raise DeviceCodePollingError(
                f"Token endpoint returned unexpected HTTP status: {resp.status_code}"
            )

        return payload  # success – contains access_token, refresh_token, etc.

    logger.error("Device code expired before the user completed authorisation.")
    raise DeviceCodeExpiredError("Device code expired before authorization completed")
