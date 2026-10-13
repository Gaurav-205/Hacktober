# Munim: 60-second cinematic demo prompt pack

## Creative direction

**Title:** The work is done. The payment is waiting.

**Length:** Exactly 60 seconds. Nine shots. A fictional small supplier moves from scattered papers to a checked, printable evidence file. The tangible outcome is a clearer record for following up on delayed payment.

**Format:** 16:9, 3840 x 2160 delivery if available, 24 fps timeline, full-frame picture without baked-in letterbox bars. Use 1920 x 1080 if the footage is recorded at that resolution. Keep important faces, papers and screen details inside the central 80% of the frame.

**Mood:** A grounded Indian workshop drama with the precision of a product demonstration. Cinematic lighting, restrained acting, ordinary objects, tactile paper, observable human actions. The emotional arc is waiting, attention, clarity, agency.

Generate the physical-world shots individually. Capture the actual Munim interface for product actions. Composite that capture into the laptop screen where needed. Add all titles, captions and exact numbers in the editor.

This is a scripted illustration, not a customer testimonial or a measured impact report. On the first workshop shot, add a small, readable caption: “Illustrative scenario”. For replay footage, keep the actual “Recorded responses” badge visible and add “Demo uses synthetic papers and recorded responses” during the first full-screen app shot.

## Assets to prepare

- One supplier reference portrait, one workshop reference frame and one desk reference frame. Reuse them throughout if the generation tool supports visual references.
- The same unbranded dark laptop, black phone, steel desk, white invoice, faded pink challan, pale yellow purchase order and blue ballpoint pen in every physical scene.
- Printed synthetic documents from `eval/fixtures/demo/`. Use these as physical props and upload these exact files for replay. Newly generated document pictures will not match the replay fixture hashes.
- A fresh screen recording of the real upload, red-pen correction, confirmation, payment-clock working and evidence-file flow. Capture the provider label and any unconfirmed-rate message faithfully.
- The existing screenshots are layout references: `docs/screens/workbench-1440-en.png`, `docs/screens/workbench-1440-hi.png` and `docs/screens/evidence-1440-en.png`. A screenshot supplies layout, not the live correction animation.
- A printed evidence file from the same synthetic case, with its actual draft label and assumptions retained.

Do not change documents, timestamps, providers or rates merely to make the footage look more convincing. Compress waiting time with straight cuts; retain the sequence of user actions. The video demonstrates a workflow rather than a processing-time benchmark.

## Master visual prompt

Paste this before each physical-world shot prompt:

> Create a photorealistic live-action shot for a cinematic short about Munim, a tool used by a small Indian supplier to assemble an evidence file about a delayed business payment. Set the scene in a credible small metal-fabrication workshop in an Indian industrial neighbourhood. Show a functional, cared-for workplace: stacked metal components, modest machinery, a scuffed steel desk, a ceiling fan and daylight from a side window. The supplier is a fictional Indian man in his early forties with short black hair lightly grey at the temples, a neatly trimmed moustache, medium-brown skin and a faded slate-blue cotton work shirt with sleeves rolled to the forearms. He has dignity and professional competence. His concern is quiet and practical. Reuse his exact face, clothing, desk, laptop and document props from the supplied references. Use natural skin texture, physically plausible lighting, restrained film grain, soft highlight roll-off and neutral colour rendition. Warm window highlights and slightly cool shadows may occur naturally; avoid an exaggerated orange-and-teal grade. Use deliberate camera movement, believable weight and inertia, realistic hands and clear object permanence. Capture 16:9 at 24 fps with the framing and lens specified below. No generated narration, speech, subtitles, logos, interface text or readable identifiers. Leave document microtext unobtrusive. Preserve a clean, flat laptop display surface when screen replacement is requested.

### Shared exclusion prompt

If the tool offers a negative-prompt field, use this; otherwise append it to the prompt:

> Cartoon, anime, illustration, game-engine look, glossy CGI, plastic skin, beauty retouching, uncanny faces, caricatures of Indian life, staged destitution, exaggerated distress, cheering, holograms, floating data, glowing circuitry, robot imagery, science-fiction interfaces, neon, artificial lens flares, excessive bloom, extreme shallow focus that obscures the product, jitter, whip pans, warped desks, bending laptops, duplicated papers, changing clothing, changing faces, extra fingers, fused hands, impossible grips, unreadable generated app interfaces, counterfeit bank messages, real business logos, real customer names, real tax identifiers, invented awards, invented accuracy percentages, cash transfers, courtroom victories, payment-success screens.

## Shot 1 — The work is done

**Timeline:** 00:00–00:06. Generate a 6-second clip, ideally with extra edit handles if supported.

**Paste after the master prompt:**

> A 35 mm eye-level establishing shot inside the workshop. Finished metal brackets are stacked neatly on the workbench in the foreground. Two workers are visible softly in the distant background, each safely inspecting stationary components; no welding or moving machinery. The supplier stands beside the finished stack and then glances toward the office desk a few steps away. Start with the components in focus, then make a gentle focus transition to his face. The camera makes a slow 30-centimetre lateral slide to reveal the desk without dramatic parallax. Diffused late-afternoon window light gives the metal a soft sheen and illuminates one side of his face. His expression conveys pride in the completed work, followed by restrained concern. End with his gaze directed toward the desk on frame right. No visible writing, no posed smile, no artificial slow motion. Ambient sound only: soft workshop room tone and a distant fan.

**Voice-over:** “The work is done. The goods are delivered. But payment is still waiting.”

**Editor:** Add “Illustrative scenario” unobtrusively. At 00:02, add “The work is done.” in sentence case. Straight cut to the desk; carry the room tone across the cut.

## Shot 2 — The paper trail

**Timeline:** 00:06–00:12.

**Prompt:**

> An 85 mm close-up at a shallow downward angle over the same steel desk. The white invoice, faded pink delivery challan and pale yellow purchase order overlap naturally, with creased corners and ordinary staple holes. A blue pen lies at the upper edge of the papers. The supplier places the black phone face-up beside them using his right hand, then slides the white sheet gently away from the other two so all three can be distinguished. His hand is work-worn but clean, with realistic joints and movement. The phone shows an out-of-focus gallery-like grid of paper photographs; no messaging app, notification or bank screen. The camera makes a slow 10-centimetre push toward the papers. Maintain enough depth of field to read the objects as invoice, delivery proof and order, without exposing readable identifiers. Window light falls from frame left; soft paper rustle and one muted phone-on-desk contact sound. End on the three papers in an orderly triangle.

**Voice-over:** “For a small supplier, chasing it starts with three scattered papers.”

**Editor:** Add labels beside the physical sheets: “Tax invoice”, “Delivery challan”, “Purchase order”. Labels belong to the video, not the generated documents. Keep each visible for several seconds.

## Shot 3 — Meet Munim

**Timeline:** 00:12–00:18.

**Prompt:**

> A 50 mm over-the-shoulder shot of the same supplier seated at the same desk. His left shoulder occupies the lower-left foreground. The unbranded dark laptop is open at a physically plausible angle, facing the camera closely enough to see its full display rectangle. The three papers remain to the right of the laptop, the phone remains farther right and the blue pen stays above them. The supplier rests his right hand beside the trackpad and leans forward slightly. Move the camera slowly forward by 15 centimetres while keeping the screen corners unobstructed and its geometry stable. The display is a plain light-grey surface prepared for compositing; moderate screen brightness, no strong reflection, no changing graphics. Focus favours the laptop and hands while retaining his profile. Subtle concentration, natural breathing, no dialogue. End with the laptop display nearly filling the central half of the composition.

**Screen insert:** Track a real Munim workbench recording onto the display. Preserve the actual three-column layout, white panels, paper rail, document viewer, claims table, restrained blue accents and small rectangular controls. Retain “Recorded responses” if active.

**Voice-over:** “Meet Munim. Bring those papers into one case.”

**Editor:** Add “Munim” as a modest lower-third. Finish with a straight cut to the clean screen recording for shot 4; do not morph the physical screen into an invented interface.

## Shot 4 — Read the evidence

**Timeline:** 00:18–00:25. Use actual screen capture.

**Capture brief:**

> Record the real Munim workbench with the synthetic demo case. Start before its invoice is read. Show the invoice upload, paper-type selection and “Check this paper” action. Cut past waiting time to the returned fields, keeping the invoice photo and the claims table visible together. Show one selected claim and its actual source box on the photo. Use short cuts to establish that the challan and purchase order are also present and read, without suggesting one upload creates all three. Keep the same case throughout. Preserve the provider badge and the actual status language. No simulated code typing, generated field values, replacement status labels or fabricated speed counters. Hold the returned source-box view for at least two seconds.

**Voice-over:** “Gemma reads the fields. Code checks the numbers, dates, and whether the papers agree.”

**Editor:** Add “Demo uses synthetic papers and recorded responses” for the full seven seconds when using replay. A gentle crop enlargement is acceptable, provided the viewer still sees the photo-to-field relationship. Add an “Edited for length” label if processing waits are cut.

## Shot 5 — The red-pen moment

**Timeline:** 00:25–00:34. Use actual screen capture. This is the centrepiece.

**Capture brief:**

> Capture the existing recorded-response demo’s buyer-GSTIN misread and repair. Start on the actual “Doesn't match” finding, with its source crop visible. Hold for two seconds so the error can be understood. Then show the app's real re-read and correction state: the old read remains visible under a red strike, the new value appears in ballpoint-blue handwriting, and the relevant check displays “Passed”. Retain the reason for the correction and the relationship to the marked box on the original invoice. End with the old and new values simultaneously visible. Do not substitute a different tax identifier or construct fake text. Use a deliberate screen crop large enough to read on a presentation display. Keep a clear replay disclosure within the shot when the provider badge is outside the crop. Do not stretch the animation into a theatrical scribble or add a floating physical pen.

**Voice-over:** “A misread character? Munim flags it, re-reads the marked box, and keeps the original visible.”

**Editor:** Use a restrained red-pen scratch sound and a soft confirmation click, synced to visible changes. Hold the final comparison for two seconds. “Passed” stays the product's word; add no “Verified” badge. This is the recorded example, not a claim that every error can be repaired.

## Shot 6 — The person confirms; the clock becomes visible

**Timeline:** 00:34–00:41. Use actual screen capture.

**Capture brief:**

> Begin with all blocking findings resolved in the same synthetic case and the real “Confirm these values” action visible. Show the user's confirmation before the checked evidence-file state. Cut to the payment-clock strip, then briefly open the real calculation working. Prioritise the due date, days late, interest and total amount in a legible composition. Display the actual as-on date and preserve any unconfirmed Bank Rate notice. Show figures as ordinary static values, not a rising winnings counter. No automated eligibility approval, no instant payment, no prediction about recovery. End on a readable view of the working or its source inputs.

**Voice-over:** “You confirm the values. Munim calculates the due date and interest, with the working shown.”

**Editor:** Use the numbers recorded from the app. For the existing seeded example, the reference is due 19 Apr 2026, 177 days late as on 13 Oct 2026, interest ₹40,976.71 and amount ₹5,40,976.71. These are synthetic example calculations using the project's seeded, unconfirmed rate assumptions. If used in a cropped graphic, pair them with “Synthetic example · rate requires confirmation”. Do not narrate them as a current legally established debt. If settings change, use the new screen output consistently.

## Shot 7 — From screen to evidence file

**Timeline:** 00:41–00:49. First four seconds actual screen capture; last four seconds physical-world clip.

**Screen-capture brief, 00:41–00:45:**

> Open the real evidence file. Show the summary and actual CHECKED stamp after user confirmation. Make a clean cut to the draft notice and a Hindi view from the same case. Preserve “Draft for review. Not legal advice.” and relevant assumptions. Show genuine rendered Hindi text; use no generated lettering. This is a preview of printable output, not an online filing or sent notice.

**Physical-shot prompt, 00:45–00:49:**

> A 65 mm close-up at desk height in the same workshop office. The supplier uses both hands to align a small stack of white A4 evidence pages already printed and resting on the steel desk. He taps the bottom edges lightly once, then places the stack beside the original white, pink and yellow papers. The pages have credible dense printed rows and a modest blue rectangular stamp area near the top; use the supplied genuine print reference if available. Keep microtext below legibility unless a real print is filmed or composited. The camera makes a subtle 10-centimetre side slide. Preserve the established left-side window lighting and prop positions. Paper bends naturally; hands remain anatomically correct. End with the evidence stack and originals side by side. No printer-output mechanism, no dramatic rubber-stamp impact, no cheque, no cash.

**Voice-over:** “Then print the evidence file, with a draft notice in English and Hindi.”

**Editor:** Match the visible evidence-file page on screen to the physical stack. Add “Draft for review” over the print shot if the printed draft label is not legible. Avoid a claim that the Hindi draft has received human legal review.

## Shot 8 — Ready to follow up

**Timeline:** 00:49–00:56.

**Prompt:**

> A 50 mm medium eye-level shot in the same workshop office. The same supplier places the evidence stack in a simple transparent document folder and holds it at his side. He rises from his chair with unhurried, physically plausible movement. Begin with slight tension in his shoulders; as he stands, his shoulders ease and he takes one calm breath. His expression becomes focused and prepared, with only the smallest natural smile. The workshop and finished components remain visible behind him; a coworker continues inspecting parts in soft focus. The camera holds steady, then makes a gentle five-centimetre push during the last two seconds. The late-afternoon light remains consistent with the opening scene. End with the supplier looking toward his workspace rather than directly selling to the camera. Realistic cloth movement, subtle expression, ordinary room tone. No bank alert, buyer handshake, cheque, celebration, courtroom, testimony or implied recovered payment.

**Voice-over:** “So the supplier can follow up with a clearer record, and every number's source.”

**Editor:** Add “A clearer record. A practical next step.” Low-key confidence is the resolution. The file is prepared; the payment outcome remains open.

## Shot 9 — Munim end frame

**Timeline:** 00:56–01:00.

**Background prompt:**

> A restrained overhead 50 mm still-life shot of the same steel desk. Arrange the white evidence-file stack on the left third, with the faded pink challan and pale yellow purchase order visible underneath. The blue pen lies horizontally near the bottom-left. The right half is uncluttered cool light-grey desk surface, reserved for editor-added titles. Soft side-window light, natural paper fibres and minor desk wear. The camera is locked off for four seconds. No moving props, generated lettering, logos, interface graphics, ornamental decorations or artificial glow. If a supplied genuine print reference is used, preserve its draft label and modest blue stamp. Natural quiet room tone.

**Editor-added title, visible for all four seconds:**

> Munim
>
> Turn scattered papers into a clearer payment claim.
>
> Open source. Local-first.

**Voice-over:** “Munim. Your papers. A clearer claim.”

Add the repository address as a small, readable secondary line only if it fits: `github.com/Gaurav-205/Hacktober`. Make it an actual editor-added text layer. Add “Illustrative scenario · synthetic demo” as a small footer. Keep the end frame still for the full four seconds.

## Complete voice-over

> The work is done. The goods are delivered. But payment is still waiting.
>
> For a small supplier, chasing it starts with three scattered papers.
>
> Meet Munim. Bring those papers into one case.
>
> Gemma reads the fields. Code checks the numbers, dates, and whether the papers agree.
>
> A misread character? Munim flags it, re-reads the marked box, and keeps the original visible.
>
> You confirm the values. Munim calculates the due date and interest, with the working shown.
>
> Then print the evidence file, with a draft notice in English and Hindi.
>
> So the supplier can follow up with a clearer record, and every number's source.
>
> Munim. Your papers. A clearer claim.

### Voice-generation direction

> Read this as a thoughtful Indian English narrator explaining a real tool to another person. Natural Indian English pronunciation, warm mid-register voice, precise articulation, measured delivery, no announcer flourish and no exaggerated accent. Use short pauses after “waiting”, “three scattered papers”, and “You confirm the values”. Emphasise “Code checks”, “original visible”, and “working shown” gently. Keep the emotional movement from concern to practical confidence. Treat Munim as “moo-neem”; confirm the pronunciation with the team before the final recording. No laughter, whispered drama, sales pitch or artificial excitement. Record dry studio speech with no music underneath. Fit each sentence to its allotted shot; leave air at the beginning and end of the film.

The script is approximately 120 words. Record to the shot timings rather than relying on an exact automatic speech rate. During the four-second final shot, leave a brief pause between “Munim” and “Your papers”.

## Sound and edit direction

- Start with real workshop room tone, a distant fan, paper contact and subtle desk sounds. Keep continuity across the cuts.
- A quiet instrumental bed can begin around 00:12: sparse felt piano, soft sustained strings and a restrained low pulse. No vocals, heroic drums, risers or orchestral climax. Use music you have permission to use. A voice-and-room-tone version is also suitable.
- If generating music, prompt: “A 60-second understated instrumental cue for an observational short in a small Indian workshop. Sparse felt piano, warm low strings, very gentle pulse near 72 BPM, no vocals. Begin spacious and unresolved. Gradually introduce a small sense of order between 25 and 45 seconds. End with quiet resolve, not triumph. Leave space for narration and tactile paper sounds. No identifiable melody borrowed from an existing song.”
- Keep narration clearly above music; reduce the music during the red-pen moment so the viewer can read. Aim for a comfortable web-video mix around -16 LUFS integrated with peaks below -1 dBTP, then audition on laptop speakers.
- Use straight cuts and one physical-to-screen match cut. Avoid aggressive transitions, speed ramps, repeated whooshes and a montage so fast that nobody can see the app.
- Render screen footage at its captured resolution or record it again at a larger size. Prioritise readable text over a nominal 4K export. Use moderate crop enlargement, not heavy blur or interpolated detail.
- Keep the app's neutral paper-like colours, ballpoint blue, red correction and restrained green Passed marks. Add captions with a plain readable sans font, preferably Mukta to match the product. Use sentence case. The application's CHECKED stamp is the intentional uppercase exception.
- Produce the narration captions as a separate subtitle track as well as a version burned into the video if needed. Keep captions clear of the correction row, provider label and clock strip.
- For generated clips with embedded sound, remove generated dialogue or unexplained device sounds and rebuild the sound bed in the editor.

## Practical generation sequence

1. Generate or select one convincing reference frame for the supplier at the desk. Lock the face, shirt, lighting and props before generating the remaining clips.
2. Generate shots 1, 2, 3, the physical half of 7, 8 and 9 separately. Reuse references and any supported seed or continuity controls. A supported first-frame image can help lock the scene; a seed alone does not ensure continuity.
3. Use one main physical action per clip. If hands or papers deform, simplify the action to an already-held folder or a stationary desk composition.
4. Record the real app actions for shots 3–7 using synthetic fixtures. Do not generate a facsimile of the interface. Keep replay disclosure readable.
5. Track the genuine interface into shot 3. Use full-screen recordings for the central demo so judges can read the actual feature.
6. Assemble the 60-second timeline, record the voice-over, add titles and captions, and mix the tactile sound effects.
7. Review the exact final cut at normal playback speed on a laptop screen. Check that old and new values, the confirmation action, example labels and draft status can be understood without pausing.

## Project grounding

Product flow and red-pen sequence: `docs/PRD.md` section 6 and `docs/DEMO_SCRIPT.md`. Model/code boundary and replay disclosure: `docs/AI_SPEC.md` sections 2 and 5.3. UI treatment: `DESIGN.md`. Seeded sample clock figures and assumptions: `docs/DOMAIN_RULES.md` sections 5.3–5.4. Current delivery status: `README.md` and `docs/PROGRESS.md`.

No live-model accuracy report exists at preparation time (`eval/reports/latest.json` is absent). The film therefore quotes no model accuracy, processing-time result, recovered-payment figure or customer impact statistic. It also makes no event-day-build claim. “Local-first” describes the product's intended architecture; any explicit “papers stay on this computer” statement must accompany actual local-provider footage, because the hosted provider sends photos off the machine with consent.
