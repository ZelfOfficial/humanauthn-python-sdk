# humanauthn-python-sdk

Official Python SDK for the online (HTTP API) version of
[HumanAuthn](https://docs.verifik.co/biometrics/humanauthn/) by Verifik.

HumanAuthn is an authentication + encryption primitive that turns a live
biometric sample plus stored entropy into a verifiable credential — a
**HumanID**, represented on the wire as a `zelfProof` token. This SDK wraps the
current online HumanAuthn endpoints (`/v2/human-id/encrypt`,
`/encrypt-qr-code`, `/decrypt`, `/preview`) in a small, typed client. (The
legacy `/v2/zelf-proof/*` routes are deprecated and not used.)

## Installation

```bash
pip install humanauthn
```

```bash
uv add humanauthn
```

Requires Python 3.9+. The development environment targets Python 3.14.

## Quick start

```python
import os
from humanauthn import HumanAuthnClient

client = HumanAuthnClient(api_key=os.environ["VERIFIK_CLIENT_JWT"])

# Enrollment: bind metadata to a live biometric sample, get a HumanID token.
enrolled = client.encrypt(
    face_base64=face_base64,  # base64 (or data: URI) facial image
    identifier="user42",  # alphanumeric
    public_data={"org": "Zelf"},  # string key-value pairs
    metadata={"userId": "42"},  # encrypted, owner-only
    require_liveness=True,
)

# Authentication: only the enrolled face reconstructs the key and decrypts.
result = client.decrypt(zelf_proof=enrolled.zelf_proof, face_base64=live_face)
print("Welcome back", result.identifier, result.metadata)
```

How it works: **enroll** = `encrypt`, **authenticate** = `decrypt`, inspect
public fields with `preview`. Full documentation (JWT auth, credits, security,
and framework integrations) will land in a follow-up PR.

## Development

```bash
uv sync --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run python examples/quickstart.py
```

## License

MIT
