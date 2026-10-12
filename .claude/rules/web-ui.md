---
paths:
  - "packages/munim_web/src/munim_web/templates/**"
  - "packages/munim_web/src/munim_web/static/**"
  - "packages/munim_web/src/munim_web/i18n/**"
  - "DESIGN.md"
---

# Rules for templates, styles, scripts and strings

- `DESIGN.md` is the contract. Read the section for the component you are building (section 4) before you write it.
- Colours: tokens only, through `var(--...)`. No raw hex outside `tokens.css`. Status is never shown by colour alone.
- Type: Mukta for the interface and Kalam only for corrections. Tabular lining figures for numbers, right-aligned in tables. Sentence case; the only capitals are in the stamp.
- Never use: shadows (except the marked focus ring), gradients, backdrop filters, radius above 6px, pills, emoji, icon fonts or libraries, card grids, centred body text, hover lifts, scroll or entrance animations.
- The only animated moments are the red-pen correction and the stamp. Both have a reduced-motion path.
- Every string comes from `i18n/en.json` and `i18n/hi.json` with identical keys. The copy follows `docs/CONTENT.md`. Use "evidence file" in visible English text, not "dossier".
- No inline scripts or styles (strict CSP). JavaScript lives in small ES modules in `static/js/`. Configure htmx through the `htmx-config` meta; no `hx-on`, no `js:` values, no bracketed event filters.
- Accessibility: labels tied to fields, a visible focus ring, accessible names on SVG boxes, `lang` attributes for Devanagari, `aria-live` for status changes, 44px touch targets.
- After changing a page, run `/design-pass` for it. The post-edit hook runs the design lint on every file you save.
