# Browser capture

Minimal front-end that grabs a `faceBase64` from the webcam and POSTs it to your
backend (the [Flask](../flask) or [FastAPI](../fastapi) example). The Verifik
JWT never touches the browser — the client only sends a base64 image and receives
your app's own session.

## How it works

[`capture.html`](capture.html):

1. `navigator.mediaDevices.getUserMedia({ video: true })` to open the camera.
2. Draw the current video frame onto a `<canvas>`.
3. `canvas.toDataURL("image/jpeg")` and strip the `data:` prefix to get raw
   base64.
4. `POST { userId, faceBase64 }` to `/human-id/enroll` or
   `/human-id/authenticate`.

```js
canvas.getContext("2d").drawImage(video, 0, 0);
const faceBase64 = canvas.toDataURL("image/jpeg", 0.9).split(",")[1];
await fetch("/human-id/enroll", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ userId, faceBase64 }),
});
```

## Notes

- Serve over HTTPS (or `localhost`); `getUserMedia` requires a secure context.
- The SDK also accepts a full `data:image/...;base64,...` URI, so passing the
  whole `toDataURL()` result works too.
- Point the `fetch` paths at your backend origin if the API is hosted elsewhere.
