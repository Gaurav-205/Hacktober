# HTTP interface

Server-rendered HTML plus a small JSON surface for the viewer and for programmatic use. Everything is local (`127.0.0.1`). All non-GET requests require the CSRF token. Errors: HTML routes show a message page or fragment; JSON routes return RFC 7807-style problem objects `{type, title, status, detail, instance}`. Strings in problems are in English plus a `message_key` for the UI to translate.

## Pages

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Case list (table, empty state) |
| POST | `/cases` | Create case (title, supplier_name, buyer_name) -> 303 to `/cases/{id}` |
| GET | `/cases/{id}` | Workbench |
| POST | `/cases/{id}/settings` | Update case inputs (udyam, agreement, credit_days, acceptance_date, objection_removed_on, interest_base, as_on_date) |
| POST | `/cases/{id}/papers` | Multipart upload: `file`, `kind` (invoice, challan, po). Validates type, size, decodability; stores; returns the papers rail fragment |
| POST | `/papers/{id}/kind` | Change type |
| POST | `/papers/{id}/rotate?deg=90` | Rotate original (stored as metadata; new derived image generated) |
| POST | `/papers/{id}/read` | Start reading; returns the status fragment |
| GET | `/papers/{id}/status` | Status fragment (polled by htmx until `read` or `failed`) |
| GET | `/papers/{id}/image` | Original image (`Cache-Control: no-store`) |
| GET | `/papers/{id}/crop?box=y1,x1,y2,x2` | Cropped region for source cells (`no-store`) |
| GET | `/papers/{id}/claims` | Claims panel fragment |
| POST | `/claims/{id}` | Edit value (form: `value`, `reason?`) -> returns the updated row, re-runs checks |
| POST | `/claims/{id}/accept` | Accept a failing check with typed reason |
| POST | `/claims/{id}/reread` | Trigger a manual repair attempt (at most 2 per field) |
| POST | `/cases/{id}/confirm` | Confirm values; 409 with the list of blocking findings if not allowed |
| GET | `/cases/{id}/clock` | Clock strip fragment (`as_on` optional) |
| GET | `/cases/{id}/working` | The working steps page/fragment |
| POST | `/cases/{id}/payments` | Add a part-payment (date, amount) |
| GET | `/cases/{id}/dossier` | Dossier (screen + print) |
| GET | `/cases/{id}/notice?lang=en|hi` | Draft notice text |
| GET | `/cases/{id}/export.zip` | Stretch: JSON + originals + dossier HTML |
| POST | `/cases/{id}/delete` | Delete case and all files (confirmation required in the UI) |
| GET | `/rules` | Rule list from `rules/*.yaml` and bank-rate table |
| POST | `/rules/bank-rate` | Add or confirm a bank-rate row |
| GET | `/evaluation` | Latest evaluation report |
| GET | `/settings` | Provider, model, language, preflight report |
| POST | `/settings` | Save provider settings; enabling Gemini requires `cloud_consent=on` |
| GET | `/about` | Licence, model, privacy |
| GET | `/healthz` | JSON `{status, version, provider, preflight}`; no document data |

## JSON surface (`/api/v1`)

| Method | Path | Body / query | Response |
| --- | --- | --- | --- |
| GET | `/api/v1/cases/{id}/claims` | none | `{paper_id: [{id, field, value_read, value_current, source, box:[y1,x1,y2,x2]|null, findings:[…]}]}` used by the viewer |
| POST | `/api/v1/verify/gstin` | `{"gstin": "27AAPFU0939F1ZV"}` | `{valid, state_code, pan, errors:[rule_id…]}` |
| POST | `/api/v1/clock` | `{acceptance_date, agreement, credit_days, principal_paise, as_on, rates:[{effective_from, percent}], payments:[…]}` | `{due_date, days_late, interest_paise, total_paise, steps:[…]}` |
| GET | `/api/v1/rules` | none | list of rules with ids, versions, status |

The `verify` and `clock` endpoints are pure and stateless; they exist for the MCP server, tests, and third parties.

## Headers and cookies
- `Content-Security-Policy` as in ARCHITECTURE section 7.
- `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin`, `Permissions-Policy: camera=(self), microphone=(), geolocation=()` (camera allowed only for a stretch "take photo" button).
- Cookies: `munim_csrf` (SameSite=Strict, HttpOnly=false because htmx reads it; value is random per session), `munim_lang` (SameSite=Lax).

## Upload validation
1. Size <= 15 MB (stream-checked, not trusting `Content-Length`).
2. Magic bytes, not the extension: JPEG, PNG, WebP, HEIC (pillow-heif), PDF (`%PDF`).
3. Decode with Pillow/pypdfium2 inside a try block with `Image.MAX_IMAGE_PIXELS = 50_000_000` to block decompression bombs.
4. Strip EXIF GPS and device metadata from the stored derived copy; the original is stored unmodified except for rotation metadata.
5. Store under `data/uploads/<case>/<paper>/<sha256>.<ext>`; names never come from the client.

## Idempotency and concurrency
- `POST /papers/{id}/read` while status is `reading` returns the current status.
- Claim edits use `If-Match` style optimistic version (`claims.rowid` version column or `updated_at`); a stale edit returns 409 and a fragment with the latest value.
