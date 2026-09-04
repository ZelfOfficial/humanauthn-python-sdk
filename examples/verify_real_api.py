"""Real Verifik API smoke test.

Proves the SDK can reach the live HumanAuthn API and that the configured
client JWT (``VERIFIK_CLIENT_JWT``) is accepted — without needing a real face
image and without charging credits.

Strategy: call ``decrypt`` with an intentionally invalid ``zelf_proof``. A
request rejected for authentication reasons returns 401 (UNAUTHORIZED). Any
other outcome means the token was accepted and the request reached the
HumanAuthn pipeline (it then fails validation on the bogus proof, which does
not create a HumanID and is not charged).

    VERIFIK_CLIENT_JWT=<token> uv run python examples/verify_real_api.py
"""

from __future__ import annotations

import os
import sys
from base64 import b64encode

from humanauthn import HumanAuthnApiError, HumanAuthnClient


def main() -> int:
    jwt = os.environ.get("VERIFIK_CLIENT_JWT") or os.environ.get("VERIFIK_TOKEN")
    if not jwt:
        print(
            "\u274c VERIFIK_CLIENT_JWT is not set. This VM did not receive the secret.\n"
            "  (Secrets are injected into freshly booted Cloud Agent VMs.)",
            file=sys.stderr,
        )
        return 2

    base_url = os.environ.get("HUMANAUTHN_BASE_URL") or "https://api.verifik.co"
    print(f"Verifying real Verifik API auth against {base_url} ...")
    client = HumanAuthnClient(jwt, base_url=base_url)
    dummy_face = b64encode(b"smoke-test-not-a-real-face").decode("ascii")

    try:
        result = client.decrypt(zelf_proof="invalid-smoke-test-proof", face_base64=dummy_face)
        print(
            "\u2705 Token accepted (request unexpectedly succeeded):",
            str(result)[:120],
        )
        return 0
    except HumanAuthnApiError as err:
        if err.status == 401:
            print(
                f"\u274c Token REJECTED by Verifik: {err.status} {err.code or ''} {err}",
                file=sys.stderr,
            )
            return 1
        print(
            "\u2705 Token ACCEPTED by Verifik. Reached the HumanAuthn pipeline; "
            f'the bogus proof was rejected as expected: {err.status} {err.code or ""} "{err}".'
        )
        return 0
    except Exception as err:
        print(f"\u274c Unexpected error reaching the Verifik API: {err}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
