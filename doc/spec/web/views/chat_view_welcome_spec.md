# Design Specification: ChatView Welcome Banner

## Intended Behavior
When opening a new/empty chat thread (`messages.length === 0` and `loading === false`), the `ChatView` component will render a Welcome hint banner above the chat input box (e.g., "Welcome" / "What can I help you with today?" with a clean subtitle). When a message is sent or loaded (`composerDocked === true`), the Welcome banner is hidden and the composer docks to the bottom of the page.

## Affected Boundaries and Public Contracts
- **Affected Component**: `web/src/views/ChatView.vue`
- **Public Contracts**: None changed. Props, composable return types, and API contracts remain unmodified.

## File Modification Plan
- `web/src/views/ChatView.vue`:
  - Add a Welcome banner template block inside `<footer ...>` above `ChatMessageInputComponent`, conditionally rendered when `!composerDocked && !loading`.
  - Adjust undocked footer positioning from exact vertical centering (`absolute top-1/2 -translate-y-1/2`) to upper-middle positioning (`absolute top-[38%] -translate-y-1/2`) for better visual balance on empty threads.

## Validation Approach
- Execute `cd web && npm run build` (or `npm run type-check`) to verify TypeScript and Vue template compilation.
- Verify visually that the Welcome banner is displayed on empty threads and hidden once messages exist.
