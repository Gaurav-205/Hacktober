# ADR 0003: Server-rendered HTML with htmx and small ES modules

Status: accepted. Date: 2026-10-12.

## Context
One day to build; the UI is document-centric (forms, tables, an image viewer, a print layout). We want accessibility by default, no build step, a strict CSP, and a look that is not a stock component-library kit.

## Decision
FastAPI + Jinja2 templates, htmx for partial updates, vanilla ES modules for the viewer and the red-pen animation, hand-written CSS from design tokens. No SPA framework, no CSS framework, no icon font.

## Consequences
+ Fewer moving parts, faster to test, easy to print, works with a CSP of `script-src 'self'`.
+ Visual identity comes from `DESIGN.md` tokens rather than a library's defaults.
- Rich interactions (zoom/pan, box overlays) are hand-written; budgeted in Gate 3.
- No client-side routing; acceptable for this app.

## Alternatives rejected
- React/Next: build tooling and component-library look; larger surface for one day.
- Streamlit/Gradio: fast, but not controllable enough for the design, accessibility and print requirements.
