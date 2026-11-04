# Tampak-Chat design proposal

4 November 2026 · Approved direction: Focus

The user approved **Focus**: a compact navigation rail, a wider conversation and an inspector below it. The rail expands from 60 to 224 px on hover or visible keyboard focus, overlays the conversation, and has an explicit touch toggle. The working application follows this direction.

The original interactive preview remains a fictional design prototype. The implemented application uses real backend data, durable worker events, protected administration and source provenance. Verification and screenshots are recorded in [the verification report](../VERIFICATION.md).

## Existing foundations

| Part | Upstream reference | Adaptation for Tampak-Chat |
| --- | --- | --- |
| Main conversation and composer | [assistant-ui Thread](https://www.assistant-ui.com/elements/thread) and [Assistant Sidebar](https://www.assistant-ui.com/elements/assistant-sidebar) | Bot-scoped navigation, source chips, attachments and independent inspector toggles |
| Evidence and suggested actions | [Document Reference](https://www.assistant-ui.com/elements/document-reference) and [Retrieval Chunks](https://www.assistant-ui.com/elements/retrieval-chunks) | One evidence identity from a citation to its candidate and document highlight |
| Controls and chart composition | [shadcn Sidebar](https://ui.shadcn.com/docs/components/base/sidebar) and [Chart](https://ui.shadcn.com/docs/components/base/chart) | Consistent application forms, buttons, tabbed chart/table view and context menus |
| Alternative layout | [shadcn chatbot template](https://github.com/shadcn-ui/chatbot-template) | More open conversation canvas and an inspector below the answer |
| Execution inspector | [React Flow UI](https://reactflow.dev/ui) | Fixed pipeline nodes, stage status and evidence selection, not a workflow editor |

The preview renders these compositions independently for review. It does not claim the upstream React packages are already integrated. During implementation, reuse their components and primitives rather than rebuilding their interaction behavior. Preserve the applicable license notices when copying source.

## Intent and visual direction

The reviewer should be able to ask a business question, assess its answer, then follow the evidence without losing their place. The portfolio visitor should be able to make a temporary bot and understand how its documents become searchable. The interface should feel like a calm analysis desk with useful instruments within reach.

**Domain:** evidence, source passages, index cards, document margins, retrieval ranks, calculation results, execution traces and instrument readouts.

**Color world:** paper, graphite, sea-glass green, pale highlight ink, muted amber for review, and cool gray for inactive connections. Use a largely neutral canvas. Green identifies the active evidence path and successful ready states; amber identifies something needing attention. The same identity appears on a citation marker, candidate, source region, chunk and selected context.

**Signature:** a visible evidence trail connects the answer to the specific material used. The inspector is optional; the evidence remains directly accessible in normal chat.

**Choices to avoid:** decorative chatbot avatars give way to a small aperture mark and readable messages; an always-visible debugging dashboard gives way to independent Pipeline and Metrics toggles; generic next-question lists give way to actions tied to the actual result.

## Shared system

Use Plus Jakarta Sans for product text and IBM Plex Mono for identifiers and compact numeric readouts. The base size is 14 px, body reading text is 14–15 px, and page headings are 24 px with a clear weight hierarchy. Use a 4 px spacing grid; 12–16 px in tools and 24–32 px around conversation content. All text remains at least 11 px, with larger form text on touch devices.

The depth strategy is subtle surface separation with quiet borders; reserve shadows for an actual overlay. Controls use 8 px radii, grouped content 12 px, and the composer 16 px. Make focus visible and provide keyboard-accessible controls. Follow light and dark appearance; use restrained motion and reduced-motion support.

| Component | Intent and hierarchy | Geometry and behavior |
| --- | --- | --- |
| Navigation | Keep the active bot and its sources recognizable | Workbench uses a 196 px sidebar; Focus uses a 60 px rail; collapse into a menu on narrow screens |
| Conversation | The answer is the focal content | Maximum reading width around 680 px; prose leads; compact supporting evidence and actions follow |
| Chart | Explain a change with exact values | Neutral plot area, one persistent data color, explicit units, direct labels, Chart/Data tabs |
| Source viewer | Inspect what a citation actually supports | Opaque source panel; clear page number, highlighted passage, adjacent-page controls and unavailable/page-only states |
| Pipeline | Explain the executed stages | Compact staged path, candidate ranks and selected context; explicit preview animation in this prototype |
| Metrics | Inspect execution cost without overwhelming chat | Compact strip plus a detailed panel, estimated/reported labels and stable numeric widths |
| Upload and extraction | Select a method and inspect the outcome | Native, layout/OCR, figure enrichment and page vision; advanced options; original/extracted comparison and review state |
| Admin | Configure models with clear capability boundaries | Protected-entry preview, masked credentials, chat and vision role assignments, pinned OpenRouter Nemotron embedding profile and a capability matrix; no actual secrets in the prototype |

## Review journey

Start with the seeded operations conversation. Open a citation and inspect its highlighted page; switch the chart to a table or channel breakdown; use a suggested action. Turn Pipeline and Metrics on separately, and play the labeled sample trace. Open Knowledge, select processing methods, and inspect the extraction preview. Open Chatbots to create a sample temporary bot. Open Admin to inspect the login and configuration layouts.

The Workbench inspector sits beside chat on desktop. Focus puts the same inspector below it. At narrow widths, both layouts use a compact header and stacked panels so source inspection does not compress the answer into an unreadable column.

The embedding default is the user's selected OpenRouter `nvidia/nemotron-3.5-embed-8b:free`, with its documented full 4,096-dimensional output. The admin preview shows it as a fixed profile with a separate server-side key. Upload explains that indexing still sends extracted text remotely even when parsing runs locally, and the chosen free endpoint excludes confidential and personal data. [OpenRouter API](https://openrouter.ai/docs/api/reference/embeddings), [model and data-use notice](https://openrouter.ai/nvidia/nemotron-3.5-embed-8b:free).

Inspect loading, ready, review-needed, unavailable-source and missing-capability states as part of this review. The actual source pages, timings, token counts and price estimates shown here are fictional design data, not measured application results.

The prototype was checked in Chromium at desktop, tablet and phone widths, including a 320 px content area. Verified interactions include source navigation, chatbot creation, chart switching, suggested actions, diagram rendering, the admin preview, the pinned embedding profile and disabled vision methods when no vision profile is selected. Light and dark states were inspected, and the exercised views produced no JavaScript errors or horizontal overflow. These are prototype checks, not verification of a running RAG backend or a live OpenRouter integration.

The selected composition and any changes from review will become the implementation design system. No final direction is locked by this proposal.
