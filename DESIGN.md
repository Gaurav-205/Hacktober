---
name: Munim
version: 1.0.0
format: DESIGN.md (Google Stitch format, sections as in VoltAgent/awesome-design-md)
description: >
  Design system for Munim, an open-source tool that turns phone photos of
  invoices, delivery challans and purchase orders into a verified evidence
  file for a small supplier chasing a late payment. The look comes from the
  paper trail itself: carbon-copy challan books, ballpoint ink, an auditor's
  red pen, and a rubber "Checked" stamp.
colors:
  bond: "#F3F4F6"            # page background, the desk the papers sit on
  sheet: "#FFFFFF"           # every document, panel and form surface
  ink: "#15171C"             # primary text
  ink-2: "#4A4F5A"           # secondary text
  muted: "#5C6272"           # captions, helper text (5.5:1 on bond)
  hairline: "#D5D8DE"        # decorative dividers only, never a control edge
  hairline-strong: "#80879A" # control edges, table rules; must sit on sheet
  ballpoint: "#1F3DB8"       # the one accent: actions, links, selection, corrections
  ballpoint-pressed: "#162E91" # hover and pressed state of the primary button
  ballpoint-wash: "#E6EBFA"  # selected row, active sheet
  red-pen: "#C4281C"         # a check failed; strike-through of a wrong value
  red-wash: "#FBE4E1"
  tick: "#1E7A4F"            # a check passed
  tick-wash: "#E3F2EA"
  highlighter: "#F5D547"     # needs a human; never used for text
  highlighter-wash: "#FBF1C4"
  carbon-pink: "#F2D4CF"     # challan duplicate sheet; delivery proof
  carbon-yellow: "#F3E7B0"   # triplicate sheet; purchase order
typography:
  family-ui: "Mukta, 'IBM Plex Sans', 'Noto Sans Devanagari', system-ui, sans-serif"
  family-hand: "Kalam, 'Noto Sans Devanagari', cursive"
  display-amount: { family: ui, size: 56px, line: 60px, weight: 600, tracking: -0.02em, features: [tnum, lnum] }
  display: { family: ui, size: 34px, line: 40px, weight: 600, tracking: -0.01em }
  h1: { family: ui, size: 32px, line: 38px, weight: 600, tracking: -0.01em }
  h2: { family: ui, size: 24px, line: 30px, weight: 600 }
  h3: { family: ui, size: 18px, line: 26px, weight: 600 }
  body: { family: ui, size: 16px, line: 26px, weight: 400 }
  body-sm: { family: ui, size: 14px, line: 22px, weight: 400 }
  label: { family: ui, size: 13px, line: 18px, weight: 500, case: sentence }
  number: { family: ui, size: 16px, line: 23px, weight: 500, features: [tnum, lnum] }
  check: { family: ui, size: 15px, line: 20px, weight: 500 }
  hand: { family: hand, size: 20px, line: 28px, weight: 400 }
rounded:
  field: 2px      # a printed box on a form
  panel: 6px      # sheets and panels
  stamp: 3px
  none: 0px
spacing: { base: 4px, scale: [4, 8, 12, 16, 24, 32, 48, 64] }
motion:
  stamp: { duration: 160ms, easing: "cubic-bezier(.2,.9,.3,1.2)", from: "scale(1.18) rotate(-4deg)", to: "scale(1) rotate(-2deg)" }
  strike: { duration: 220ms, easing: "ease-out" }
  write: { duration: 380ms, easing: "steps(18, end)" }
  reduced-motion: "all of the above become instant state changes"
---

# Munim design system

This file is the single source of truth for how Munim looks and reads. A coding
agent must treat it as a contract: tokens are exported to CSS custom properties
by `scripts/build_tokens.py`, and `scripts/design_lint.py` fails the build when
the UI drifts from it (see "Design lint" at the end).

**Provenance, stated plainly.** The structure of this file follows the DESIGN.md
format collected in [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)
(MIT licence; the format is derived from Google Stitch): YAML tokens first,
then Visual Theme, Color, Typography, Components, Layout, Elevation, Do's and
Don'ts, Responsive Behaviour and an Agent Prompt Guide. From the WIRED file in
that collection I took one idea only: depth comes from surface contrast and
borders, never from drop shadows. No palette, type or component from any
existing brand file is reused, because none of them describes this product and
copying a known brand would make Munim look like a template.

---

## 1. Visual theme and atmosphere

**Subject.** A small supplier in an industrial cluster, an accountant at a
cyber cafe, or a shopkeeper's son. They hold a pile of paper: a tax invoice, a
delivery challan with a receiver's stamp, a purchase order, usually as WhatsApp
photos. They need to know three things: is each paper readable and consistent,
what does the law say they are owed, and can they hand someone a file that proves it.

**Concept: the challan book.** Indian challan and bill books are bound pads of
numbered, carbon-interleaved sheets: white original, pink duplicate, yellow
triplicate. The accountant checks them with a ballpoint, marks errors in red pen
and stamps the page. Munim borrows this working vocabulary and nothing else.

- The three sheet colours are not decoration. They encode document type everywhere:
  white is the tax invoice, carbon pink is the delivery challan (proof of delivery),
  carbon yellow is the purchase order.
- Ink colours encode who wrote what. Printed or typed text is `ink`. Anything a
  person or Munim corrected is written in `ballpoint`, in the handwriting face.
  A wrong value is struck through in `red-pen`. A passed check is a small `tick` mark.
- The interface is calm, flat and document-like. It should feel like a tidy desk,
  not a dashboard.

**The one memorable thing (and only one): the red-pen correction.** When Munim
re-reads a value because a check failed, the user watches the old value get struck
through in red and the corrected value written beside it in ballpoint handwriting,
with the reason underneath. When every blocking issue is resolved and the person
confirms, a rubber stamp lands on the document. Everything else is quiet so these
two moments carry the product.

**Atmosphere words:** orderly, unhurried, trustworthy, a little worn, never glossy.

### Key characteristics
- Cool off-white desk (`bond`) with pure white sheets (`sheet`). Not cream, not dark.
- One accent, ballpoint blue. Status colours appear only on status.
- Two typefaces with different jobs: a clear Latin plus Devanagari sans for the interface,
  a handwriting face used only for corrections and margin notes.
- Rectangles with small radii, like printed boxes. No pills, no circles except avatars (there are none).
- No shadows, no gradients, no glass, no emoji, no scroll animations.
- Hindi and English are equal citizens: every screen is designed and tested in both.

---

## 2. Colour palette and roles

| Token | Hex | Role | Notes |
| --- | --- | --- | --- |
| `bond` | `#F3F4F6` | Page background | The desk. Text on it must be `ink`, `ink-2` or `muted`. |
| `sheet` | `#FFFFFF` | Documents, panels, forms, table bodies | Controls (inputs, checkboxes) sit only on `sheet`. |
| `ink` | `#15171C` | Primary text, printed content | 16.3:1 on bond, 17.9:1 on sheet |
| `ink-2` | `#4A4F5A` | Secondary text | 7.5:1 on bond |
| `muted` | `#5C6272` | Captions, helper text, timestamps | 5.5:1 on bond, 6.1:1 on sheet |
| `hairline` | `#D5D8DE` | Decorative separators | Never the only boundary of a control |
| `hairline-strong` | `#80879A` | Input borders, table rules | 3.59:1 on sheet, 3.26:1 on bond (both clear the 3:1 minimum for UI edges) |
| `ballpoint-pressed` | `#162E91` | Primary button hover and pressed | White text on it 11.5:1 |
| `ballpoint` | `#1F3DB8` | Primary actions, links, selection, handwritten corrections | 8.7:1 on sheet |
| `ballpoint-wash` | `#E6EBFA` | Selected row, active thumbnail | Text on it is `ink` |
| `red-pen` | `#C4281C` | Failed check, strike-through | 5.7:1 on sheet, 5.2:1 on bond, 4.7:1 on its own wash. Do not put red text on `carbon-pink` |
| `red-wash` | `#FBE4E1` | Background of a failed row | Text on it is `ink` |
| `tick` | `#1E7A4F` | Passed check | 5.3:1 on sheet, 4.8:1 on bond, 4.6:1 on its own wash |
| `tick-wash` | `#E3F2EA` | Background of a passed row | Text on it is `ink` |
| `highlighter` | `#F5D547` | A mark that says "check by hand" | A fill only, never text colour |
| `highlighter-wash` | `#FBF1C4` | Background of a needs-review row | Text on it is `ink` |
| `carbon-pink` | `#F2D4CF` | Challan sheet tab, dossier computation band | Text on it is `ink` (12.9:1) |
| `carbon-yellow` | `#F3E7B0` | Purchase-order sheet tab | Text on it is `ink` |

**Rules**
1. Every colour in CSS, templates and SVG must be one of the tokens above, read through `var(--…)`.
   Raw hex values outside `tokens.css` fail the design lint.
2. Status is never colour alone. Each status pairs colour with a word and a mark
   (tick, strike, or a hand-pointing bracket for "check by hand").
3. Status text (`red-pen`, `tick`) appears only on `sheet` or `bond` or on its own wash, never on the carbon colours.
4. `scripts/check_contrast.py` reads this file's front matter, tests every foreground and
   background pair listed in the table, and fails below 4.5:1 for text and 3:1 for UI edges.
5. No dark mode in v1. The product is used in bright rooms and printed on paper. Do not add
   `prefers-color-scheme` rules; state this in the README as a known limit.

---

## 3. Typography rules

**Families**
- **Interface: Mukta** (Latin and Devanagari in one family, Ek Type, SIL Open Font License).
  It was designed for Indian scripts, which is the reason to choose it over a default
  Western grotesque. Self-host the WOFF2 files in `packages/munim_web/src/munim_web/static/fonts/`; the app must work offline.
- **Hand: Kalam** (Latin and Devanagari handwriting, Indian Type Foundry, SIL OFL).
  Used for corrections, margin notes, and nothing else. Never for body copy or labels.
- **Verification step.** Before committing fonts run `scripts/check_fonts.py` (fontTools): it must
  confirm Devanagari coverage, OFL licence text in the font files, and the `tnum` and `lnum`
  OpenType features for Mukta. If Mukta lacks `tnum`, switch the interface family to
  **IBM Plex Sans with IBM Plex Sans Devanagari** (OFL) and update the front matter.
  (Checked 12 Oct 2026: Mukta 5.3.0 from Fontsource has `tnum`; it has no `lnum` feature because its
  figures are lining by default, with no `onum`. `check_fonts.py` accepts lining-by-default.)
- Include each family's licence file under `packages/munim_web/src/munim_web/static/fonts/LICENSES/` and list them in `THIRD_PARTY.md`.

**Scale** (rem values assume 16px root)

| Style | Size / line | Weight | Use |
| --- | --- | --- | --- |
| display-amount | 56 / 60 | 600, tabular lining figures | The amount owed in the clock strip and on the evidence file cover |
| display | 34 / 40 | 600 | The overall verdict word for a case |
| h1 | 32 / 38 | 600 | Page title (case name) |
| h2 | 24 / 30 | 600 | Panel titles |
| h3 | 18 / 26 | 600 | Field group titles |
| body | 16 / 26 | 400 | Running text, notices |
| body-sm | 14 / 22 | 400 | Table cells, helper text |
| label | 13 / 18 | 500 | Form labels; sentence case, no tracking |
| number | 16 / 23 | 500, tabular lining figures | Every amount, date, quantity and identifier |
| check | 15 / 20 | 500 | The verdict word inside a claims row |
| hand | 20 / 28 | 400 | Corrections and margin notes, never below 18px |

**Principles**
- Line length under 72 characters for running text. The notice and dossier text blocks are capped at `max-width: 68ch`.
- All amounts, dates, quantities and identifiers use `number` so columns align. Amounts are right-aligned.
- Money format: Indian digit grouping with a rupee sign and exactly two decimals: `₹1,25,000.00`. In Hindi UI the digits stay Latin
  (as printed on the papers); the number formatter is a tested function, never ad-hoc string code.
- Devanagari text gets +0.1 line-height (`:lang(hi)`), and no letter-spacing is ever applied to it.
- Sentence case everywhere. No all-caps labels, no tracked eyebrow text above headings.
  The only capitals are inside the stamp graphic, because stamps are printed in capitals.
- Headlines are plain. Do not italicise, bold or recolour a single word in a heading for effect.
- Identifiers (GSTIN, PAN, invoice numbers) are copyable, show a visible group rhythm
  (`27 AAPFU0939F 1 Z V`) and never wrap mid-token. The groups are adjacent inline spans with a
  2px margin between them and no space characters, inside a `white-space: nowrap` element, so a copy
  gives the contiguous characters. Identifiers are never truncated.

---

## 4. Component stylings

All components below are implemented once as Jinja macros in `packages/munim_web/src/munim_web/templates/components/`
and styled in `packages/munim_web/src/munim_web/static/css/components.css`. Names are stable; tests refer to them.

### 4.1 Buttons
- **Primary:** background `ballpoint`, text `sheet`, `rounded.field`, height 44px (the touch-target minimum), padding 0 16px, weight 500.
  Hover darkens by switching to a second declared token `ballpoint-pressed` (`#162E91`, add to tokens).
  Focus: 2px `ballpoint` outline with 2px `sheet` gap outside. One primary button per view.
- **Secondary:** background `sheet`, 1px `hairline-strong` border, text `ink`.
- **Quiet:** no border, text `ballpoint`, underline on hover. For in-table actions.
- **Danger:** secondary style with text and border `red-pen`; used only for "Delete this case".
- Labels name the action: "Check this paper", "Open evidence file", "Delete case". Never "Submit", never an arrow glyph appended.

### 4.2 Inputs and forms
- Label above the field (13px/500). Helper text below in `muted`. The field is `sheet`, 1px `hairline-strong`, `rounded.field`, 44px tall. An input always sits on `sheet`, also when its row is washed (the edit cell gets a `sheet` background).
- Error: border and message in `red-pen`, message names the rule and what to do ("Invoice date is after the due date. Enter the date printed on the invoice.").
- Date fields accept `DD/MM/YYYY` as typed on Indian papers and show the parsed date in words next to the field ("12 October 2026") so a swapped day and month is visible.
- Money fields accept Indian grouping while typing and store integer paise.

### 4.3 The sheet (document panel)
- A white panel, `rounded.panel`, 1px `hairline-strong` border. A 6px-wide left edge tab in the document-type colour
  (white sheet gets a `hairline-strong` tab, challan `carbon-pink`, purchase order `carbon-yellow`).
- **Sheet stack (case card).** Up to three outline-only copies of the sheet offset 4px and 8px down-right behind the front one
  (1px `hairline-strong` borders on `bond`, no fill, no blur). This is the only depth device in the product.

### 4.4 Document viewer
- The photo sits on `sheet` with its own aspect ratio. Zoom and pan with pointer and keyboard (`+`, `-`, arrow keys, `0` to reset).
- Field boxes are 2px outlines in the status colour with a 2px `sheet` inner gap so they stay visible on dark photo areas: solid `tick` for Passed, solid `red-pen` for Doesn't match, and a dashed `ink` outline for Check by hand (`highlighter` is only 1.45:1 on white, so it is never an outline). They are SVG, not canvas, so they take focus and have accessible names.
- Selecting a row in the claims table focuses its box and vice versa. The selected box gets a `ballpoint-wash` fill at 40% opacity.

### 4.5 Claims table (what Gemma read)
Columns: Field, Value read, Check, Source.
- Row height 48px minimum. Header 13px/500 `ink-2`, bottom rule `hairline-strong`.
- **Check cell** contains a status mark and a word: tick and "Passed", strike and "Doesn't match", bracket and "Check by hand". The row background takes the status wash when the status is not Passed. A selected row gets a 2px `ballpoint` left rule (and `ballpoint-wash` only on Passed rows); the check word stays `ink` on any wash, with the mark in the status colour. The check word may wrap under its mark.
- Below 1440px the Source crop sits under the value instead of in its own column. A correction always stacks: struck original above, handwriting below.
- **Source cell** shows a 64x40 crop of the box from the photo, or "Not found on the paper" in `muted`.
- Edited values appear in the hand face in `ballpoint`, with the original struck through in `red-pen` above or beside it. Do not hide the original.
- Keyboard: arrow keys move between rows, Enter edits, Escape cancels.

### 4.6 Verdict chip
Rectangular, `rounded.field`, 24px tall, 1px border in the status colour, background the status wash, text `ink`, a 12px mark at the left. Not a pill.

### 4.7 The stamp
- A rectangle with a 2px double border in `ballpoint`, `rounded.stamp`, rotated -2 degrees, containing two centred lines: the word "CHECKED" (the one allowed capitalised word) and the date as `12 Oct 2026`.
- It appears once, on the front sheet of the dossier preview and on the first page of the printed dossier, only when every blocking finding is passed or explicitly accepted by the user and the user has pressed "Confirm these values".
- The stamp is an SVG with its text as real `<text>` for accessibility, and it prints.

### 4.8 The red-pen correction
Sequence, each step as a state change that also works with reduced motion (steps 2 and 3 become instant):
1. The failed value shows with a `red-wash` row and the message from the rule.
2. A red-pen strike (a slightly wavy SVG path, 2px, `red-pen`) draws across the old value over `motion.strike`.
3. The corrected value is revealed to the right in the hand face, `ballpoint`, with a left-to-right `clip-path` reveal over `motion.write`.
4. A line under it in `muted` body-sm says what happened: "Re-read from the marked box. GSTIN checksum now passes."
If the re-read still fails, no handwriting appears; the row becomes "Check by hand" with the reason, and the box stays highlighted.

### 4.9 Clock strip
A full-width strip at the bottom of the workbench on `sheet` with a top rule. Left to right: Delivered on, Due on, Days late, Interest to date, Amount owed (the `display-amount`). Each has a label (13px) above its value. Inside the strip, a single link opens the working: "How this is worked out". No sparkline, no progress ring.

States (every number has a source, so the strip never fills a default the person did not give):
- **Input missing:** no delivery date, no agreement choice, or no credit days with a written agreement. The strip names what is missing and links to that field. No amount is shown.
- **No Bank Rate:** a period starts before every Bank Rate row. The strip says "Add a Bank Rate effective on or before <date>" and links to the table.
- **Provisional:** all inputs exist but the values are not confirmed. Figures show with the label "Provisional until you confirm the values".
- **Not yet late:** the as-on date is on or before the due date. Days late 0, interest ₹0.00.
- **Interest off:** the supplier is a medium enterprise and "Calculate anyway" is not chosen. The strip shows the due date and the explanatory note.
- **Bank Rate not confirmed:** a note under the strip (`clock.rate.unconfirmed`).

### 4.10 Tables of documents (case list)
A plain table, not a card grid: Case, Parties, Papers (shown as up to three small coloured sheet tabs), Amount owed, Updated. Row height 56px. The page's primary action is "New case" (a case must exist before a paper can be added; "Add a paper" is the workbench's action). The empty state is a sheet with a tear-off dotted line and the sentence "No cases yet. Start a case, then add its papers: a tax invoice, a delivery challan and a purchase order." plus the primary button "New case".

### 4.11 Dropzone
A `sheet` with a 2px dotted top rule (like a tear-off line) and the text "Drop a photo or PDF here, or choose a file." No dashed border, no cloud icon, no animation. During drag-over the border becomes `ballpoint`. After choosing, the file name, size and a thumbnail appear.

### 4.12 Notices and messages
- Inline messages sit in `sheet` with a 4px left rule in the status colour and the text in `ink`. No toasts for errors. A toast is allowed only for "Copied" and "Saved", bottom-left, auto-dismiss after 4 seconds, `aria-live="polite"`.
- Errors state what happened and what to do, in plain words, without apology or mood: "This photo is too dark to read the stamp date. Retake it in daylight or enter the date by hand."

---

## 5. Layout principles

**Grid.** 4px base. Content max width 1440px. The workbench uses three columns on desktop; everything else is a single column with a 720px reading width, left aligned. Do not centre-align body text, headings or forms. Centre alignment is allowed only inside the stamp and the empty-state sentence.

**Pages**

1. **Cases** (`/`): header, table of cases, "New case".
2. **Workbench** (`/cases/{id}`): the main screen.
3. **Dossier** (`/cases/{id}/dossier`): screen preview and print layout.
4. **Rules and sources** (`/rules`): the rule set in use, versions, bank-rate table, links to the sources.
5. **About** (`/about`): what it is, licence, model licence, privacy in five sentences.
6. **How well it reads** (`/evaluation`): the latest evaluation report as one table and a short list of failure examples, single 720px column. A replay run is labelled as recorded responses, never as a live read.
7. **Settings** (`/settings`): reader choice, the preflight report with plain fixes, the hosted-model consent line, and language. Single 720px column.

**Workbench wireframe (≥1200px)**

```
+----------------------------------------------------------------------------+
| Munim        Shree Ram Fabricators and Delta Textiles       Open evidence file |  56px header on bond
+---------+--------------------------------------------+---------------------+
| Papers  |  Tax invoice 2025-26/0412                   | What Gemma read      |
| [inv ]  |  +---------------------------------------+  | Field   Value  Check |
| [chal]  |  |                                       |  | GSTIN   27AAP.. tick |
| [PO  ]  |  |   photo with outlined field boxes     |  | Total   12,500 strike|
|         |  |                                       |  |   12,500 -> 15,200   |
| Add a   |  +---------------------------------------+  | Date    14/07  hand  |
| paper   |   zoom - / + / fit                          | 3 checks passed      |
+---------+--------------------------------------------+---------------------+
| Delivered 14 Jul 2026 | Due 28 Aug 2026 | 76 days late | Interest ₹ | ₹ OWED  |
| How this is worked out                                                       |
+----------------------------------------------------------------------------+
```

Column widths: papers rail 200px, viewer fluid (min 480px), claims panel 400px. The claims panel scrolls independently; the clock strip is sticky.

**Alignment guidance.** Text left-aligned. Numbers right-aligned in tables. Labels above fields. Table headers align with their column content.

**Rhythm.** Panel padding 24px. Gap between panels 16px. Heading to content 12px. Do not use identical vertical padding on every block; spacing follows the grouping of the content.

**Dossier print layout (A4, 18mm margins)**

```
Page 1  Summary: parties, invoice, amount, due date, days late, interest, total owed, the stamp, list of assumptions
Page 2  Evidence table: each field, the value, the check, a crop of the source box
Page 3  The working: steps of the payment-clock calculation with the rule version and bank rate used
Page 4+ The originals: each photo at full width with its boxes
Last    Draft notice (English and Hindi), clearly marked as a draft for the user to review
```
Page headers carry case name and page number in `body-sm`. The page 3 band is `carbon-pink` and the page 4 band is `carbon-yellow` only when they contain the challan and the purchase order respectively. Print CSS uses `@page`, `break-inside: avoid` on evidence rows, and no background images.

---

## 6. Depth and elevation

| Level | Treatment | Use |
| --- | --- | --- |
| 0 | `bond` background | The desk |
| 1 | `sheet` with 1px `hairline-strong` border | Panels, tables, forms |
| 2 | Offset outline copies (sheet stack) | Case rows with several papers; the stamped front sheet |
| Focus | 2px `ballpoint` outline offset 2px | Any focused control |

There are no drop shadows, no blurs, no gradients and no translucency except the 40% `ballpoint-wash` on a selected box. The only permitted `box-shadow` is the focus ring, if an outline cannot be used.

---

## 7. Do's and Don'ts

**Do**
- Show the evidence next to every number: a crop of the box, the rule that checked it, the rule version.
- Say "Passed" or "Doesn't match", never "Verified" or "Correct". A checksum passing is not proof the value is right.
- Keep corrections visible: original struck through, new value in ballpoint, reason beneath.
- Write sentence case, active voice, plain verbs: "Check this paper", "Delete case", "Copy notice text".
- Give each empty state a next action. Give each error a cause and a fix.
- Test every screen in Hindi, with long Devanagari strings, at 200% zoom and at 360px width.
- Keep real names and numbers in demo data realistic and clearly synthetic ("Sample Fabricators Pvt Ltd"), never a real company.

**Don't**
- No purple or blue-purple gradients, no mesh or aurora backgrounds, no glassmorphism, no neon on dark.
- No cream-and-terracotta palette, no near-black with a single acid accent, no newspaper-column broadsheet pastiche.
- No grid of identical rounded cards with identical soft shadows. The case list is a table.
- No all-caps tracked eyebrow labels, no numbered "01 / 02 / 03" markers unless the content really is a sequence.
- No spaced em dashes in labels, no middle-dot strings ("A · B · C") for metadata, no arrows appended to buttons or links, no monospace face for small labels.
- No emoji, sparkle or magic-wand icons, no robot imagery, no "AI-powered", "magic", "supercharge", "seamless".
- No fade-and-slide-up entrances on sections, no hover lift on cards, no parallax, no confetti.
- No fake testimonials, fake logos, fake usage numbers, lorem ipsum, or stock photographs.
- No centred hero with three feature cards. There is no marketing page; the first screen is the working screen.
- No tinted near-black (`#0B0B0B`, `#111`) as pure black; text is `ink`.
- No `border-radius` above 6px, no pills, no circles.
- No `box-shadow`, `backdrop-filter`, or `linear-gradient`/`radial-gradient` in app CSS.
- No icon font and no generic icon-library grid. Draw the dozen icons the product needs (below) as inline SVG.

---

## 8. Responsive behaviour

| Breakpoint | Layout |
| --- | --- |
| ≥1200px | Three-column workbench as drawn above |
| 900 to 1199px | Papers rail collapses to a horizontal strip of tabs above the viewer; claims panel stays at the right |
| 600 to 899px | Single column: viewer first, claims table below. Only the Amount owed and the link to the working are sticky at the bottom; the rest of the strip scrolls with the page |
| <600px | Single column, claims table becomes a list of rows (value and check on two lines), source crop below the value. The clock strip shows only "Amount owed" with a button "See how this is worked out" |

- Touch targets are at least 44x44px. Inputs are 16px minimum font size so mobile browsers do not zoom.
- The viewer supports pinch zoom. Photos taken in portrait must not be cropped.
- The dossier screen preview is a single column on narrow screens; printing always uses the A4 layout.
- Test widths: 360, 768, 1024, 1440.

---

## 9. Agent prompt guide

**Quick reference for building any screen**
- Desk `#F3F4F6`, sheets `#FFFFFF`, text `#15171C`, accent ballpoint `#1F3DB8`, failure `#C4281C`, pass `#1E7A4F`, review `#F5D547`.
- Font Mukta for everything, Kalam for corrections only. Radii 2px for fields and chips, 6px for panels.
- Three type registers: `display-amount` (56px) for money, `display` (34px) for a verdict word, `h1`–`h3` for structure, `body` for reading. Body copy never changes size.
- No shadows, gradients, emoji or scroll animations. The case list is a table.
- A paper has a type colour: invoice white, challan `#F2D4CF`, purchase order `#F3E7B0`.

**Prompts that work with this file**
- "Build the claims table exactly as section 4.5, with the red-pen correction from 4.8, using tokens only."
- "Build the case list as the table in 4.10 with its empty state. Do not use cards."
- "Build the dossier print stylesheet from section 5 with `@page` rules and test it by rendering to PDF."
- "Review this template against section 7 and list every violation with file and line."

**Self-review checklist before any UI commit**
1. `python scripts/design_lint.py` passes.
2. `python scripts/check_contrast.py` passes.
3. Screenshots at 360, 768 and 1440px, in English and in Hindi, show no overflow, no clipped Devanagari, and visible focus on every control.
4. Keyboard only: can you add a paper, correct a value, open the dossier and print it?
5. With `prefers-reduced-motion: reduce`, nothing moves.

---

## 10. Icons

Draw these as inline SVG at 16px and 20px, 1.5px stroke, square caps, `currentColor`. Keep them in `packages/munim_web/src/munim_web/templates/components/icons.html`.
`tick`, `strike` (a short wavy line), `bracket-hand` (a square bracket with a small pointing mark), `box` (a dashed rectangle with corner marks), `sheet`, `plus`, `trash`, `copy`, `print`, `zoom-in`, `zoom-out`, `fit`. No other icons in v1.

---

## 11. Content and voice

- Name things by what the user does with them: paper, case, evidence file, check, due date, amount owed. (Code and routes may say "dossier"; the visible word is "evidence file", Hindi "सबूत की फ़ाइल".) Not "documents processed", "pipeline", "inference", "agent".
- Refer to the model once, plainly, where it matters: "Gemma read this paper". Never "AI-powered" and never imply the model is certain.
- Every number has a source: a box on a paper, a rule, or a setting.
- Use one name per concept throughout: "Check this paper" produces a message "Paper checked".
- The full English and Hindi string table is `docs/CONTENT.md`. All UI strings live in `packages/munim_web/src/munim_web/i18n/en.json` and `packages/munim_web/src/munim_web/i18n/hi.json`; there are no hard-coded strings in templates.
- Legal wording: Munim explains and calculates; it does not give legal advice. This sentence appears on the dossier, the rules page and the About page.

---

## 12. Design lint (enforced, not aspirational)

`scripts/design_lint.py` runs in CI and in `make check`. It scans `packages/munim_web/src/munim_web/templates`, `packages/munim_web/src/munim_web/static/css`, `packages/munim_web/src/munim_web/static/js` (except vendored files in `static/js/vendor/`, which are covered by `check_licences.py` and `THIRD_PARTY.md`) and inline SVG, fails if a scan root is missing, and fails on:

1. Any hex colour outside `tokens.css` and the SVG icon files' `currentColor` usage.
2. `box-shadow` (except a focus ring marked with a `/* focus-ring */` comment), `backdrop-filter`, `linear-gradient(`, `radial-gradient(`, `conic-gradient(`.
3. `border-radius` values above 6px, and the value `9999px` or `50%`.
4. `text-transform: uppercase` outside the `.stamp` selector, and any `letter-spacing` above `0.02em`.
5. Any emoji code point or the characters `✨`, `→`, `—` used as a UI separator in strings under `packages/munim_web/src/munim_web/i18n` and templates.
6. Fonts other than the declared families (Mukta, Kalam, the declared fallbacks).
7. Missing `lang` attributes on elements that contain Devanagari.
8. Animation or transition on `opacity` combined with `translate` on scroll-triggered selectors, and any use of `IntersectionObserver` for entrance effects.
9. Strings from the banned-words list: "AI-powered", "magic", "seamless", "supercharge", "unlock", "revolutionary", "lorem".

Each failure prints the file, line and the rule number from section 7.
