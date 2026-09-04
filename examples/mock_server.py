"""In-process stand-in for Verifik's online HumanAuthn (``human-id``) API.

Implements enough of ``/v2/human-id/{encrypt,encrypt-qr-code,decrypt,preview}``
for the SDK to be exercised end to end over real HTTP without credentials.

A "face" is the SHA-256 of ``faceBase64``: decrypt succeeds only when the live
sample hashes to the same value used at enrollment.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

API_KEY = "demo-jwt-token"


@dataclass
class StoredProof:
    face_hash: str
    identifier: str
    metadata: dict[str, str]
    public_data: dict[str, str]
    password: str | None
    require_liveness: bool
    created_at: str


@dataclass
class MockServer:
    url: str
    api_key: str
    _server: ThreadingHTTPServer = field(repr=False)
    _thread: threading.Thread = field(repr=False)

    def close(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)


def start_mock_server() -> MockServer:
    store: dict[str, StoredProof] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_POST(self) -> None:  # noqa: N802
            try:
                self._handle()
            except Exception as err:  # pragma: no cover - defensive
                _send(self, 500, {"message": f"mock server error: {err}", "code": "ERROR"})

        def _handle(self) -> None:
            if self.headers.get("Authorization") != f"Bearer {API_KEY}":
                _send(self, 401, {"message": "Authentication required", "code": "UNAUTHORIZED"})
                return

            body = _read_json(self)
            path = urlparse(self.path).path

            if path.endswith("/encrypt") or path.endswith("/encrypt-qr-code"):
                for field_name in ("faceBase64", "identifier", "publicData", "metadata"):
                    if field_name not in body:
                        _send(
                            self,
                            409,
                            {"message": f'"{field_name}" is required', "code": "MissingParameter"},
                        )
                        return
                zelf_proof = secrets.token_urlsafe(48)
                store[zelf_proof] = StoredProof(
                    face_hash=_hash_face(body.get("faceBase64")),
                    identifier=str(body.get("identifier")),
                    metadata=_as_str_map(body.get("metadata")),
                    public_data=_as_str_map(body.get("publicData")),
                    password=body.get("password")
                    if isinstance(body.get("password"), str)
                    else None,
                    require_liveness=bool(body.get("requireLiveness")),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                record = store[zelf_proof]
                payload: dict[str, Any] = {
                    "zelfProof": zelf_proof,
                    "publicData": record.public_data,
                    "ipfs": {
                        "url": "https://mock.ipfs.local/ipfs/bafyMockHash",
                        "IpfsHash": "bafyMockHash",
                        "pinned": True,
                    },
                    "credits": {
                        "amount": -0.84,
                        "status": "approved",
                        "category": "usage",
                        "code": "zelf-proofs",
                    },
                }
                if path.endswith("/encrypt-qr-code"):
                    payload["qrCode"] = "data:image/png;base64," + base64.b64encode(
                        zelf_proof.encode("utf-8")
                    ).decode("ascii")
                _send(self, 200, payload)
                return

            if path.endswith("/decrypt"):
                if "zelfProof" not in body:
                    _send(
                        self,
                        409,
                        {"message": '"zelfProof" is required', "code": "MissingParameter"},
                    )
                    return
                if "faceBase64" not in body:
                    _send(
                        self,
                        409,
                        {"message": '"faceBase64" is required', "code": "MissingParameter"},
                    )
                    return
                enrolled = store.get(str(body["zelfProof"]))
                if enrolled is None:
                    _send(self, 409, {"message": "Invalid zelfProof", "code": "InvalidProof"})
                    return
                face_matches = enrolled.face_hash == _hash_face(body.get("faceBase64"))
                incoming_password = (
                    body.get("password") if isinstance(body.get("password"), str) else None
                )
                password_matches = enrolled.password == incoming_password
                if not face_matches or not password_matches:
                    _send(
                        self,
                        409,
                        {"message": "Face verification failed", "code": "FaceVerificationFailed"},
                    )
                    return
                _send(
                    self,
                    200,
                    {
                        "identifier": enrolled.identifier,
                        "metadata": enrolled.metadata,
                        "publicData": enrolled.public_data,
                        "faceCropBase64": "/9j/mockcrop",
                        "difficulty": "EASY",
                        "requiredLiveness": enrolled.require_liveness,
                        "charged": False,
                    },
                )
                return

            if path.endswith("/preview"):
                previewed = store.get(str(body.get("zelfProof")))
                if previewed is None:
                    _send(self, 409, {"message": "Invalid zelfProof", "code": "InvalidProof"})
                    return
                _send(
                    self,
                    200,
                    {
                        "publicData": previewed.public_data,
                        "requiredLiveness": previewed.require_liveness,
                        "passwordProtected": bool(previewed.password),
                    },
                )
                return

            _send(self, 404, {"message": f"Unknown endpoint: {path}", "code": "not_found"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = server.server_address
    host = address[0] if isinstance(address, tuple) else "127.0.0.1"
    port = address[1] if isinstance(address, tuple) else 0
    host_s = host.decode("ascii") if isinstance(host, bytes) else str(host)
    return MockServer(
        url=f"http://{host_s}:{port}",
        api_key=API_KEY,
        _server=server,
        _thread=thread,
    )


def _hash_face(image: object) -> str:
    if isinstance(image, bytes):
        payload = image
    else:
        payload = str(image).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _as_str_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items()}


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _send(handler: BaseHTTPRequestHandler, status: int, body: object) -> None:
    payload = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)
