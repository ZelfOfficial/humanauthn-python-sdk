"""Public types for the HumanAuthn Python SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

OperatingSystem = Literal["DESKTOP", "ANDROID", "IOS"]
Tolerance = Literal["SOFT", "REGULAR", "HARDENED", "REGULAR_HARD", "REGULAR_SOFT"]
StringMap = dict[str, str]


@dataclass(frozen=True)
class EncryptResult:
    """Result of a successful :meth:`HumanAuthnClient.encrypt`."""

    zelf_proof: str
    ipfs: dict[str, Any] | None = None
    public_data: dict[str, Any] | None = None
    credits: dict[str, Any] | None = None


@dataclass(frozen=True)
class EncryptQrCodeResult(EncryptResult):
    """Result of a successful :meth:`HumanAuthnClient.encrypt_qr_code`."""

    qr_code: str | None = None


@dataclass(frozen=True)
class DecryptResult:
    """Result of a successful :meth:`HumanAuthnClient.decrypt`.

    Successful decryption *is* the authentication: it only occurs when the live
    face reconstructs the key, at which point the private metadata is revealed.
    """

    identifier: str | None = None
    metadata: StringMap | None = None
    public_data: dict[str, Any] | None = None
    face_crop_base64: str | None = None
    difficulty: str | None = None
    required_liveness: bool | None = None
    charged: bool | None = None


@dataclass(frozen=True)
class PreviewResult:
    """Result of :meth:`HumanAuthnClient.preview`."""

    public_data: dict[str, Any] | None = None
    required_liveness: bool | None = None
    password_protected: bool | None = None
