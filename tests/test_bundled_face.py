"""The bundled synthetic face is copied from the Node SDK and must stay committed."""

from __future__ import annotations

import hashlib
from pathlib import Path

# Byte-identical to ZelfOfficial/humanauthn-nodejs-sdk
# examples/faces/generated-test-face.jpg
_NODE_SDK_FACE_SHA256 = "d1473c5d2fa6ca14fe6d3104b66fbeaf1d80a41e6fe10e2d5fce8765f139551c"
_FACE = Path(__file__).resolve().parents[1] / "examples" / "faces" / "generated-test-face.jpg"


def test_bundled_synthetic_face_matches_nodejs_sdk() -> None:
    assert _FACE.is_file(), (
        "Missing examples/faces/generated-test-face.jpg — copy it from "
        "ZelfOfficial/humanauthn-nodejs-sdk (synthetic test face, not a real person)."
    )
    digest = hashlib.sha256(_FACE.read_bytes()).hexdigest()
    assert digest == _NODE_SDK_FACE_SHA256
