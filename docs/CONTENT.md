# Content deck (English and Hindi)

Rules (from `DESIGN.md` section 11): plain verbs, sentence case, one name per concept, no marketing words, errors say what happened and what to do. All strings live in `packages/munim_web/src/munim_web/i18n/en.json` and `hi.json` with identical key sets (`scripts/check_i18n.py` enforces this and also flags Latin text in `hi.json` except for proper nouns and units).

**Hindi status: machine-drafted, not reviewed by a native speaker.** Terms were chosen for everyday business Hindi as used with invoices ("बिल", "चालान", "बकाया"). Before the demo, have a Hindi-speaking person who handles business papers read every string and the notice, and record the reviewer and date in `docs/AI_CONTRIBUTION.md`. Do not claim the Hindi is verified until that is done.

Glossary used consistently:

| English | Hindi | Note |
| --- | --- | --- |
| paper | कागज़ | a scanned or photographed document |
| case | मामला | one dispute, one buyer |
| tax invoice | टैक्स इनवॉइस | printed term on most papers |
| delivery challan | डिलीवरी चालान | |
| purchase order | खरीद आदेश (पीओ) | |
| evidence file (code name: dossier) | सबूत की फ़ाइल | the visible English word is "evidence file" (see note below) |
| amount owed | बकाया रकम | |
| due date | देय तिथि | |
| interest | ब्याज | |
| passed / doesn't match / check by hand | जाँच में पास / मेल नहीं खाता / हाथ से जाँचें | "पास" reports the check's outcome; "सही" (correct) would claim the value is true |

> English UI uses **"evidence file"** for what the design doc calls the dossier. Route names and code may keep `dossier`; the visible word is "evidence file" (Hindi: "सबूत की फ़ाइल").

## 1. Strings

| Key | English | Hindi (draft) |
| --- | --- | --- |
| app.name | Munim | मुनीम |
| nav.cases | Cases | मामले |
| nav.rules | Rules and sources | नियम और स्रोत |
| nav.evaluation | How well it reads | यह कितना सही पढ़ता है |
| nav.about | About | परिचय |
| nav.settings | Settings | सेटिंग |
| cases.title | Cases | मामले |
| cases.empty | No cases yet. Start a case, then add its papers: a tax invoice, a delivery challan and a purchase order. | अभी कोई मामला नहीं है। एक मामला शुरू करें, फिर उसके कागज़ जोड़ें: टैक्स इनवॉइस, डिलीवरी चालान और खरीद आदेश। |
| cases.new | New case | नया मामला |
| cases.col.case | Case | मामला |
| cases.col.parties | Supplier and buyer | सप्लायर और खरीदार |
| cases.col.papers | Papers | कागज़ |
| cases.col.owed | Amount owed | बकाया रकम |
| cases.col.updated | Updated | अपडेट |
| case.form.title | Case name | मामले का नाम |
| case.form.supplier | Supplier (you) | सप्लायर (आप) |
| case.form.buyer | Buyer | खरीदार |
| case.create | Create case | मामला बनाएँ |
| paper.add | Add a paper | कागज़ जोड़ें |
| paper.drop | Drop a photo or PDF here, or choose a file. | फ़ोटो या पीडीएफ़ यहाँ डालें, या फ़ाइल चुनें। |
| paper.kind | What is this paper? | यह कौन-सा कागज़ है? |
| paper.kind.invoice | Tax invoice | टैक्स इनवॉइस |
| paper.kind.challan | Delivery challan | डिलीवरी चालान |
| paper.kind.po | Purchase order | खरीद आदेश |
| paper.read | Check this paper | इस कागज़ को जाँचें |
| paper.reading | Reading this paper. This can take a minute. | कागज़ पढ़ा जा रहा है। इसमें एक मिनट लग सकता है। |
| paper.read.done | Paper checked | कागज़ जाँचा गया |
| paper.rotate | Rotate | घुमाएँ |
| paper.delete | Delete this paper | यह कागज़ हटाएँ |
| paper.err.type | This file type isn't supported. Use a JPEG, PNG, WebP or HEIC photo, or a PDF. | यह फ़ाइल प्रकार स्वीकार नहीं है। JPEG, PNG, WebP या HEIC फ़ोटो, या पीडीएफ़ इस्तेमाल करें। |
| paper.err.size | This file is larger than 15 MB. Take the photo again at a lower quality, or crop it. | यह फ़ाइल 15 एमबी से बड़ी है। कम क्वालिटी में फ़ोटो दोबारा लें, या उसे क्रॉप करें। |
| paper.err.dark | This photo is too dark to read. Retake it in daylight. | यह फ़ोटो पढ़ने के लिए बहुत अँधेरी है। दिन की रोशनी में दोबारा लें। |
| paper.err.blur | This photo is blurred. Hold the phone still and retake it. | यह फ़ोटो धुँधली है। फ़ोन स्थिर रखकर दोबारा लें। |
| paper.err.read | Munim couldn't read this paper automatically. Enter the values by hand. | मुनीम यह कागज़ अपने-आप नहीं पढ़ सका। मान हाथ से भरें। |
| claims.title | What Gemma read | Gemma ने क्या पढ़ा |
| claims.col.field | Field | विवरण |
| claims.col.value | Value read | पढ़ा गया मान |
| claims.col.check | Check | जाँच |
| claims.col.source | On the paper | कागज़ पर |
| claims.notfound | Not found on the paper | कागज़ पर नहीं मिला |
| claims.edit | Edit | बदलें |
| claims.edited | Edited by you | आपने बदला |
| claims.original | Originally read | पहले यह पढ़ा गया था |
| claims.accept | Accept anyway | फिर भी मानें |
| claims.accept.reason | Why are you accepting this? (for example, "I checked the paper by hand") | आप इसे क्यों मान रहे हैं? (जैसे, "मैंने कागज़ हाथ से देख लिया") |
| check.passed | Passed | जाँच में पास |
| check.failed | Doesn't match | मेल नहीं खाता |
| check.review | Check by hand | हाथ से जाँचें |
| check.skipped | Not enough to check | जाँच के लिए जानकारी कम है |
| redpen.reason.gstin | Re-read from the marked box. The GSTIN checksum now passes. | चिह्नित डिब्बे से दोबारा पढ़ा। GSTIN का चेकसम अब सही है। |
| redpen.reason.lookalike | A look-alike character fixed the checksum. Check it against the paper. | मिलते-जुलते अक्षर से चेकसम ठीक हुआ। कागज़ से मिलाकर देखें। |
| redpen.unchanged | Read again, same value. Check it by hand. | दोबारा पढ़ा, वही मान आया। हाथ से जाँचें। |
| rule.GSTIN-FORMAT | The GSTIN must be 15 characters: 2 digits, 5 letters, 4 digits, 1 letter, then 3 more characters. | GSTIN 15 अक्षर का होना चाहिए: 2 अंक, 5 अक्षर, 4 अंक, 1 अक्षर, फिर 3 और अक्षर। |
| rule.GSTIN-STATE | The first two digits {code} are not a state code. | पहले दो अंक {code} किसी राज्य का कोड नहीं हैं। |
| rule.GSTIN-CHECKSUM | The last character doesn't match the other 14 characters. Check the GSTIN on the paper. | आख़िरी अक्षर बाकी 14 अक्षरों से मेल नहीं खाता। कागज़ पर GSTIN देखें। |
| rule.GSTIN-PAN | The PAN inside the GSTIN ({pan_gstin}) differs from the PAN printed on the paper ({pan_paper}). | GSTIN के अंदर का PAN ({pan_gstin}) कागज़ पर छपे PAN ({pan_paper}) से अलग है। |
| rule.INV-TOTAL | Taxable value plus tax is {computed}, but the invoice total is {printed}. | कर-योग्य मूल्य और टैक्स मिलाकर {computed} होता है, पर बिल का कुल {printed} है। |
| rule.INV-TAXABLE-SUM | The lines add up to {computed}, but the taxable total is {printed}. | लाइनों का जोड़ {computed} है, पर कर-योग्य कुल {printed} है। |
| rule.INV-LINE-AMOUNT | Line {n}: quantity times rate is {computed}, but the amount is {printed}. | लाइन {n}: मात्रा गुणा दर {computed} है, पर रकम {printed} है। |
| rule.INV-TAX-SPLIT | The supplier and buyer are in {same_or_different} states, so the tax should be {expected}. | सप्लायर और खरीदार {same_or_different} राज्यों में हैं, इसलिए टैक्स {expected} होना चाहिए। |
| rule.DATE-AMBIGUOUS | The date {printed} can be read as {a} or {b}. Pick the right one. | तारीख {printed} को {a} या {b} पढ़ा जा सकता है। सही वाली चुनें। |
| rule.X-INVOICE-REF | The challan names invoice {on_challan}, but this invoice is {on_invoice}. | चालान में इनवॉइस {on_challan} लिखा है, पर यह इनवॉइस {on_invoice} है। |
| rule.X-QTY | Line "{item}": the challan says {challan_qty}, the invoice says {invoice_qty}. | "{item}": चालान में {challan_qty}, इनवॉइस में {invoice_qty} है। |
| rule.X-RECEIVER-ACK | No receiver's stamp or signature found. The delivery date may be disputed. | प्राप्तकर्ता की मुहर या दस्तख़त नहीं मिले। डिलीवरी की तारीख़ पर विवाद हो सकता है। |
| clock.delivered | Delivered on | डिलीवरी की तारीख |
| clock.due | Due on | देय तिथि |
| clock.late | Days late | देरी (दिन) |
| clock.interest | Interest to date | आज तक ब्याज |
| clock.owed | Amount owed | बकाया रकम |
| clock.working | How this is worked out | यह कैसे निकाला गया |
| clock.basis.written | Due {days} days after acceptance, as agreed in writing. | लिखित सहमति के अनुसार स्वीकृति के {days} दिन बाद देय। |
| clock.basis.capped | You entered {entered} days. The Act limits agreed credit to 45 days, so 45 is used. | आपने {entered} दिन लिखे। अधिनियम सहमत उधार की सीमा 45 दिन रखता है, इसलिए 45 दिन लिए गए। |
| clock.basis.none | No written agreement, so payment was due {days} days after acceptance. | लिखित सहमति नहीं है, इसलिए स्वीकृति के {days} दिन बाद भुगतान देय था। |
| clock.rate | Interest rate: 3 times the Bank Rate of {bank_rate}% = {rate}% a year, compounded every month. | ब्याज दर: बैंक दर {bank_rate}% की 3 गुना = {rate}% सालाना, हर महीने चक्रवृद्धि। |
| clock.rate.unconfirmed | This Bank Rate hasn't been confirmed by you. Check it against the RBI notification. | इस बैंक दर की आपने पुष्टि नहीं की है। इसे आरबीआई की अधिसूचना से मिलाएँ। |
| elig.title | Who the Act protects | अधिनियम किसे सुरक्षा देता है |
| elig.body | The Act's protection applies to micro and small suppliers. Courts have taken different views on whether the registration must exist on the date the contract was made. The Supreme Court in NBCC (India) Ltd v State of West Bengal (January 2025) held that prior registration is not mandatory for a Section 18 reference, and referred the point to a larger bench. Earlier decisions (Silpi Industries, 2021; Mahakali Foods, 2023) took the opposite view. Check with a lawyer or your industry association before filing. | अधिनियम की सुरक्षा सूक्ष्म और लघु सप्लायरों के लिए है। अदालतों की राय इस पर अलग-अलग रही है कि अनुबंध की तारीख पर पंजीकरण होना ज़रूरी है या नहीं। सुप्रीम कोर्ट ने NBCC (India) Ltd बनाम पश्चिम बंगाल राज्य (जनवरी 2025) में कहा कि धारा 18 के अंतर्गत भेजने के लिए पहले से पंजीकरण अनिवार्य नहीं है, और यह प्रश्न बड़ी पीठ को भेजा। पहले के फ़ैसलों (Silpi Industries, 2021; Mahakali Foods, 2023) में उल्टी राय थी। दावा करने से पहले किसी वकील या अपने उद्योग संघ से पूछें। (हिंदी अनुवाद की समीक्षा बाकी है) |
| confirm.button | Confirm these values | इन मानों की पुष्टि करें |
| confirm.blocked | {n} checks still need you. Fix them or accept them with a reason. | {n} जाँचों पर आपका ध्यान चाहिए। उन्हें ठीक करें या कारण लिखकर मानें। |
| stamp.word | CHECKED | जाँचा गया |
| evidence.open | Open evidence file | सबूत की फ़ाइल खोलें |
| evidence.print | Print | प्रिंट करें |
| evidence.title | Evidence file | सबूत की फ़ाइल |
| evidence.draft | Draft for review. Not legal advice. | समीक्षा के लिए मसौदा। यह कानूनी सलाह नहीं है। |
| notice.copy | Copy notice text | नोटिस का पाठ कॉपी करें |
| toast.copied | Copied | कॉपी हो गया |
| toast.saved | Saved | सहेजा गया |
| delete.case | Delete case | मामला हटाएँ |
| delete.confirm | This deletes the case, its photos and everything read from them. It can't be undone. | इससे मामला, उसकी फ़ोटो और उनसे पढ़ा सब कुछ हट जाएगा। इसे वापस नहीं लाया जा सकता। |
| settings.provider | Reader | पढ़ने का तरीका |
| settings.provider.ollama | On this computer (Gemma 4 through Ollama) | इसी कंप्यूटर पर (Ollama से Gemma 4) |
| settings.provider.gemini | Hosted Gemma 4 (Gemini API) | होस्टेड Gemma 4 (Gemini API) |
| settings.provider.replay | Recorded responses (demo and tests) | रिकॉर्ड किए गए जवाब (डेमो और परीक्षण) |
| settings.consent | I understand the photos of my papers will be sent to Google's servers to be read. | मैं समझता/समझती हूँ कि मेरे कागज़ों की फ़ोटो पढ़ने के लिए Google के सर्वर पर भेजी जाएँगी। |
| badge.hosted | Reading with the hosted model | होस्टेड मॉडल से पढ़ा जा रहा है |
| badge.replay | Recorded responses | रिकॉर्ड किए गए जवाब |
| fix.ollama.down | Munim can't reach Ollama at {url}. Start it, then try again. | मुनीम {url} पर Ollama तक नहीं पहुँच पा रहा। उसे चालू करें, फिर दोबारा कोशिश करें। |
| fix.ollama.model | The model {model} isn't downloaded. Run: ollama pull {model} | मॉडल {model} डाउनलोड नहीं है। चलाएँ: ollama pull {model} |
| error.generic | Something went wrong. Nothing was lost. Reference: {ref} | कुछ गड़बड़ हुई। कुछ भी खोया नहीं है। संदर्भ: {ref} |
| about.privacy | Your papers stay on this computer unless you choose the hosted reader. Munim sends nothing anywhere else. | आपके कागज़ इसी कंप्यूटर पर रहते हैं, जब तक आप होस्टेड रीडर न चुनें। मुनीम कहीं और कुछ नहीं भेजता। |
| legal.notice | Munim reads and calculates. It does not give legal advice and does not file anything. Check with a lawyer, a chartered accountant or your industry association before relying on a figure or sending a notice. | मुनीम पढ़ता और हिसाब लगाता है। यह कानूनी सलाह नहीं देता और कुछ दाखिल नहीं करता। किसी रकम पर भरोसा करने या नोटिस भेजने से पहले वकील, चार्टर्ड अकाउंटेंट या अपने उद्योग संघ से पूछें। |

Notes
- The hand-written correction text (Kalam) and stamp text must render in both languages; for Hindi the stamp shows "जाँचा गया" and the "capitals only in stamp" lint rule allows it (no case in Devanagari).
- Plural forms: none needed for Hindi in these strings; `{n}` placeholders are numeric.
- Gender in "समझता/समझती": keep both forms; do not guess the user's gender.
- Do not translate proper nouns: GSTIN, PAN, IFSC, Udyam, MSMED, Gemma, Ollama.

## 2. Notice templates

Rendered by Jinja2 from confirmed values only. `[rule: X]` comments stay in the template source as HTML/Jinja comments, not in output.

### English (`notice.en.md.j2`)

```
Draft for review. Not legal advice.

Date: {{ today }}

To: {{ buyer_name }}{% if buyer_address %}, {{ buyer_address }}{% endif %}
From: {{ supplier_name }}{% if supplier_address %}, {{ supplier_address }}{% endif %}

Subject: Payment due for invoice {{ invoice_number }} dated {{ invoice_date }}

1. We supplied goods to you{% if po_number %} under purchase order {{ po_number }}{% endif %}.
   The goods were delivered on {{ delivery_date }} under challan {{ challan_number }},
   and invoiced under invoice {{ invoice_number }} for {{ invoice_total }}.   {# rule: CLOCK-ACCEPT #}

2. {{ due_basis_sentence }} Payment therefore fell due on {{ due_date }}.      {# rule: CLOCK-DUE #}

3. As on {{ as_on }}, {{ days_late }} days have passed since the due date. Under sections 15 and 16
   of the Micro, Small and Medium Enterprises Development Act, 2006, interest is payable at three
   times the Bank Rate notified by the Reserve Bank of India, compounded with monthly rests, from the
   day after the due date. At the Bank Rate of {{ bank_rate }}%, that is {{ rate }}% a year.
   Interest to {{ as_on }} is {{ interest }}, making {{ total_owed }} due. The working is attached.  {# rule: CLOCK-INTEREST #}

4. Please pay {{ total_owed }}, with interest accruing until payment, within {{ notice_days }} days of this notice.
   If we do not receive payment, we reserve all our rights, including referring the dispute to the
   Micro and Small Enterprises Facilitation Council under section 18 of the Act.   {# rule: SEC-18-REFERENCE #}

{{ supplier_name }}
Udyam registration: {{ udyam_number }} ({{ udyam_date }})
Signature: ____________________
```

### Hindi (`notice.hi.md.j2`, draft; same structure)

```
समीक्षा के लिए मसौदा। यह कानूनी सलाह नहीं है।

दिनांक: {{ today }}

प्रति: {{ buyer_name }}{% if buyer_address %}, {{ buyer_address }}{% endif %}
प्रेषक: {{ supplier_name }}{% if supplier_address %}, {{ supplier_address }}{% endif %}

विषय: इनवॉइस {{ invoice_number }} दिनांक {{ invoice_date }} का भुगतान बकाया

1. हमने आपको माल की आपूर्ति की{% if po_number %} (खरीद आदेश {{ po_number }} के अंतर्गत){% endif %}।
   माल चालान {{ challan_number }} के अंतर्गत {{ delivery_date }} को पहुँचाया गया और
   इनवॉइस {{ invoice_number }} द्वारा {{ invoice_total }} का बिल बनाया गया।

2. {{ due_basis_sentence }} इसलिए भुगतान {{ due_date }} को देय हुआ।

3. {{ as_on }} तक देय तिथि के बाद {{ days_late }} दिन बीत चुके हैं। सूक्ष्म, लघु और मध्यम उद्यम विकास
   अधिनियम, 2006 की धाराओं 15 और 16 के अनुसार, भारतीय रिज़र्व बैंक द्वारा अधिसूचित बैंक दर की तीन गुना दर से,
   मासिक चक्रवृद्धि के साथ, देय तिथि के अगले दिन से ब्याज देय है। {{ bank_rate }}% की बैंक दर पर यह {{ rate }}% सालाना है।
   {{ as_on }} तक ब्याज {{ interest }} है, यानी कुल {{ total_owed }} देय है। हिसाब संलग्न है।

4. कृपया इस नोटिस के {{ notice_days }} दिनों के भीतर {{ total_owed }} का भुगतान करें; भुगतान तक ब्याज चलता रहेगा।
   भुगतान न मिलने पर हम अपने सभी अधिकार सुरक्षित रखते हैं, जिनमें अधिनियम की धारा 18 के अंतर्गत
   सूक्ष्म और लघु उद्यम सुविधा परिषद को विवाद भेजना शामिल है।

{{ supplier_name }}
उद्यम पंजीकरण: {{ udyam_number }} ({{ udyam_date }})
हस्ताक्षर: ____________________
```

`due_basis_sentence` comes from the `clock.basis.*` strings, never from free text.

## 3. Demo data (synthetic)

| Item | Value |
| --- | --- |
| Supplier | Sample Fabricators Pvt Ltd (Ghaziabad; GSTIN constructed with state 09) |
| Buyer | Demo Textiles Ltd (Pune; GSTIN constructed with state 27) |
| PO | PO-2026-0117, dated 2026-03-02 (printed as `02 Mar 2026`, so the date is not ambiguous) |
| Challan | CH-0412, dated 2026-03-20 (printed `20/03/2026`), receiver stamp present, no separate received date, so acceptance is 20 Mar 2026 |
| Invoice | SF/2025-26/0412, dated 2026-03-21, taxable ₹4,23,729.00, IGST 18% ₹76,271.22 (inter-state), round-off −₹0.22, total ₹5,00,000.00 (checked: 4,23,729.00 + 76,271.22 − 0.22 = 5,00,000.00) |
| Terms | Written agreement, 30 credit days -> due 2026-04-19; interest from 2026-04-20 |
| Misread in first read | Buyer GSTIN: the check character (position 15) is read as a different character outside the look-alike map, so `GSTIN-CHECKSUM` fails, no look-alike candidate passes and the model re-read returns the printed value. The misread exists only in the recorded response; the paper prints the correct GSTIN, so a live read may not show it |

(The ₹5,00,000 total ties to the golden interest vector family used in the tests. On the seeded Bank Rate table the demo shows ₹40,976.71 interest and ₹5,40,976.71 owed at 16.5%; at the golden vector's explicit 17.25% it would be ₹42,903.70 and ₹5,42,903.70. The generator constructs the GSTINs with the checksum algorithm; they are synthetic.)
