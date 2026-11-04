# Tampak Chat UI and chatbot harness research

Research date: 4 November 2026. Status: planning recommendation, subject to the next design review.

## Recommendation

Use **assistant-ui’s existing Thread and Assistant Sidebar components**, shadcn/ui for the surrounding application, and **React Flow’s free components and examples** for the RAG inspector. Keep the application’s RAG execution, document permissions, provider settings, and telemetry in the Python backend. This gives Tampak-Chat a recognizable, functional chat foundation while leaving room for its distinguishing feature: inspecting what happened to a document and why a passage reached an answer.

This is a recommendation based on the documented interfaces and licensing below. It is not a completed compatibility test or the final visual design. Do not scaffold the application until the user has reviewed the planned design.

## Candidates and tradeoffs

| Candidate | Verified foundation | Fit for Tampak-Chat | Main constraint | Decision |
| --- | --- | --- | --- | --- |
| assistant-ui | React chat components, runtimes, registry source, attachments | Composable chat UI with room for a separate live inspector | A custom FastAPI stream needs an explicit adapter | Preferred chat foundation |
| shadcn/ui AI Elements and chatbot template | Copyable chat and trace patterns; minimal Next.js chatbot | Strong alternative with direct control over component source | The template uses AI SDK and Vercel Gateway by default | Preferred alternative and useful reference |
| Vercel Chatbot | Complete Next.js chatbot template | Useful reference for everyday chat interactions and persistence | Its supplied backend and services would overlap with Python responsibilities | Reference rather than full application fork |
| Open WebUI | Self-hosted chat product with uploads, tools and RAG | Useful feature benchmark and possible separate internal tool | Branding terms constrain a growing rebranded portfolio deployment | Do not use as Tampak-Chat’s foundation |
| LibreChat | Self-hosted chat product with agents, attachments and custom providers | Useful benchmark for chat controls and provider administration | Adopting the entire product introduces its own application architecture | Reference rather than full application fork |
| React Flow | React graph library, UI components and animated edge examples | Appropriate for the ingestion and retrieval inspector | Its graph renders data; backend instrumentation must supply the facts | Preferred graph foundation |

The fit and decisions in this table are our assessment. The product capabilities and license facts are sourced below.

## What to reuse

### assistant-ui

The official CLI supports existing starters and copies component source into the project. Its named components include `thread`, `thread-list`, and `assistant-sidebar`; the example catalog includes `with-external-store` and `with-assistant-transport`. These are concrete starting points for the next design proposal. [Official CLI and starter catalog](https://www.assistant-ui.com/docs/cli).

Its runtime layer can use an external application store, while history may live in the application’s own database. This supports a local deployment without requiring Assistant Cloud. [Architecture](https://www.assistant-ui.com/docs/architecture).

**Integration decision:** with a plain FastAPI application, connect our event reducer and persisted messages through `ExternalStoreRuntime`. Implement send, cancel, regeneration, and editing handlers deliberately; components alone do not persist these behaviors. The external-store documentation lists the handlers and explains streaming updates. [ExternalStoreRuntime](https://www.assistant-ui.com/docs/runtimes/custom/external-store).

The native LangGraph runtime targets the LangGraph server API and uses its SDK. Merely running a Python LangGraph object inside FastAPI does not supply that API. Choose the native runtime only if we intentionally adopt that server contract. [LangGraph runtime requirements](https://www.assistant-ui.com/docs/runtimes/langgraph/overview).

Attachments have adapter hooks for processing and upload. A model may support images but reject other binary files, so document parsing and model capability checks remain application responsibilities. Use server-side uploads and opaque attachment IDs rather than large browser data URLs. [Attachment guide](https://www.assistant-ui.com/docs/guides/attachments).

### Current shadcn alternative and AI Elements transition

The current shadcn documentation provides copyable chat, prompt input, citation, source, context, and trace patterns. It recommends its own chatbot template for new chat applications. [AI Elements patterns and migration guide](https://ui.shadcn.com/docs/ai-elements).

The older `elements.ai-sdk.dev` documentation currently announces a move to shadcn/ui and deprecation at the end of November 2026. Existing copied code continues to exist, but a new project should consult the current shadcn patterns. [Announcement on the existing Sources documentation](https://elements.ai-sdk.dev/components/sources), [shadcn October 2026 announcement](https://ui.shadcn.com/docs/changelog/2026-10-ai-elements).

The **shadcn chatbot template** is the alternative to show during design review. It supplies streaming markdown, example tools, web search and clarification questions. Its default execution path uses AI SDK and Vercel AI Gateway; adopting it would require replacing that path or explicitly adapting Python events to its stream protocol. Its README also states that its chat endpoint is public by default. Authentication, document isolation and quotas must be designed for Tampak-Chat. [Official template](https://github.com/shadcn-ui/chatbot-template).

Keep this alternative distinct from **Vercel Chatbot**, which is a fuller application template with Auth.js, Postgres persistence and Blob storage defaults. It is useful for interaction references, but importing the entire stack would duplicate parts of the planned backend. [Vercel Chatbot](https://github.com/vercel/chatbot).

### Open WebUI and LibreChat

Open WebUI documents file and image uploads, tools, knowledge bases and RAG. Its chat and corpus separation is a useful benchmark for deciding which attachment belongs only to a conversation and which belongs permanently to a chatbot. [Features](https://docs.openwebui.com/features/), [file management](https://docs.openwebui.com/features/chat-conversations/data-controls/files/).

LibreChat documents custom endpoints with separate base URLs, API keys and model lists; discovery can be enabled, while explicit defaults cover services without discovery. This is a useful administration reference, rather than proof that every compatible endpoint supports every capability. [Custom endpoint configuration](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/custom_endpoint).

LibreChat’s current repository describes unified attachments, agents, authentication and a substantial application structure. Reusing the complete product would mean extending that structure instead of building the proposed focused FastAPI service. The latter is our architectural assessment. [Official repository](https://github.com/LibreChat-AI/LibreChat).

### React Flow

React Flow UI supplies ready-made nodes, handles, status indicators and controls using shadcn/ui and Tailwind. Its animated edge example demonstrates motion along a path. Reuse those patterns for a fixed, inspectable pipeline rather than building a workflow editor. [React Flow UI](https://reactflow.dev/ui), [animated edges](https://reactflow.dev/examples/edges/animating-edges).

The free example catalog explicitly distinguishes MIT examples from Pro content. The full AI Workflow Editor is listed in the Pro template catalog, so the local implementation should use the free primitives and examples unless the user later chooses to purchase a template. [Examples and license distinction](https://reactflow.dev/examples), [Pro template catalog](https://reactflow.dev/pro/content).

## License findings

| Source | License verified during research | Implementation requirement |
| --- | --- | --- |
| assistant-ui | MIT | Retain required copyright and permission notices in reused source or distributions. [License](https://github.com/assistant-ui/assistant-ui/blob/main/LICENSE) |
| shadcn/ui and its chatbot template | MIT | Retain each source’s notices. [UI license](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md), [template license](https://github.com/shadcn-ui/chatbot-template/blob/main/LICENSE) |
| Vercel AI Elements and Vercel Chatbot | Apache 2.0 | Preserve the applicable license, notices and modification attribution for reused material. [Elements license](https://github.com/vercel/ai-elements/blob/main/LICENSE), [Chatbot license](https://github.com/vercel/chatbot/blob/main/LICENSE) |
| LibreChat | MIT | Retain required notices for reused source. [License](https://github.com/LibreChat-AI/LibreChat/blob/main/LICENSE) |
| Open WebUI | Open WebUI License with branding conditions | The official policy requires retaining branding unless an exception applies, including a deployment with no more than 50 users in a rolling 30-day period or appropriate permission/license. Do not plan an unrestricted rebrand. [Official license policy](https://docs.openwebui.com/license/) |
| React Flow library | MIT | Retain notices; check individual example/template terms before copying. [Library license](https://github.com/xyflow/xyflow/blob/main/LICENSE) |

At implementation, record exact upstream versions or commits and copied files in a third-party notices document. These findings apply to the inspected sources, not automatically to every dependency, paid asset or trademark.

## Direction for the next design proposal

**Recommended direction:** retain assistant-ui’s established sidebar, thread and composer structure, then add a resizable inspector using React Flow UI. Treat the experience as a readable chat with an optional instrument panel. The proposed originality comes from document evidence, trace transitions and precise metrics rather than replacing familiar chat controls.

The next proposal should show these concrete states before implementation:

1. Chat with the seeded technical-test bot, both inspector toggles off.
2. The same chat with live retrieval visualization and observability on.
3. An in-app source viewer opened from a citation at the correct immutable page, with the supporting passage, table cells or figure highlighted and linked to its retrieval candidate. Include multi-page navigation, unavailable-source and page-only fallback states, and a narrow-screen layout.
4. Document ingestion with parsing, cleaning, chunk boundaries and embedding status.
5. Bot and corpus management, including pending, failed and ready documents.
6. Protected provider configuration with model catalog, capability tests and masked credentials.
7. Inline analytical charts with a data-table view and source details, plus rendered procedure or relationship diagrams inside assistant messages. These remain visible with both inspector toggles off.
8. Contextual next-step buttons beneath an answer with a More actions dropdown. Show a breakdown or comparison that starts a new turn, direct source inspection, an input selector, and loading or stale states using existing UI primitives.

Show the preferred assistant-ui composition beside the current shadcn template alternative, including links to their upstream references. Use a consistent theme across chat, graph and administration. Propose typography, color, density and motion in that review; this research does not lock those decisions.

Animation must reflect backend events. A ranked list represents the returned candidate set, not necessarily every document in the corpus. Embedding plots, if shown, need a label explaining projection. A generating indicator can show elapsed time and streaming state without inventing the model’s private thoughts. Provide a textual stage list, keyboard access and reduced-motion behavior alongside the graph.

## Visual answers added to the required scope

The user explicitly requested charts, visualizations and diagrams inside chat answers. Recommend reusing shadcn/ui's chart components, which use Recharts, through a small allowed chart-spec renderer. The model selects the presentation, while a validated analytics result supplies the actual values. Show labels, units, citations, exact-value tooltips and an underlying table. [Official chart foundation](https://ui.shadcn.com/docs/components/base/chart).

For flowcharts, sequences and relationship diagrams, compile a constrained node/edge or sequence specification into Mermaid. Its documented strict mode encodes HTML tags and disables click functionality; keep configuration application-owned, disable HTML labels, validate inputs and sanitize rendering output. Treat this as an additional message renderer rather than replacing the RAG inspector's React Flow graph. [Mermaid usage and security levels](https://mermaid.js.org/config/usage.html), [configuration schema](https://mermaid.js.org/config/schema-docs/config.html).

Show both kinds of answer in the expected design: a trend question answered with a chart and table, and a procedure question answered with a cited diagram. This recommendation is based on primary documentation; no renderer integration has been implemented or tested yet.

## Limits and checks before implementation

This was a primary-source capability and licensing review, not a hands-on visual or accessibility audit. No packages were installed, no UI was implemented, and no paid template was acquired. The final dependency choices require a small integration check for our event transport, attachments, cancellation, citation rendering and persisted conversations. Recheck source versions and license text when copying components, especially during the AI Elements transition.
