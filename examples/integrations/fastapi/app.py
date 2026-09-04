"""FastAPI integration example for humanauthn.

Shows how to add face enrollment + authentication to an existing backend:

    POST /human-id/enroll { userId, faceBase64 } -> stores a zelfProof
    POST /human-id/authenticate { userId, faceBase64 } -> verifies the face

The Verifik JWT stays on the server. The browser only ever sends a base64
face image (see ../browser) and receives your own app session, never the JWT.

This is a reference snippet (not linted or type-checked by the SDK). To run it:

    pip install fastapi uvicorn humanauthn
    VERIFIK_CLIENT_JWT=<token> uvicorn app:app --port 3000
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from humanauthn import HumanAuthnApiError, HumanAuthnClient
from pydantic import BaseModel

jwt = os.environ.get("VERIFIK_CLIENT_JWT")
if not jwt:
    raise SystemExit("Set VERIFIK_CLIENT_JWT (your Verifik client JWT).")

human_authn = HumanAuthnClient(jwt)

# Replace this in-memory map with your real datastore. Store the zelfProof
# (a HumanID token) on the user record; it is safe to persist.
zelf_proof_by_user: dict[str, str] = {}

app = FastAPI()


class FacePayload(BaseModel):
    userId: str
    faceBase64: str


@app.post("/human-id/enroll", status_code=201)
def enroll(payload: FacePayload) -> dict[str, bool]:
    try:
        enrolled = human_authn.encrypt(
            face_base64=payload.faceBase64,
            identifier=payload.userId,  # must be alphanumeric
            public_data={"app": "my-app"},
            metadata={"userId": payload.userId},
            require_liveness=True,
        )
        zelf_proof_by_user[payload.userId] = enrolled.zelf_proof
        return {"enrolled": True}
    except Exception as err:
        raise HTTPException(status_code=_status_for(err), detail=_message_for(err)) from err


@app.post("/human-id/authenticate")
def authenticate(payload: FacePayload) -> dict[str, object]:
    zelf_proof = zelf_proof_by_user.get(payload.userId)
    if not zelf_proof:
        raise HTTPException(status_code=404, detail="user not enrolled")

    try:
        # A successful decrypt IS the authentication.
        result = human_authn.decrypt(zelf_proof=zelf_proof, face_base64=payload.faceBase64)
        # Issue your own app session here (cookie/JWT). Do not return Verifik data.
        return {"authenticated": True, "userId": result.identifier}
    except HumanAuthnApiError as err:
        # A non-matching face surfaces as a HumanAuthnApiError.
        if not err.is_auth_error:
            raise HTTPException(status_code=401, detail={"authenticated": False}) from err
        raise HTTPException(status_code=_status_for(err), detail=_message_for(err)) from err


def _status_for(err: object) -> int:
    return err.status if isinstance(err, HumanAuthnApiError) else 500


def _message_for(err: object) -> str:
    # Never leak the JWT or the face image; surface only a safe message.
    return str(err) if isinstance(err, Exception) else "internal error"
