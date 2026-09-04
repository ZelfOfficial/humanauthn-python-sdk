from __future__ import annotations

from typing import Any

import pytest

from humanauthn import (
    HumanAuthnApiError,
    HumanAuthnClient,
    HumanAuthnConfigError,
)
from tests.helpers import SAMPLE_IMAGE, Recorder, recorder

VALID_ENCRYPT: dict[str, Any] = {
    "face_base64": SAMPLE_IMAGE,
    "identifier": "user42",
    "public_data": {"org": "zelf"},
    "metadata": {"userId": "42"},
}


def make_client(rec: Recorder, **kwargs: Any) -> HumanAuthnClient:
    options: dict[str, Any] = {
        "base_url": "https://api.example.test",
        "http_client": rec.http_client(),
        "max_retries": 0,
    }
    options.update(kwargs)
    return HumanAuthnClient("test-jwt", **options)


def test_constructor_rejects_blank_api_key() -> None:
    with pytest.raises(HumanAuthnConfigError):
        HumanAuthnClient("   ")


def test_encrypt_sends_auth_header_and_normalizes_body() -> None:
    rec = recorder({"body": {"zelfProof": "zp_abc", "credits": {"amount": -0.84}}})
    client = make_client(rec)

    result = client.encrypt(
        **{**VALID_ENCRYPT, "face_base64": f"data:image/png;base64,{SAMPLE_IMAGE}"},
        require_liveness=True,
        tolerance="HARDENED",
    )

    assert result.zelf_proof == "zp_abc"
    assert result.credits == {"amount": -0.84}
    assert len(rec.calls) == 1
    call = rec.calls[0]
    assert call.url == "https://api.example.test/v2/human-id/encrypt"
    assert call.method == "POST"
    assert call.headers["authorization"] == "Bearer test-jwt"
    assert call.body == {
        "faceBase64": SAMPLE_IMAGE,
        "identifier": "user42",
        "publicData": {"org": "zelf"},
        "metadata": {"userId": "42"},
        "os": "DESKTOP",
        "requireLiveness": True,
        "tolerance": "HARDENED",
    }


def test_encrypt_honors_custom_default_os() -> None:
    rec = recorder({"body": {"zelfProof": "zp"}})
    client = make_client(rec, default_os="IOS")
    client.encrypt(**VALID_ENCRYPT)
    assert rec.calls[0].body["os"] == "IOS"


def test_encrypt_requires_face_base64() -> None:
    rec = recorder({"body": {}})
    client = make_client(rec)
    with pytest.raises(HumanAuthnConfigError):
        client.encrypt(**{**VALID_ENCRYPT, "face_base64": ""})


def test_encrypt_rejects_non_alphanumeric_identifier() -> None:
    rec = recorder({"body": {}})
    client = make_client(rec)
    with pytest.raises(HumanAuthnConfigError):
        client.encrypt(**{**VALID_ENCRYPT, "identifier": "user 42!"})


def test_encrypt_rejects_non_string_metadata() -> None:
    rec = recorder({"body": {}})
    client = make_client(rec)
    with pytest.raises(HumanAuthnConfigError):
        client.encrypt(**{**VALID_ENCRYPT, "metadata": {"userId": 42}})


def test_encrypt_throws_when_api_omits_zelf_proof() -> None:
    rec = recorder({"body": {"publicData": {}}})
    client = make_client(rec)
    with pytest.raises(HumanAuthnConfigError):
        client.encrypt(**VALID_ENCRYPT)


def test_encrypt_qr_code_posts_to_qr_endpoint() -> None:
    rec = recorder({"body": {"zelfProof": "zp_qr", "qrCode": "data:image/png;base64,QR=="}})
    client = make_client(rec)
    result = client.encrypt_qr_code(**VALID_ENCRYPT)
    assert result.zelf_proof == "zp_qr"
    assert result.qr_code == "data:image/png;base64,QR=="
    assert rec.calls[0].url == "https://api.example.test/v2/human-id/encrypt-qr-code"


def test_decrypt_reveals_identifier_and_metadata() -> None:
    rec = recorder(
        {"body": {"identifier": "user42", "metadata": {"userId": "42"}, "difficulty": "EASY"}}
    )
    client = make_client(rec)
    result = client.decrypt(zelf_proof="zp_abc", face_base64=SAMPLE_IMAGE)
    assert result.identifier == "user42"
    assert result.metadata == {"userId": "42"}
    assert result.difficulty == "EASY"
    assert rec.calls[0].url == "https://api.example.test/v2/human-id/decrypt"
    assert rec.calls[0].body == {
        "zelfProof": "zp_abc",
        "faceBase64": SAMPLE_IMAGE,
        "os": "DESKTOP",
    }


def test_decrypt_surfaces_failed_match_as_api_error() -> None:
    rec = recorder(
        {
            "status": 409,
            "body": {"message": "Face verification failed", "code": "FaceVerificationFailed"},
        }
    )
    client = make_client(rec)
    with pytest.raises(HumanAuthnApiError):
        client.decrypt(zelf_proof="zp_abc", face_base64=SAMPLE_IMAGE)


def test_decrypt_requires_zelf_proof() -> None:
    rec = recorder({"body": {}})
    client = make_client(rec)
    with pytest.raises(HumanAuthnConfigError):
        client.decrypt(zelf_proof="", face_base64=SAMPLE_IMAGE)


def test_preview_returns_public_data() -> None:
    rec = recorder({"body": {"publicData": {"org": "zelf"}, "passwordProtected": True}})
    client = make_client(rec)
    result = client.preview(zelf_proof="zp_abc")
    assert result.public_data == {"org": "zelf"}
    assert result.password_protected is True
    assert rec.calls[0].body == {"zelfProof": "zp_abc"}


def test_maps_401_to_auth_error() -> None:
    rec = recorder(
        {"status": 401, "body": {"message": "Authentication required", "code": "UNAUTHORIZED"}}
    )
    client = make_client(rec)
    with pytest.raises(HumanAuthnApiError) as exc_info:
        client.encrypt(**VALID_ENCRYPT)
    err = exc_info.value
    assert err.status == 401
    assert err.code == "UNAUTHORIZED"
    assert err.is_auth_error is True
    assert str(err) == "Authentication required"
