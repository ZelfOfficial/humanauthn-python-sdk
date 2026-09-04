"""HumanAuthn client for Verifik's online ``/v2/human-id/*`` API."""

from __future__ import annotations

import re
from collections.abc import Mapping

import httpx

from humanauthn._http import HttpClient
from humanauthn.errors import HumanAuthnConfigError
from humanauthn.types import (
    DecryptResult,
    EncryptQrCodeResult,
    EncryptResult,
    OperatingSystem,
    PreviewResult,
    StringMap,
    Tolerance,
)

DEFAULT_BASE_URL = "https://api.verifik.co"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_OS: OperatingSystem = "DESKTOP"

_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z0-9]+$")
_DATA_URI_PREFIX = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,", re.DOTALL)


class HumanAuthnClient:
    """Client for the online (HTTP API) version of HumanAuthn.

    Backed by Verifik's ``human-id`` endpoints (the successor to the deprecated
    ``zelf-proof`` routes).

    Example::

        client = HumanAuthnClient(api_key=os.environ["VERIFIK_CLIENT_JWT"])
        enrolled = client.encrypt(
            face_base64=face,
            identifier="user42",
            public_data={"org": "Zelf"},
            metadata={"userId": "42"},
        )
        result = client.decrypt(zelf_proof=enrolled.zelf_proof, face_base64=live)
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        default_os: OperatingSystem = DEFAULT_OS,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not isinstance(api_key, str) or api_key.strip() == "":
            raise HumanAuthnConfigError(
                "A non-empty `api_key` (Verifik client JWT) is required to "
                "construct a HumanAuthnClient."
            )
        self._default_os = default_os
        self._http = HttpClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )

    def close(self) -> None:
        """Close the underlying HTTP client if this instance owns it."""
        self._http.close()

    def __enter__(self) -> HumanAuthnClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def encrypt(
        self,
        *,
        face_base64: str,
        identifier: str,
        public_data: Mapping[str, str],
        metadata: Mapping[str, str],
        os: OperatingSystem | None = None,
        require_liveness: bool = False,
        liveness_detection_prior_creation: bool | None = None,
        tolerance: Tolerance | None = None,
        password: str | None = None,
        reference_face_base64: str | None = None,
        verifier_key: str | None = None,
    ) -> EncryptResult:
        """Enrollment: bind metadata to a live biometric sample, get a HumanID."""
        body = self._build_encrypt_body(
            face_base64=face_base64,
            identifier=identifier,
            public_data=public_data,
            metadata=metadata,
            os=os,
            require_liveness=require_liveness,
            liveness_detection_prior_creation=liveness_detection_prior_creation,
            tolerance=tolerance,
            password=password,
            reference_face_base64=reference_face_base64,
            verifier_key=verifier_key,
        )
        data = self._http.post("/v2/human-id/encrypt", body)
        return _parse_encrypt_result(data)

    def encrypt_qr_code(
        self,
        *,
        face_base64: str,
        identifier: str,
        public_data: Mapping[str, str],
        metadata: Mapping[str, str],
        os: OperatingSystem | None = None,
        require_liveness: bool = False,
        liveness_detection_prior_creation: bool | None = None,
        tolerance: Tolerance | None = None,
        password: str | None = None,
        reference_face_base64: str | None = None,
        verifier_key: str | None = None,
    ) -> EncryptQrCodeResult:
        """Like :meth:`encrypt`, but also renders the HumanID as a QR code."""
        body = self._build_encrypt_body(
            face_base64=face_base64,
            identifier=identifier,
            public_data=public_data,
            metadata=metadata,
            os=os,
            require_liveness=require_liveness,
            liveness_detection_prior_creation=liveness_detection_prior_creation,
            tolerance=tolerance,
            password=password,
            reference_face_base64=reference_face_base64,
            verifier_key=verifier_key,
        )
        data = self._http.post("/v2/human-id/encrypt-qr-code", body)
        result = _parse_encrypt_result(data)
        qr_code = data.get("qrCode") if isinstance(data, dict) else None
        return EncryptQrCodeResult(
            zelf_proof=result.zelf_proof,
            ipfs=result.ipfs,
            public_data=result.public_data,
            credits=result.credits,
            qr_code=qr_code if isinstance(qr_code, str) else None,
        )

    def decrypt(
        self,
        *,
        zelf_proof: str,
        face_base64: str,
        os: OperatingSystem | None = None,
        password: str | None = None,
        verifier_key: str | None = None,
    ) -> DecryptResult:
        """Authentication: only the enrolled face reconstructs the key."""
        _require_field(zelf_proof, "zelf_proof", "decrypt")
        _require_field(face_base64, "face_base64", "decrypt")

        body: dict[str, object] = {
            "zelfProof": zelf_proof,
            "faceBase64": _normalize_image(face_base64),
            "os": os if os is not None else self._default_os,
        }
        if password:
            body["password"] = password
        if verifier_key:
            body["verifierKey"] = verifier_key

        data = self._http.post("/v2/human-id/decrypt", body)
        return _parse_decrypt_result(data)

    def preview(self, *, zelf_proof: str) -> PreviewResult:
        """Read the public, non-sensitive data of a HumanID without biometrics."""
        _require_field(zelf_proof, "zelf_proof", "preview")
        data = self._http.post("/v2/human-id/preview", {"zelfProof": zelf_proof})
        return _parse_preview_result(data)

    def _build_encrypt_body(
        self,
        *,
        face_base64: str,
        identifier: str,
        public_data: Mapping[str, str],
        metadata: Mapping[str, str],
        os: OperatingSystem | None,
        require_liveness: bool,
        liveness_detection_prior_creation: bool | None,
        tolerance: Tolerance | None,
        password: str | None,
        reference_face_base64: str | None,
        verifier_key: str | None,
    ) -> dict[str, object]:
        _require_field(face_base64, "face_base64", "encrypt")
        _require_identifier(identifier)
        _require_string_map(public_data, "public_data", "encrypt")
        _require_string_map(metadata, "metadata", "encrypt")

        body: dict[str, object] = {
            "faceBase64": _normalize_image(face_base64),
            "identifier": identifier,
            "publicData": dict(public_data),
            "metadata": dict(metadata),
            "os": os if os is not None else self._default_os,
            "requireLiveness": require_liveness,
        }
        if liveness_detection_prior_creation is not None:
            body["livenessDetectionPriorCreation"] = liveness_detection_prior_creation
        if tolerance:
            body["tolerance"] = tolerance
        if password:
            body["password"] = password
        if reference_face_base64:
            body["referenceFaceBase64"] = _normalize_image(reference_face_base64)
        if verifier_key:
            body["verifierKey"] = verifier_key
        return body


def _parse_encrypt_result(data: object) -> EncryptResult:
    if not isinstance(data, dict):
        raise HumanAuthnConfigError("Verifik API response did not include a `zelfProof` token.")
    zelf_proof = data.get("zelfProof")
    if not isinstance(zelf_proof, str) or zelf_proof == "":
        raise HumanAuthnConfigError("Verifik API response did not include a `zelfProof` token.")
    ipfs = data.get("ipfs")
    public_data = data.get("publicData")
    credits = data.get("credits")
    return EncryptResult(
        zelf_proof=zelf_proof,
        ipfs=ipfs if isinstance(ipfs, dict) else None,
        public_data=public_data if isinstance(public_data, dict) else None,
        credits=credits if isinstance(credits, dict) else None,
    )


def _parse_decrypt_result(data: object) -> DecryptResult:
    if not isinstance(data, dict):
        return DecryptResult()
    identifier = data.get("identifier")
    metadata = data.get("metadata")
    public_data = data.get("publicData")
    face_crop = data.get("faceCropBase64")
    difficulty = data.get("difficulty")
    required_liveness = data.get("requiredLiveness")
    charged = data.get("charged")
    return DecryptResult(
        identifier=identifier if isinstance(identifier, str) else None,
        metadata=_as_string_map(metadata),
        public_data=public_data if isinstance(public_data, dict) else None,
        face_crop_base64=face_crop if isinstance(face_crop, str) else None,
        difficulty=difficulty if isinstance(difficulty, str) else None,
        required_liveness=required_liveness if isinstance(required_liveness, bool) else None,
        charged=charged if isinstance(charged, bool) else None,
    )


def _parse_preview_result(data: object) -> PreviewResult:
    if not isinstance(data, dict):
        return PreviewResult()
    public_data = data.get("publicData")
    required_liveness = data.get("requiredLiveness")
    password_protected = data.get("passwordProtected")
    return PreviewResult(
        public_data=public_data if isinstance(public_data, dict) else None,
        required_liveness=required_liveness if isinstance(required_liveness, bool) else None,
        password_protected=password_protected if isinstance(password_protected, bool) else None,
    )


def _as_string_map(value: object) -> StringMap | None:
    if not isinstance(value, dict):
        return None
    out: StringMap = {}
    for key, val in value.items():
        if isinstance(key, str) and isinstance(val, str):
            out[key] = val
    return out


def _normalize_image(image: str) -> str:
    """Strip a ``data:`` URI prefix so callers can pass either form."""
    return _DATA_URI_PREFIX.sub("", image, count=1)


def _require_field(value: object, field: str, method: str) -> None:
    if not isinstance(value, str) or value.strip() == "":
        raise HumanAuthnConfigError(f"`{field}` is required for {method}().")


def _require_identifier(identifier: object) -> None:
    _require_field(identifier, "identifier", "encrypt")
    if not isinstance(identifier, str) or not _IDENTIFIER_PATTERN.match(identifier):
        raise HumanAuthnConfigError(
            "`identifier` must be alphanumeric (no spaces or special characters)."
        )


def _require_string_map(value: object, field: str, method: str) -> None:
    if value is None or not isinstance(value, Mapping) or isinstance(value, (str, bytes)):
        raise HumanAuthnConfigError(
            f"`{field}` is required for {method}() and must be an object of string values."
        )
    for key, val in value.items():
        if not isinstance(val, str):
            raise HumanAuthnConfigError(
                f"`{field}.{key}` must be a string; HumanAuthn only accepts string key-value pairs."
            )
