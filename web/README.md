# AM Web

React frontend for AM (Agent Multiverse). The current Chat flow uses the FastAPI authentication,
Thread, Agent Run, cancellation, and SSE endpoints through the Vite `/api` proxy.

## Commands

```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm test
npm run build
npm run preview
```

## shadcn/ui

Run `npm exec -- shadcn add button` from `web/` to add a shared UI component.
The CLI configuration is in `components.json`; generated components go into
`src/components/ui/`.
