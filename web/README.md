# AM Web

React frontend for AM (Agent Multiverse). The current Chat flow uses the FastAPI authentication,
Thread, Agent Run, cancellation, and SSE endpoints through the Vite `/api` proxy.

## Technology stack

- React, TypeScript, Vite, React Router, and React Context.
- All shared UI and interactive primitives use shadcn/ui components based on Base UI, with Tailwind CSS v4 and Lucide icons.
- Browser `fetch` for API and SSE communication; Vite proxies `/api` to FastAPI during development.
- npm, TypeScript, ESLint, and Vitest for development and validation.

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

## Map page

The `/map` page uses TianDiTu imagery as its basemap. Add a browser-side TianDiTu
key to `web/.env.local` before starting Vite:

```dotenv
VITE_TIANDITU_TK=your-browser-key
```

The key is exposed to the browser; configure the allowed website origin in the
TianDiTu console. Satellite catalog search and Map conversation are not connected
on this initial page.
