# Web ChatGPT

`web-chatgpt/` contains the standalone Vue 3 design prototype for the OpenGPT
conversation experience. It does not share application code with the existing
React frontend in `web/`.

The current phase focuses on the interface and local interactions. Authentication,
thread creation, Agent Runs, uploads, and SSE are not connected yet. The UI never
simulates model output or seeded conversations. Library, Agent, Image, Static,
and Sandbox are design-only App Bar surfaces until their real services are
connected.

## Commands

```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm run build
npm run preview
```

The Vite dev server keeps the `/api` proxy ready for the next integration phase.
