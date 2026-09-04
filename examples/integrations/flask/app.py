"""Flask integration example for humanauthn.

Shows how to add face enrollment + authentication to an existing backend:

    POST /human-id/enroll { userId, faceBase64 } -> stores a zelfProof
    POST /human-id/authenticate { userId, faceBase64 } -> verifies the face

The Verifik JWT stays on the server. The browser only ever sends a base64
face image (see ../browser) and receives your own app session, never the JWT.

This is a reference snippet (not linted or type-checked by the SDK). To run it:

    pip install flask humanauthn
    VERIFIK_CLIENT_JWT=<token> python app.py
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, request
from humanauthn import HumanAuthnApiError, HumanAuthnClient

jwt = os.environ.get("VERIFIK_CLIENT_JWT")
if not jwt:
    raise SystemExit("Set VERIFIK_CLIENT_JWT (your Verifik client JWT).")

human_authn = HumanAuthnClient(jwt)

# Replace this in-memory map with your real datastore. Store the zelfProof
# (a HumanID token) on the user record; it is safe to persist.
zelf_proof_by_user: dict[str, str] = {}

app = Flask(__name__)
# Base64 face images are large; raise the JSON body limit accordingly.
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


@app.post("/human-id/enroll")
def enroll():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId")
    face_base64 = payload.get("faceBase64")
    if not isinstance(user_id, str) or not isinstance(face_base64, str):
        return jsonify({"error": "userId and faceBase64 are required"}), 400

    try:
        enrolled = human_authn.encrypt(
            face_base64=face_base64,
            identifier=user_id,  # must be alphanumeric
            public_data={"app": "my-app"},
            metadata={"userId": user_id},
            require_liveness=True,
        )
        zelf_proof_by_user[user_id] = enrolled.zelf_proof
        return jsonify({"enrolled": True}), 201
    except Exception as err:
        return jsonify({"error": _message_for(err)}), _status_for(err)


@app.post("/human-id/authenticate")
def authenticate():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("userId")
    face_base64 = payload.get("faceBase64")
    if not isinstance(user_id, str) or not isinstance(face_base64, str):
        return jsonify({"error": "userId and faceBase64 are required"}), 400

    zelf_proof = zelf_proof_by_user.get(user_id)
    if not zelf_proof:
        return jsonify({"error": "user not enrolled"}), 404

    try:
        # A successful decrypt IS the authentication.
        result = human_authn.decrypt(zelf_proof=zelf_proof, face_base64=face_base64)
        # Issue your own app session here (cookie/JWT). Do not return Verifik data.
        return jsonify({"authenticated": True, "userId": result.identifier})
    except HumanAuthnApiError as err:
        # A non-matching face surfaces as a HumanAuthnApiError.
        if not err.is_auth_error:
            return jsonify({"authenticated": False}), 401
        return jsonify({"error": _message_for(err)}), _status_for(err)
    except Exception as err:
        return jsonify({"error": _message_for(err)}), _status_for(err)


def _status_for(err: object) -> int:
    return err.status if isinstance(err, HumanAuthnApiError) else 500


def _message_for(err: object) -> str:
    # Never leak the JWT or the face image; surface only a safe message.
    return str(err) if isinstance(err, Exception) else "internal error"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="127.0.0.1", port=port)
