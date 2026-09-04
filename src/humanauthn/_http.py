"""HTTP transport for the HumanAuthn Python SDK.

Never log ``face_base64``, ``metadata``, or the Verifik JWT.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx

from humanauthn.errors import (
    HumanAuthnApiError,
    HumanAuthnConfigError,
    HumanAuthnError,
    HumanAuthnTimeoutError,
)

_PACKAGE_NAME = "humanauthn"


def _sdk_version() -> str:
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.1.0"


def _user_agent() -> str:
    return f"humanauthn-python-sdk/{_sdk_version()}"


class HttpClient:
    """Small typed HTTP transport with timeouts, retries, and error mapping."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        if http_client is None:
            self._client = httpx.Client()
            self._owns_client = True
        else:
            self._client = http_client
            self._owns_client = False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def post(self, path: str, body: Mapping[str, Any]) -> Any:
        url = self._build_url(path)
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "authorization": f"Bearer {self._api_key}",
            "user-agent": _user_agent(),
        }
        payload = json.dumps(body)

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._send_once(url, headers, payload)
            except Exception as err:
                last_error = err
                if not self._should_retry(err) or attempt == self._max_retries:
                    raise
                time.sleep(_backoff_s(attempt))
        if last_error is not None:
            raise last_error
        raise HumanAuthnError("Request failed for an unknown reason")

    def _send_once(self, url: str, headers: Mapping[str, str], payload: str) -> Any:
        try:
            response = self._client.post(
                url,
                content=payload.encode("utf-8"),
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise HumanAuthnTimeoutError(self._timeout) from exc
        except httpx.RequestError as exc:
            raise HumanAuthnError(f"Network request failed: {exc}") from exc

        parsed = _parse_json(response.text)
        if not response.is_success:
            raise _to_api_error(response.status_code, parsed, response.text)
        return parsed if parsed is not None else {}

    def _build_url(self, path: str) -> str:
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{self._base_url}{suffix}"

    def _should_retry(self, err: BaseException) -> bool:
        if isinstance(err, HumanAuthnApiError):
            return err.is_retryable
        if isinstance(err, (HumanAuthnTimeoutError, HumanAuthnConfigError)):
            return False
        return isinstance(err, HumanAuthnError)


def _to_api_error(status: int, parsed: object, raw: str) -> HumanAuthnApiError:
    message = f"HumanAuthn API request failed with status {status}"
    code: str | None = None
    if isinstance(parsed, dict):
        raw_message = parsed.get("message")
        raw_error = parsed.get("error")
        if isinstance(raw_message, str):
            message = raw_message
        elif isinstance(raw_error, str):
            message = raw_error
        raw_code = parsed.get("code")
        if isinstance(raw_code, str):
            code = raw_code
    elif raw:
        message = f"{message}: {raw[:200]}"
    return HumanAuthnApiError(message, status, code, parsed)


def _parse_json(raw: str) -> object | None:
    if not raw:
        return None
    try:
        parsed: object = json.loads(raw)
        return parsed
    except json.JSONDecodeError:
        return None


def _backoff_s(attempt: int) -> float:
    # Exponential backoff with a little jitter: 200ms, 400ms, 800ms, ...
    base = 0.2 * (2**attempt)
    return float(base + (random.random() * 0.1))
