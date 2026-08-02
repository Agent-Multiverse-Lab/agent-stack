# Vue Frontend Agent Guide

This file contains the frontend-specific rules for `web-chatgpt/`. The root
repository guide still applies. This Vue application is independent from the
React application in `web/`.

## Product and Technology

`web-chatgpt/` is a general-purpose AI conversation frontend. It is composed of
route-level Views, feature Components, and reusable Composables.

The frontend uses:

- Vue 3 with the Composition API and TypeScript;
- Vite 7 and Vue Router 4;
- Tailwind CSS 4 for styling;
- Lucide for interface icons;
- GSAP for authored motion;
- `markstream-vue` for assistant Markdown.

The current application is a local design prototype. Authentication,
conversation APIs, Agent Runs, uploads, and authenticated SSE streaming are not
connected. Never make an unconnected control look successful. Do not add fake
users, fake conversations, fake Agent output, simulated tool calls, seeded
content, fake uploads, or timer-driven streaming.

## Application Composition

The normal responsibility chain is:

`main.ts` -> `App.vue` -> router -> View -> feature Component

This chain describes ownership. It is not a requirement to create one file for
every visual layer.

- `src/App.vue` contains the root router outlet.
- `src/router/` maps URLs to Views and owns application-level redirects.
- `src/views/` contains route entries and route-level coordination.
- `src/components/` contains complete user-facing functions grouped by feature.
- `src/composables/` contains reusable Vue state and behavior without markup.
- `src/types/` contains shared TypeScript contracts.
- `src/styles/` contains the Tailwind entrypoint, tokens, and unavoidable global
  rules.
- `src/assets/` contains fonts and static visual assets.
- Future HTTP, upload, and SSE transport belongs in `src/api/`.

Use the `@` alias for imports from `src/`.

## Views

A View is the entry for a routed page.

- View filenames use PascalCase and end with `View.vue`.
- Views own route parameters, navigation, page-level state, and coordination.
- A View may keep one-off page chrome and layout markup inline.
- A View should import Components when the page is composed of multiple
  complete, independently nameable functions.
- Do not create a shared layout for one route. Shared route structure is
  justified only when multiple routed Views actually use it.

The main navigation routes render their Views in one persistent right-side
content region. Search and settings remain overlays because they are temporary
interactions rather than destinations.

## Components

A Component represents a complete, nameable user-facing function.

Create a Component only when at least one of these statements is true:

- it owns substantial independent interaction or lifecycle behavior;
- it is genuinely reused;
- it is a complete feature boundary that makes its parent easier to understand.

Do not extract markup merely because it has a visual boundary, a layout role,
its own CSS, or a convenient slot. Keep one-off headers, footers, rows, action
groups, empty states, icons, labels, and simple event forwarding inline in the
owning View or Component.

A cohesive Component may be long. Prefer one readable feature implementation
over a chain of small Components that only pass props and emits through several
files.

Pass parent-owned values down with typed `defineProps` and report actions or
state changes with typed `defineEmits`. Components must not mutate props.
Sibling Components communicate through their closest common parent. Do not add
a global event bus for communication inside one page.

### Component naming

- Component filenames use PascalCase and end with `Component.vue`.
- The text before `Component` must name the exact function implemented by the
  file, for example `ConversationComponent.vue`,
  `MessageInputComponent.vue`, `ConversationSearchComponent.vue`, and
  `SettingsComponent.vue`.
- Do not prefix local Component filenames or import identifiers with a product
  brand such as `OpenGpt`.
- Do not use vague structural names such as `Surface`, `Shell`, `Glyph`,
  `Wrapper`, `Container`, generic `Panel`, or similar words that do not reveal
  the function.
- Do not create standalone `Header`, `Footer`, `Item`, `Actions`, `Toolbar`, or
  `Tray` Components when they only render markup or forward props and events.
- A Component must contain only the UI and behavior required by the function in
  its filename. Do not add unrelated controls, page chrome, branding wrappers,
  or speculative future UI to make the Component look more complete.

Do not explicitly assign a Vue Component name. Do not use
`defineOptions({ name: ... })`, `defineComponent({ name: ... })`, or an Options
API `name` field. The `.vue` filename is the Component name. `defineProps` and
`defineEmits` define the public contract only.

## Feature-Based Organization

Keep Component files directly under `src/components/` while the Component set
is small. Do not create feature subdirectories in advance.

Create a feature directory only after that feature has enough tightly related
Components or local helpers that a flat list is genuinely difficult to
navigate. When a feature directory becomes necessary, use PascalCase and end
its name with `Component`, such as `ConversationComponent/`. Use the exact
product function before the suffix; do not create lowercase feature directories
or generic directories such as `ui/`, `panels/`, or `shared/`.

Do not group files by visual fragments or generic layers such as `ui/`,
`surface/`, or `panels/` when the files belong to one feature. Keep feature
state, behavior, markup, and feature-local helpers close together.

## Composables

A Composable is reusable Vue state and behavior without a template.

- Composable files and exported functions use `use<Feature>`.
- Use a Composable for cohesive state, computed values, watchers, persistence,
  or transport behavior shared by more than one owner.
- Keep HTML, CSS, icons, and presentation decisions out of Composables.
- Keep one-off UI state in its owning View or Component.
- Return only the reactive state and actions callers need.

Composables do not replace props and emits. They provide behavior to the state
owner; component-tree communication remains explicit.

## Routing, State, and API Boundaries

- Each primary navigation destination has its own URL and renders in the shared
  right-side content region.
- `/` starts a local conversation and `/c/:conversationId` opens one.
- `/library`, `/agent`, `/image`, `/static`, and `/sandbox` are feature
  destinations.
- `/login` and `/register` are standalone authentication pages.
- Do not fake route protection before authentication is connected.
- Prefer `ref`, `reactive`, and `computed` for locally owned state.
- Add a global state library only when real cross-route state cannot remain
  clear with Vue primitives and Composables.
- Persist only durable, serializable, user-created state.
- Keep dialog state, errors, pending uploads, streaming state, and abort
  controllers out of `localStorage`.
- A selected attachment is local metadata and must not be described as
  uploaded.
- Keep HTTP, upload, authenticated SSE transport, parsing, and event
  normalization outside visual Components.
- Use authenticated `fetch` streaming rather than unauthenticated `EventSource`
  for future Agent Run SSE.

## Styling, Icons, Motion, and Markdown

- Vue templates must use semantic kebab-case class names. Do not place Tailwind
  utility strings directly in `class`, `:class`, Transition class props, or
  render-time string expressions.
- Inject Tailwind utilities through the owning SFC's `<style scoped>` block
  with `@reference` to `src/styles/index.css` and `@apply`.
- Class names must describe the feature or element they identify. Use `is-*`
  names for dynamic states. Do not replace utility lists with vague numbered or
  purely visual names.
- Keep injected styles local to the owning Component or View. Use native CSS
  only where it is clearer for CSS variables, pseudo-classes, media queries, or
  values that `@apply` cannot express reliably.
- Keep global CSS limited to design tokens, font declarations, resets, and
  behavior that cannot be scoped to one template.
- `src/styles/tokens.css` is the single source of application colors, radii,
  shared dimensions, and theme-level typography. Only palette tokens may
  contain literal color values. Components and Views must consume semantic
  `--color-*` tokens; do not place hex, `rgb()`, or `hsl()` values in their
  scoped styles.
- Keep the palette compact and derive interaction surfaces, borders, overlays,
  and muted states from it. Add a semantic token only for a real visual role;
  do not create a full numbered color scale speculatively.
- Tailwind remains the utility system and CSS custom properties remain the
  runtime theme boundary. Do not add Less only to centralize colors or theme
  values.
- If another theme mode is implemented, override the existing semantic tokens
  from one root theme selector. Keep theme selection and persistence in one
  state owner; Components must not set root theme classes independently.
- Use existing design tokens before adding new colors, radii, shadows, or
  dimensions.
- Use Lucide for common interface icons. Do not add another icon library or
  hand-draw common controls.
- Keep product artwork as a static asset instead of wrapping it in a Vue
  Component without functional behavior.
- Use Tailwind or CSS for simple hover, focus, color, and opacity transitions.
- Use GSAP for authored sequences, coordinated DOM/SVG motion, and timelines.
- Create GSAP work after mount, scope it to the owning element, clean it up on
  unmount, and respect `prefers-reduced-motion`.
- Render assistant Markdown through one
  `MarkdownRendererComponent.vue` backed by `markstream-vue`.
- Do not use `v-html` for untrusted user or model content.

Maintain the restrained conversation-product visual language: practical
density, weak borders, stable surfaces, clear focus states, and responsive
layouts.

## Vue and TypeScript Style

- Use `<script setup lang="ts">`.
- Use 2-space indentation.
- Keep imports grouped as external packages, `@/` imports, then relative
  imports.
- Keep props, emits, route contracts, and shared domain objects typed.
- Prefer direct code over factories, generic wrappers, or configuration for one
  value.
- Do not add an abstraction for a possible future caller.
- When renaming a file, update its imports, router records, and references in
  the same change.

## Verification

Run:

```bash
npm run typecheck
npm run lint
npm run build
git diff --check -- web-chatgpt
```

For visual changes, verify affected routes at desktop and mobile widths. Check
sidebar collapse and drawer behavior, composer overlap, local-only states,
keyboard focus, and reduced-motion behavior.

## Security and Contributions

- Keep secrets out of the repository.
- Expose only client-safe configuration through `VITE_*` variables.
- Validate API payloads and file metadata before sending them.
- Follow the root repository Conventional Commit rules.
- Keep the lowercase English commit type and scope, and use a concise Chinese
  subject and body.
- Never wrap commit messages in `@` characters.
