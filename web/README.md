# AM Web

React frontend for AM (Agent Multiverse). The current Chat flow uses the FastAPI authentication,
Thread, Agent Run, cancellation, and SSE endpoints through the Vite `/api` proxy.
The web app targets desktop browsers and uses desktop layouts throughout.

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

The `/map` page uses Mapbox GL JS with street and satellite basemaps. Add a
public Mapbox access token to `web/.env.local` before starting Vite:

```dotenv
VITE_MAPBOX_ACCESS_TOKEN=pk.your-public-token
```

The token is exposed to the browser; use a public token and configure its allowed
URLs in the Mapbox console. Restart Vite after changing the environment file.
The map supports coordinate lookup, street/satellite switching, labels, and linked
location markers. Without a token, the local illustrative example remains available.
Live place search, satellite catalog search, and Map conversation are not connected.

## Frontend conventions

Directory ownership, naming, component selection, styling, theme tokens, interaction rules,
and validation requirements are documented in
[`docs/frontend/README.md`](../docs/frontend/README.md).
