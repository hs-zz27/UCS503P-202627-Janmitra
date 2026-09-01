# Janmitra browser harness

This Next.js application is a development interface for joining the Janmitra LiveKit
agent from a browser. It is not the citizen-facing phone channel.

```powershell
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Configure `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in `.env.local`.
The key and secret are read only by the server-side `/api/livekit/token` route and are
never sent to the browser.

Run the checks with:

```powershell
npm run lint
npm run build
npm audit
```
