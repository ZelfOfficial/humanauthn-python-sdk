# Flask integration

Adds face enrollment + authentication to a Flask backend using
[`humanauthn`](https://pypi.org/project/humanauthn/). The Verifik JWT stays on
the server; the browser only sends a base64 face image and gets your app session.

## Run

```bash
pip install flask humanauthn
VERIFIK_CLIENT_JWT=<token> python app.py
```

See the repo root [Authentication](../../../README.md#authentication-verifik-jwt)
section for how to obtain the JWT.

## Endpoints

- `POST /human-id/enroll` — body `{ userId, faceBase64 }`. Calls `encrypt`, stores
  the returned `zelf_proof` for the user.
- `POST /human-id/authenticate` — body `{ userId, faceBase64 }`. Calls `decrypt`;
  a successful decrypt is the authentication.

```bash
curl -X POST http://localhost:3000/human-id/enroll \
  -H "Content-Type: application/json" \
  -d '{ "userId": "user42", "faceBase64": "<base64>" }'

curl -X POST http://localhost:3000/human-id/authenticate \
  -H "Content-Type: application/json" \
  -d '{ "userId": "user42", "faceBase64": "<base64>" }'
```

## Notes

- Replace the in-memory dict with your real datastore; persist the `zelf_proof`
  on the user record.
- `identifier` must be alphanumeric.
- Never log `faceBase64` or the JWT. Serve over HTTPS in production.
- Get `faceBase64` from the browser with the [browser capture example](../browser).
