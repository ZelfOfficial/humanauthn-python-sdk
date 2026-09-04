"""Real HumanID round-trip: enroll a face, then authenticate with it.

By default it uses the bundled AI-generated synthetic face
(``./faces/generated-test-face.jpg``). To use a different face, supply it
locally (it is never committed — face images are biometric data; see
``.gitignore``)::

    HUMANAUTHN_FACE_IMAGE=/absolute/path/to/your-selfie.jpg
    # or a pre-encoded base64 string:
    HUMANAUTHN_FACE_BASE64=<base64>

Against the real Verifik API (charges credits), set your client JWT::

    VERIFIK_CLIENT_JWT=<token> uv run python examples/real_roundtrip.py

With no JWT it runs against a local in-process mock so you can validate the
wiring (the mock hashes the image bytes rather than doing real face matching).
"""

from __future__ import annotations

import json
import os
import sys
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

from humanauthn import HumanAuthnClient
from mock_server import MockServer, start_mock_server

DEFAULT_FACE = Path(__file__).resolve().parent / "faces" / "generated-test-face.jpg"


def load_face_base64() -> str:
    inline = os.environ.get("HUMANAUTHN_FACE_BASE64")
    if inline and inline.strip():
        return inline.strip()
    path = Path(os.environ.get("HUMANAUTHN_FACE_IMAGE") or DEFAULT_FACE)
    return b64encode(path.read_bytes()).decode("ascii")


def log(step: str, detail: object | None = None) -> None:
    suffix = "" if detail is None else f" {json.dumps(detail, default=str)}"
    print(f"\u2192 {step}{suffix}")


def main() -> None:
    face_base64 = load_face_base64()
    jwt = os.environ.get("VERIFIK_CLIENT_JWT") or os.environ.get("VERIFIK_TOKEN")
    mock: MockServer | None = None

    if jwt:
        api_key = jwt
        base_url = os.environ.get("HUMANAUTHN_BASE_URL")
        print("Running a REAL round-trip against", base_url or "https://api.verifik.co")
    else:
        mock = start_mock_server()
        api_key = mock.api_key
        base_url = mock.url
        print("No VERIFIK_CLIENT_JWT set — running against a LOCAL mock:", base_url)

    if base_url:
        client = HumanAuthnClient(api_key, base_url=base_url)
    else:
        client = HumanAuthnClient(api_key)
    identifier = (
        os.environ.get("HUMANAUTHN_IDENTIFIER") or f"test{int(datetime.now().timestamp() * 1000)}"
    )

    try:
        print("\n== Enroll (encrypt) ==")
        enrolled = client.encrypt(
            face_base64=face_base64,
            identifier=identifier,
            public_data={"app": "humanauthn-sdk-test"},
            metadata={
                "note": "round-trip test",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
            require_liveness=False,
        )
        log("HumanID (zelf_proof, truncated)", f"{enrolled.zelf_proof[:28]}...")

        print("\n== Preview ==")
        preview = client.preview(zelf_proof=enrolled.zelf_proof)
        log("Public data", preview.public_data)

        print("\n== Authenticate (decrypt) with the same face ==")
        result = client.decrypt(zelf_proof=enrolled.zelf_proof, face_base64=face_base64)
        log("Identifier", result.identifier)
        log("Revealed private metadata", result.metadata)
        if result.difficulty:
            log("Difficulty", result.difficulty)

        print("\n\u2705 Round-trip succeeded: the face enrolled and then authenticated.")
    finally:
        client.close()
        if mock is not None:
            mock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(
            f"\n\u274c Round-trip failed: {err if isinstance(err, Exception) else err}",
            file=sys.stderr,
        )
        raise SystemExit(1) from err
