from __future__ import annotations

from typing import Any

import pytest

from humanauthn import HumanAuthnApiError, HumanAuthnClient, HumanAuthnTimeoutError
from tests.helpers import SAMPLE_IMAGE, Recorder, recorder

VALID_ENCRYPT: dict[str, Any] = {
    "face_base64": SAMPLE_IMAGE,
    "identifier": "user42",
    "public_data": {"org": "zelf"},
    "metadata": {"userId": "42"},
}


def make_client(rec: Recorder, max_retries: int, timeout: float = 30.0) -> HumanAuthnClient:
    return HumanAuthnClient(
        "jwt",
        base_url="https://api.example.test",
        http_client=rec.http_client(),
        max_retries=max_retries,
        timeout=timeout,
    )


def test_retries_transient_5xx_and_succeeds() -> None:
    rec = recorder(
        {"status": 503, "body": {"message": "temporarily unavailable"}},
        {"status": 200, "body": {"zelfProof": "zp_retry"}},
    )
    client = make_client(rec, max_retries=2)
    result = client.encrypt(**VALID_ENCRYPT)
    assert result.zelf_proof == "zp_retry"
    assert len(rec.calls) == 2


def test_gives_up_after_exhausting_retries() -> None:
    rec = recorder({"status": 500, "body": {"message": "boom"}})
    client = make_client(rec, max_retries=1)
    with pytest.raises(HumanAuthnApiError):
        client.encrypt(**VALID_ENCRYPT)
    assert len(rec.calls) == 2


def test_does_not_retry_4xx() -> None:
    rec = recorder({"status": 400, "body": {"message": "bad request"}})
    client = make_client(rec, max_retries=3)
    with pytest.raises(HumanAuthnApiError):
        client.encrypt(**VALID_ENCRYPT)
    assert len(rec.calls) == 1


def test_timeout_is_not_retried() -> None:
    rec = recorder({"timeout": True})
    client = make_client(rec, max_retries=2, timeout=0.025)
    with pytest.raises(HumanAuthnTimeoutError):
        client.encrypt(**VALID_ENCRYPT)
    assert len(rec.calls) == 1


def test_retries_network_errors() -> None:
    rec = recorder(
        {"network_error": "connection reset"},
        {"status": 200, "body": {"zelfProof": "zp_net"}},
    )
    client = make_client(rec, max_retries=2)
    result = client.encrypt(**VALID_ENCRYPT)
    assert result.zelf_proof == "zp_net"
    assert len(rec.calls) == 2
