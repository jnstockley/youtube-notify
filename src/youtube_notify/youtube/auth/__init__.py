"""YouTube authentication helpers."""

from .api_key import authenticate as authenticate_api_key
from .oauth import authenticate, device_code_flow

__all__ = ["authenticate", "authenticate_api_key", "device_code_flow"]
