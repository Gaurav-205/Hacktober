# Demo script (3 minutes live, 2 minutes video)

Principle: show the working product first, explain second. Say honestly which provider is active.

## Setup (before going on stage)
- `make run` already started; browser at 1440x900, zoom 110%, language English; Hindi toggle tested.
- Ollama running with `gemma4:e4b` pulled **and warmed** (one dummy read 5 minutes before). Provider badge visible.
- Demo case pre-created *except* the three papers. Fixtures from `eval/fixtures/demo/` in a folder on the desktop: invoice (with the misread GSTIN variant), challan, PO.
- Backup: a second instance with recorded responses and its own data folder (`MUNIM_PROVIDER=replay MUNIM_PORT=8766 MUNIM_DATA_DIR=./data-replay make run`) in a second tab, same fixtures. If the live model stalls past 20 seconds, switch tabs without comment beyond "Same papers, recorded responses, and the badge says so."
- Printed copy of one finished evidence file as a physical prop.
- Network off or on: it must not matter (the app is local); say so if asked.

## Beats

| Time | Say | Do | Must be visible |
| --- | --- | --- | --- |
| 0:00 | "A supplier delivered goods in March. The buyer still hasn't paid. These are the three papers he has: all photos on a phone." | Open the case list; click the case "Sample Fabricators v Demo Textiles" | Empty workbench, three coloured sheet tabs ready |
| 0:15 | "I drop the invoice." | Drag the invoice file into the dropzone; choose "Tax invoice"; press "Check this paper" | Progress message; model badge "On this computer" |
| 0:35 | "Gemma 4 reads it on this laptop. No internet." | Boxes appear on the photo; claims table fills | Boxes aligned to values; table rows |
| 0:50 | "The buyer's GSTIN has a wrong last character. The checksum says so." | Point at the red row | Row in red-wash, message "The last character doesn't match..." (in the recorded responses; a live read may get it right first time, so say what the screen shows) |
| 1:00 | "Munim re-reads just that box." | Wait for the repair | Strike line draws, ballpoint handwriting appears, row turns Passed |
| 1:15 | "It never fixes silently. The old value stays. I still confirm." | Hover the struck value | Original visible |
| 1:25 | "Challan and PO." | Add both (already read quickly on replay if needed) | Cross-paper checks pass; one warning about stamp optional |
| 1:45 | "I confirm." | Press "Confirm these values" | Stamp lands on the sheet |
| 1:55 | "Now the law. Agreed 30 days, so due 19 April. 177 days late as on 13 October." | Scroll to clock strip; open "How this is worked out" | Due date, days late, interest, amount owed; working steps; Bank Rate rows marked "not confirmed" until confirmed |
| 2:20 | "That's the amount: ₹5,40,976.71, of which ₹40,976.71 is interest. Every step is shown." | Confirm the Bank Rate row used (5.50% from 5 Dec 2025) | The "not confirmed" notice disappears |
| 2:30 | "And the file he can print." | Open evidence file; show page 1; click Hindi notice | Stamp; draft notice Hindi |
| 2:45 | "It's open source, Apache 2.0, Gemma 4 locally. On [n] papers it was wrong-and-passed [y]% of the time, published on this page." | Open Evaluation page | The metric and a failure example |
| 3:00 | Stop. | | |

The reference figures above come from the seeded Bank Rate table (`DOMAIN_RULES.md` 5.4): principal ₹5,00,000.00 invoice total, due 19 Apr 2026, interest from 20 Apr, as-on 13 Oct 2026 set explicitly in the case, every period at 16.5% (3 x 5.50%, the row effective 5 Dec 2025, not yet confirmed against an RBI notification): 177 days late, interest ₹40,976.71, total ₹5,40,976.71. The algorithm's golden vector for the same case at an explicit 17.25% is ₹42,903.70 (`tests/golden/demo_clock.json`). If the Bank Rate table is edited, the numbers change; say only what the screen shows.

## If something goes wrong
| Failure | Response |
| --- | --- |
| Model slow | Switch to the replay tab; say so |
| Repair does not correct | Say: "It couldn't fix this one, and it says so. I type the value from the paper." Edit; show the struck original. This demonstrates the honesty rule |
| Browser print dialog issue | Show the pre-printed copy |
| Judges ask for a real paper | Offer a photo of a printed synthetic one; do not process a real third-party document in public |

## Video notes (2 minutes)
- Screen capture at 1440x900, 30 fps, no music, voice-over in plain English, captions in English; a Hindi caption for the notice moment.
- Show the provider badge at least once; show the Evaluation page for 5 seconds.
- Do not show any real name or GSTIN.
