# Structured data from OCR text

## What it's for

Extracting reliable, machine-usable JSON from noisy OCR output — receipts,
invoices, scanned forms. Developed for a receipt scanner where a cheap model
(Claude Haiku class) parses supermarket receipts for well under a cent each.

The hard-won rules are in the prompt: integers for money (never floats), no
guessing on unreadable fields, and OCR-error tolerance without hallucination.

## How to use

Use as the user message in an API call, with the OCR text substituted in.
Pair it with your platform's structured-output / JSON-schema mode so the shape
is enforced by the API rather than by hope. Two schema gotchas worth knowing:

- Money as **integer minor units** (cents/öre). Floats invite `19.999999` bugs
  downstream.
- If a nullable field has a fixed set of values, some structured-output
  implementations reject `enum` combined with a nullable type — drop the
  `enum` and state the allowed values in the field's `description` instead.

## The prompt

```text
You are a data-extraction engine. Below is raw OCR text from a receipt. OCR
output is noisy: characters are misread, columns collapse, and line order can
be wrong. Extract what the receipt actually says into the JSON schema you have
been given.

Rules:

1. Extract, never invent. Every item in your output must correspond to a line
   in the OCR text. If you cannot read a value, use null — do not guess a
   plausible value.
2. All monetary amounts are INTEGERS in minor units (cents / öre): 12.50 → 1250.
3. Tolerate OCR noise when the correction is unambiguous: "M1LK" is "MILK",
   a price read as "l2.50" is 12.50. If a correction would be a guess between
   several plausible readings, prefer null.
4. Distinguish product lines from non-product lines: discounts, deposit fees,
   subtotals, VAT summaries, loyalty points, and payment lines are NOT
   products. Attach discounts to the item they follow when the receipt format
   makes that clear.
5. Quantity lines ("3 x 4.95") multiply out: quantity 3, unit_price 495,
   total 1485. When unit price and total disagree, trust the total.
6. Validate against the receipt's own total when present: if your item totals
   plus fees minus discounts do not sum to the printed total, re-examine the
   lines you were least sure about before answering.
7. Dates in ISO 8601 (YYYY-MM-DD). Times as HH:MM, 24-hour.
8. The store name is usually in the first lines; normalize obvious chain names
   to their common form, keep unknown stores exactly as printed.

OCR text:
[PASTE OCR TEXT HERE]
```
