"""Shared helpers for offline httpx.MockTransport tests."""

from __future__ import annotations

import json
from typing import Any

import httpx

SAMPLE_IMAGE = (  # 1x1 PNG, kept as a single token for request-shape assertions
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)


class RecordedCall:
    def __init__(self, request: httpx.Request) -> None:
        self.url = str(request.url)
        self.method = request.method
        self.headers = {k.lower(): v for k, v in request.headers.items()}
        raw = request.content.decode("utf-8") if request.content else ""
        self.body: Any = json.loads(raw) if raw else None


class MockSpec:
    def __init__(
        self,
        *,
        status: int = 200,
        body: object | None = None,
        raw: str | None = None,
        network_error: str | None = None,
        timeout: bool = False,
    ) -> None:
        self.status = status
        self.body = body
        self.raw = raw
        self.network_error = network_error
        self.timeout = timeout


class Recorder:
    """Queued MockTransport that records outbound requests."""

    def __init__(self, responses: list[MockSpec]) -> None:
        self._responses = responses
        self.calls: list[RecordedCall] = []
        self._index = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(RecordedCall(request))
        if not self._responses:
            raise RuntimeError("Recorder: no response configured")
        spec = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        if spec.timeout:
            raise httpx.ReadTimeout("timed out")
        if spec.network_error:
            raise httpx.ConnectError(spec.network_error)
        if spec.raw is not None:
            return httpx.Response(spec.status, content=spec.raw.encode("utf-8"))
        if spec.body is None:
            return httpx.Response(spec.status)
        return httpx.Response(spec.status, json=spec.body)

    def http_client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def recorder(*responses: dict[str, Any]) -> Recorder:
    specs = [
        MockSpec(
            status=int(item.get("status", 200)),
            body=item.get("body"),
            raw=item.get("raw"),
            network_error=item.get("network_error"),
            timeout=bool(item.get("timeout", False)),
        )
        for item in responses
    ]
    return Recorder(specs)
