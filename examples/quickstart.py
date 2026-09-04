"""End-to-end quickstart for the HumanAuthn Python SDK.

By default this runs the real SDK against a local in-process mock of the
Verifik HumanAuthn API (see ``mock_server.py``), so it works with no
credentials::

    uv run python examples/quickstart.py

To run against the real Verifik API instead, set a client JWT::

    VERIFIK_CLIENT_JWT=<token> uv run python examples/quickstart.py
"""

from __future__ import annotations

import json
import os
import sys
from base64 import b64encode

from humanauthn import HumanAuthnApiError, HumanAuthnClient
from mock_server import MockServer, start_mock_server

ALICE_FACE = b64encode(b"alice-live-biometric-sample").decode("ascii")
MALLORY_FACE = b64encode(b"mallory-live-biometric-sample").decode("ascii")


def log(step: str, detail: object | None = None) -> None:
    suffix = "" if detail is None else f" {json.dumps(detail, default=str)}"
    print(f"\u2192 {step}{suffix}")


def main() -> None:
    jwt = os.environ.get("VERIFIK_CLIENT_JWT") or os.environ.get("VERIFIK_TOKEN")
    mock: MockServer | None = None

    if jwt:
        api_key = jwt
        base_url = os.environ.get("HUMANAUTHN_BASE_URL")
        print("Running against the REAL Verifik API:", base_url or "https://api.verifik.co")
    else:
        mock = start_mock_server()
        api_key = mock.api_key
        base_url = mock.url
        print("Running against a LOCAL mock HumanAuthn server:", base_url)

    if base_url:
        client = HumanAuthnClient(api_key, base_url=base_url)
    else:
        client = HumanAuthnClient(api_key)
    try:
        print("\n== Enrollment (encrypt) ==")
        enrolled = client.encrypt(
            face_base64=ALICE_FACE,
            identifier="user42",
            public_data={"org": "Zelf", "tier": "pro"},
            metadata={"userId": "42", "role": "admin"},
            require_liveness=False,
        )
        log("Created HumanID (zelf_proof, truncated)", f"{enrolled.zelf_proof[:24]}...")
        log("Credits", enrolled.credits)

        print("\n== Preview (public data, no biometrics) ==")
        preview = client.preview(zelf_proof=enrolled.zelf_proof)
        log("Public data", preview.public_data)
        log("Password protected", preview.password_protected or False)

        print("\n== Authentication (decrypt) with the enrolled face ==")
        ok = client.decrypt(zelf_proof=enrolled.zelf_proof, face_base64=ALICE_FACE)
        log("Identifier", ok.identifier)
        log("Revealed private metadata", ok.metadata)
        if ok.metadata is None or ok.metadata.get("userId") != "42":
            raise AssertionError("expected private metadata to be revealed")

        print("\n== Authentication (decrypt) with a different face ==")
        try:
            client.decrypt(zelf_proof=enrolled.zelf_proof, face_base64=MALLORY_FACE)
            raise RuntimeError("expected a different face to be rejected")
        except HumanAuthnApiError as err:
            log(
                "Rejected as expected",
                {"status": err.status, "code": err.code, "message": str(err)},
            )

        print("\n\u2705 End-to-end HumanAuthn flow completed successfully.")
    finally:
        client.close()
        if mock is not None:
            mock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"\n\u274c Demo failed: {err}", file=sys.stderr)
        raise SystemExit(1) from err
