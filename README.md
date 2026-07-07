# Elite Docs Library

A public library of guides, prompts, and other reusable documentation —
distilled from a real self-hosting setup (Docker on a Raspberry Pi, Traefik,
CI-driven deploys) and polished so anyone can follow along from scratch.
Everything here is meant to be read directly on GitHub — each section has its
own `README.md` index, and every document is a standalone Markdown file.

## Sections

| Section | What's in it |
|---------|--------------|
| [guides/](guides/) | Step-by-step setup and how-to guides: reverse proxy with wildcard HTTPS, Next.js in Docker, auto-deploy pipelines, a simple NAS, self-hosted Obsidian sync, and a full streaming stack. |
| [prompts/](prompts/) | Reusable prompts for LLMs and AI tools: writing beginner guides, structured OCR extraction, multi-model answer synthesis, verifying AI code reviews, and pre-publication sanitization. |
| [scripts/](scripts/) | Small self-contained shell scripts: git auto-backup from cron, verified CI deploys, Docker disk hygiene. |

## Conventions

- One document per file, written in Markdown.
- Each section folder has a `README.md` listing its contents with a short
  description — start there.
- Documents are self-contained: placeholders like `PUT_YOUR_API_KEY_HERE` mark
  anything you need to fill in yourself. No document contains real credentials,
  private URLs, or machine-specific details.
- Every document passes a sanitization review before publication — the exact
  checklist is public: [prompts/sanitize-for-public.md](prompts/sanitize-for-public.md).
