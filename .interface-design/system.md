# Tampak-Chat

Approved on 4 November 2026: **Focus**, with the sidebar expanded on hover and keyboard focus. Touch devices have an explicit toggle. Expanded navigation overlays the content instead of shifting the conversation. Pointer departure collapses it unless keyboard focus or the touch toggle keeps it open. Respect reduced motion.

Use the approved design proposal in `docs/design/DESIGN_PROPOSAL.md`. Foundations: assistant-ui thread primitives, shadcn/Radix controls, Recharts, React Flow and Mermaid. Reuse accessible primitives; application data comes from the backend, not the design fixture.

Intent: help a reviewer or visitor ask a question and inspect the evidence without losing the conversation.
Hierarchy: the answer leads; evidence, next actions and tools follow. On screens wider than 1100 px, optional inspection occupies a 360–480 px panel to the right of the chat, with independent scrolling. At 1100 px and below it docks below the thread. Metrics form two columns in the side panel; the stage graph folds into a readable two-column path rather than shrinking six nodes into one row.
Palette: neutral paper and graphite surfaces, sea-glass green for the active evidence path, amber for review. Source markers use the same identity in citations, candidates and highlights.
Depth: subtle surface differences and quiet borders, shadows only on overlays.
Surfaces: light and dark semantic tokens; controls sit slightly inset.
Typography: Plus Jakarta Sans for product text; IBM Plex Mono for numeric metrics and identifiers. Body 14–15 px; page title 24 px; metadata at least 11 px.
Spacing: 4 px base; tools 12–16 px; content 24–32 px. Controls 8 px radius, content groups 12 px, composer 16 px.

Focus navigation is 60 px collapsed and 224 px expanded. Keep icon hit targets at least 40 px and about 44 px for touch. Expansion uses label opacity and an overlay surface; never squeeze the chat text. Always preserve a visible focus indicator.

The source viewer opens the exact revision and real source location. Never manufacture PDF coordinates from generated text. Inline charts and next actions stay available with inspector toggles off.

Permanent chatbot knowledge is represented by the active knowledge count in the chat header and managed from Knowledge. Only actual conversation uploads appear in the labeled attachment tray and have a remove control. A new chat with no conversation ID must never classify permanent sources as attachments.

