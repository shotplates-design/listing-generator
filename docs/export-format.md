# Export format v1

A crosslisting app imports this document as-is. Do not scrape the Streamlit page. Read the JSON file from **Download JSON** or from `python -m listing_generator generate --format json`.

| | |
| --- | --- |
| Schema | [`schema/listing.v1.schema.json`](../schema/listing.v1.schema.json) |
| Version | `1.0.0` (`schema_version`) |
| Validator | JSON Schema draft 2020-12. This app rejects a document that does not match before writing it. |

`schema_version` stays `1.0.0` until a breaking change. Adding or removing a required field, including a marketplace key, is breaking: publish `schema/listing.v2.schema.json` and bump the constant. The v1 file already requires all six marketplaces.

Money is a decimal string with two fraction digits (`"40.00"`, `"-1.95"`) or `null`. There are no currency symbols and no thousands separators on those fields. The prose `formula` may contain `$` and commas. Currency is USD.

Empty strings and `null` amounts mean the fact is unknown. They are not guesses. Measurements the model tried to estimate are listed under `discarded` and are not copied into `attributes.measurements` or into descriptions.

## Top level

| Field | Meaning |
| --- | --- |
| `schema_version` | Always `"1.0.0"` for this file. |
| `item_id` | Stable id for this draft. The CLI `--item-id` flag sets it; otherwise it is a UUID. |
| `created_at` | UTC timestamp, ISO-8601, from when the export was built. |
| `fee_schedule_as_of` | The `as_of` date in `config/fees.yaml`. |
| `photos` | References only. Bytes are not embedded. |
| `attributes` | Confirmed facts after you edit the form. |
| `field_confidence` | `high`, `medium`, `low`, `none`, or `user` for every attribute. |
| `field_flags` | Short warnings for fields that were blanked or only partly read. Absent keys had no warning. |
| `discarded` | Readings the parser refused. Safe to ignore. Do not treat `value` as a fact. |
| `review_notes` | Seller reminders. Not buyer-facing copy. |
| `pricing_inputs` | The numbers and Facebook fulfillment used for the fee math. |
| `listings` | One object per marketplace. |

### `photos[]`

| Field | Meaning |
| --- | --- |
| `path_or_url` | Path you passed on the CLI, or the uploaded filename. The importer resolves it. |
| `role` | `front`, `back`, `tag`, `flaw`, or `detail`. |
| `order` | Integer, starting at 0. |

### `attributes`

| Field | Meaning |
| --- | --- |
| `brand`, `category`, `size_tag`, `color`, `material`, `style` | Strings. `category` is the item type (`hoodie`), not the marketplace category. |
| `department` | `""`, `mens`, `womens`, `unisex`, `boys`, `girls`, or `kids`. |
| `condition` | `""`, `new_with_tags`, `new_without_tags`, `excellent`, `good`, `fair`, or `poor`. |
| `measurements` | Object of strings the seller typed, such as `{"pit_to_pit": "22 in"}`. `{}` when none were provided. |
| `flaws` | Array of strings, one per line from the form. `[]` when none were confirmed. |

### `pricing_inputs`

| Field | Meaning |
| --- | --- |
| `cost_basis`, `target_price`, `buyer_paid_shipping`, `sales_tax` | Money strings or `null`. |
| `facebook_fulfillment` | `local_pickup` or `shipped`. Other marketplaces ignore it. |

`local_pickup` prices the Facebook draft at a $0 selling fee. `shipped` applies `shipped_percent` and `shipped_minimum` from `config/fees.yaml`. That shipped rate is a placeholder. Every Facebook fee object includes a note that starts with `Verify`.

### `listings`

Keys, all required: `ebay`, `poshmark`, `depop`, `mercari`, `whatnot`, `facebook_marketplace`.

Each value:

| Field | Meaning |
| --- | --- |
| `display_name` | Human name, such as `Facebook Marketplace`. |
| `title`, `title_limit` | Title and the cap it was cut to. Facebook's cap is 100. eBay, Poshmark, and Mercari are 80. Depop's opening line is capped at 80 by this app. Whatnot's show card is capped at 40. |
| `description`, `description_limit` | Plain description for Facebook: no hashtags. Depop puts hashtags at the end of its own description. |
| `tags`, `tags_label` | Depop hashtags, Poshmark style tags, Mercari keywords, Whatnot attribute lines. eBay and Facebook use an empty `tags` array. |
| `category_suggestion`, `category_note` | A path to confirm in the app. Not a live category id. |
| `item_specifics` | eBay name/value pairs, or Facebook's `Condition` (`New`, `Used - Like New`, `Used - Good`, `Used - Fair`). |
| `missing_specifics` | Names of specifics that were left blank. |
| `price` | Asking price string, or `null` when no target or cost-basis price was set. The same asking price is used on every platform. |
| `price_rationale` | Why that price was chosen, including condition and that platform's fee. |
| `equalized_price`, `equalized_note` | List price that would net the same as the highest net at the shared asking price. `null` and `""` when there is no asking price. |
| `fees` | Fee object, or `null` when `price` is `null`. |
| `net` | Item price minus fees, or `null`. |
| `checklist` | Seller reminders. Do not paste this block to buyers. |
| `polish` | `off`, `applied`, or `fallback`. |

`fees` when present:

| Field | Meaning |
| --- | --- |
| `currency` | `USD`. |
| `fee_base` | Amount the percentage was applied to. |
| `total` | Fee deducted from the item price. |
| `formula` | The arithmetic in one paragraph. |
| `lines` | `{label, amount}` rows that add up to `total`. |
| `notes` | Assumptions. Facebook always includes the verify note from `config/fees.yaml`. |

Facebook condition labels inside `item_specifics.Condition` and the description:

| Confirmed condition | Facebook label |
| --- | --- |
| `new_with_tags` | New |
| `new_without_tags`, `excellent` | Used - Like New |
| `good` | Used - Good |
| `fair`, `poor` | Used - Fair |

`poor` still says the seller grade is Poor in the description. Facebook has no poorer label, and the draft does not pretend the item is in better shape.

## Example shape

```json
{
  "schema_version": "1.0.0",
  "item_id": "8f1c0a2e-7b34-4d1a-9c55-0b6e2a9d4f10",
  "created_at": "2026-10-28T13:00:00Z",
  "fee_schedule_as_of": "2026-10-28",
  "photos": [
    {"path_or_url": "photos/front.jpg", "role": "front", "order": 0}
  ],
  "attributes": {
    "brand": "Nike",
    "category": "hoodie",
    "size_tag": "M",
    "measurements": {},
    "color": "navy",
    "material": "cotton blend",
    "condition": "good",
    "flaws": ["Small hole near the left hem"],
    "style": "90s athletic",
    "department": "mens"
  },
  "field_confidence": {
    "brand": "high",
    "category": "high",
    "size_tag": "high",
    "measurements": "none",
    "color": "high",
    "material": "medium",
    "condition": "user",
    "flaws": "high",
    "style": "medium",
    "department": "user"
  },
  "field_flags": {
    "measurements": "Left blank. Measurements cannot be read from photos."
  },
  "discarded": [],
  "review_notes": [],
  "pricing_inputs": {
    "cost_basis": "18.00",
    "target_price": "40.00",
    "buyer_paid_shipping": null,
    "sales_tax": null,
    "facebook_fulfillment": "local_pickup"
  },
  "listings": {
    "ebay": {},
    "poshmark": {},
    "depop": {},
    "mercari": {},
    "whatnot": {},
    "facebook_marketplace": {
      "display_name": "Facebook Marketplace",
      "title": "Nike Men's Hoodie Size M Navy",
      "title_limit": 100,
      "description": "Nike men's hoodie in navy, size M.\n\nMeasurements\nNot included.\n\nCondition\nUsed - Good. Small hole near the left hem.\n\nPhotos are of the actual item.",
      "description_limit": 5000,
      "tags": [],
      "tags_label": "Tags",
      "category_suggestion": "Apparel & accessories > Men's clothing > Hoodies & Sweatshirts",
      "category_note": "Confirm this category in the app. It is a suggestion, not a live category id.",
      "item_specifics": {"Condition": "Used - Good"},
      "missing_specifics": [],
      "price": "40.00",
      "price_rationale": "Drafted at the target price. Local pickup fee is $0.00. Verify the shipped rate before offering shipping.",
      "equalized_price": "40.00",
      "equalized_note": "At this asking price, this platform ties for the highest net.",
      "fees": {
        "currency": "USD",
        "fee_base": "40.00",
        "total": "0.00",
        "formula": "Fulfillment is local pickup. Selling fee $0.00.",
        "lines": [{"label": "Local pickup selling fee", "amount": "0.00"}],
        "notes": ["Verify this shipped selling fee before you rely on it."]
      },
      "net": "40.00",
      "checklist": ["Copy the draft into the marketplace yourself. This app does not post listings."],
      "polish": "off"
    }
  }
}
```

The skeleton above shows the Facebook object. A real file fills every marketplace the same way and will fail validation if any of `ebay`, `poshmark`, `depop`, `mercari`, or `whatnot` is missing. `pytest` builds full documents and checks them against the schema, including a shipped Facebook quote (`10%` of a $40 item is a $4.00 fee and a $36.00 net, with the verify note attached).

Set `facebook_fulfillment` to `shipped` before generating if the crosslisting app should price Facebook checkout instead of pickup.
