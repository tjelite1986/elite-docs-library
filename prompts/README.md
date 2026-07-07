# Prompts

Reusable prompts for LLMs and AI tools — system prompts, task templates, and
prompt patterns that have proven useful.

## Index

| Prompt | Description |
|--------|-------------|
| [Beginner guide writer](beginner-guide-writer.md) | Turn a working setup (configs, compose files, notes) into a self-contained beginner guide — the pattern behind the guides in this repo. |
| [Structured data from OCR](structured-data-from-ocr.md) | Extract strict JSON from noisy OCR text (receipts, invoices): integer minor-unit money, no hallucinated fields, self-checking against the printed total. |
| [Multi-LLM council synthesis](multi-llm-synthesis.md) | Merge independent answers from several models into one best answer — surfacing disagreements and ruling on them instead of averaging them away. |
| [Sanitize for public release](sanitize-for-public.md) | Pre-publication review pass that hunts credentials, real hostnames, identities, and sneaky identifiers in docs about to go public. |

## Conventions

- One prompt per file, named after what it does (e.g. `code-review.md`).
- Each file starts with a short "What it's for / how to use it" section,
  followed by the prompt itself in a fenced code block for easy copying.
