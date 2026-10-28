# Listing Generator

Turn photos of one clothing item into ready-to-post drafts for eBay, Poshmark, Depop, Mercari, Whatnot, and Facebook Marketplace.

You upload the front, back, tag, and flaw photos. A vision model reads what it can. Anything it is not sure about stays blank, including every measurement. You correct the form, then copy a title, description, category, and fee breakdown into the marketplace yourself.

Nothing in this app posts a listing.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a free Gemini key at [Google AI Studio](https://aistudio.google.com/apikey). No credit card. Do not link a billing account if you want to stay on the free tier.

```bash
export GEMINI_API_KEY=your-key
streamlit run app.py
```

The command line does the same work:

```bash
python -m listing_generator analyze front.jpg back.jpg tag.jpg flaw.jpg --output review.json
python -m listing_generator generate review.json --format json --output listing.json
```

`generate --format json` prints the v1 export. `text` prints a readable draft. `csv` is a spreadsheet of the same document.

Run without a key by pointing at the offline sample provider. It does not look at the pixels:

```bash
export VISION_PROVIDER=mock
streamlit run app.py
```

Tests do not need a key:

```bash
pytest
```

## Free tier

The default model is `gemini-2.5-flash` on the Gemini Developer API.

Checked against [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) on 28 October 2026:

- Input and output for Gemini 2.5 Flash are **free of charge** on the free tier, and image input is part of that input price.
- Do not select an image-generation model. This app sends photos and asks for JSON.
- Free-tier prompts for Gemini 2.5 Flash may be used to improve Google products. The paid tier is not used that way.
- Quotas are requests per minute, input tokens per minute, and requests per day, per project. Daily quotas reset at midnight Pacific. Google says the published limits are not a guarantee. AI Studio shows the caps on your project. In 2026, Flash models are commonly described at about 5–15 requests per minute, with a daily cap that has moved between the tens and about 1,500. Use the console number, not this paragraph.
- One **Read photos** click is one request. Drafting the six listings does not call the model unless `LISTING_LLM_POLISH=1`.
- A quota error stops the read. The form is not filled with guesses.

Override the model with `VISION_MODEL` if AI Studio shows a different free Flash id.

Set `VISION_PROVIDER=openai` to use an OpenAI-compatible chat endpoint (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`). That path is usually billed by the other provider. It is not the $0 setup.

`LISTING_LLM_POLISH` defaults off. Set it to `1` to rewrite drafts with the same provider. Titles are cut back to the platform limit afterward. If the rewrite fails, the rule-based draft is kept.

## What the reading will not invent

- Measurements, unless the reading marks a ruler or tape visible in a specific photo you uploaded. Mentioning a ruler in the notes does not count, and neither does a photo index that is not one of those photos. A marked ruler photo can fill pit to pit and length with the inches it shows. Anything else stays blank and is flagged.
- Brand, size, or material when the tag is not readable.
- A condition grade when the photos do not support one.
- A price. Enter a target asking price, or a cost basis plus a condition. A cost-basis price is `cost × markup` from `config/fees.yaml`, rounded to the nearest dollar. It is not a sold comp.

Medium-confidence readings are filled and flagged. Low-confidence readings are discarded and shown under "Readings left blank" so you can type them yourself.

## Fees

Rates live only in [`config/fees.yaml`](config/fees.yaml). Each draft shows the fee, the net, and the arithmetic.

Assumptions, US seller, checked 28 October 2026:

| Platform | What the file uses |
| --- | --- |
| eBay | 13.6% of item + buyer-paid shipping + sales tax, up to $7,500, then 2.35% on the rest, plus $0.30 / $0.40 per order. Athletic shoes at $150+ are 8% with no per-order fee. Handbags are 15% up to $2,000. No Store subscription. |
| Poshmark | $2.95 under $15, 20% at $15 and above, on the item price. |
| Depop | US selling fee $0. Processing is 3.3% + $0.45 on item + shipping + tax. Boost is not included. |
| Mercari | 10% of item + buyer-paid shipping. |
| Whatnot | 8% of the item price, plus 2.9% + $0.30 processing on item + shipping + tax. Some categories are lower. |
| Facebook Marketplace | Local pickup is $0. Shipped checkout uses `shipped_percent` (currently 10%) of item + shipping + tax, with `shipped_minimum` (currently $0.80). **Verify that shipped rate.** Public 2026 writeups disagree, often 5% versus 10% with a minimum. |

The Facebook note is repeated on every Facebook fee quote. Change the numbers in the YAML when you confirm the current checkout rate. Leave local pickup selected unless the buyer will pay through Facebook shipping.

Buyer-paid shipping and sales tax are optional form fields. Leave them blank and the fee base uses zeros, and the quote says so. Net is the item price minus fees. Shipping the buyer paid, and sales tax, are not treated as profit.

## Export contract

A crosslisting app can import the JSON as-is.

- Schema: [`schema/listing.v1.schema.json`](schema/listing.v1.schema.json)
- Field guide: [`docs/export-format.md`](docs/export-format.md)

Every JSON export is validated against that schema before it is written. `schema_version` is `1.0.0`. `listings` always contains `ebay`, `poshmark`, `depop`, `mercari`, `whatnot`, and `facebook_marketplace`.

## Layout

```
app.py                          Streamlit entry
listing_generator/              Drafting, fees, vision, export
config/fees.yaml                The only fee rates
schema/listing.v1.schema.json   Export contract
docs/export-format.md           Contract field guide
tests/                          Title limits, fee math, vision mocks, schema
```

Listing copy, fees, titles, and the vision parser are classes with static methods. The vision providers are a small interface: `GeminiVisionProvider` by default, `OpenAICompatibleVisionProvider` as an option, and `MockVisionProvider` for tests and the offline demo.
