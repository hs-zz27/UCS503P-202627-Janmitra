# Janmitra browser voice interface

This Next.js application provides microphone input, streamed agent audio, call and mute
controls, and session feedback through LiveKit. The current product uses browser audio;
no telephone service is required.

Use [Run and test](../../docs/run-and-test.md) for canonical setup, startup and checks.
Node.js 22.13+ is required. The local development server binds to `127.0.0.1:3000`.

## Server and browser boundaries

`LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` belong in `.env.local`.
The server-side `/api/livekit/token` route retains the key and secret; they are never
sent to the browser. Agent names must match the worker configuration.

The token route enforces same-origin requests, creates room/participant identities,
bounds requests, limits issuance and uses short-lived grants. Hosted deployments
require `JANMITRA_HARNESS_ACCESS_CODE`; configure `JANMITRA_HARNESS_ORIGIN` behind a
reverse proxy. Multiple server instances need a shared rate limiter.

The browser displays worker readiness and safe recovery messages. A connected room or
listening state alone does not establish a completed answer. Allow microphone and
audio-playback permissions. See [Voice architecture](../../docs/voice-architecture.md)
for retrieval behavior, evaluation and current quality/reliability limits.
