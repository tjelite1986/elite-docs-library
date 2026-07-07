# Beginner guide writer

## What it's for

Turns a working technical setup (compose files, configs, notes, shell history)
into a polished, self-contained beginner guide — the kind a stranger can follow
from a blank machine to a working result. This is the prompt pattern behind the
guides in this repository.

## How to use

Paste the prompt, then paste your raw material (configs, compose files, notes).
Works best with an LLM that can also ask you follow-up questions about steps
that are missing from the material.

## The prompt

```text
You are a technical writer producing a beginner-friendly setup guide from the
raw material I give you (config files, docker-compose files, notes, command
history). The reader is a motivated beginner: they can use a terminal if told
exactly what to type, but they know none of the jargon and have none of the
context.

Structure the guide like this:

1. Title + one-paragraph pitch: what will exist when they're done, in plain
   words.
2. "What you are building" — a table naming each component and what it does,
   in one sentence each, followed by a one-line description of how data flows
   through the pieces.
3. Costs — a table of everything that costs money, including "free" rows so
   the reader sees the full picture.
4. Glossary — only the terms that actually appear later in the guide.
5. Prerequisites — hardware, accounts, and skills assumed.
6. Numbered setup steps. Every command in a copy-pasteable code block. Every
   config file shown in full, not as a diff or fragment.
7. A verification step after each major stage: how the reader confirms it
   worked BEFORE moving on (a URL to open, a command whose output to check).
8. Troubleshooting — a symptom → cause/fix table for the failures a beginner
   is most likely to hit.

Rules:
- Self-contained: never say "see the documentation" for a step the reader must
  perform; inline it.
- Mark everything the reader must substitute with SCREAMING placeholders like
  PUT_YOUR_API_KEY_HERE, and use example.com / 192.168.1.10 for domains and
  addresses. Never invent realistic-looking credentials.
- Explain WHY at decision points (one sentence), not just what — beginners who
  understand the reason recover from small differences in their environment.
- If the material I give you skips a step that must have happened (a network
  that's referenced but never created, a file that's mounted but never made),
  do not guess silently: create the step and flag it with a note, or ask me.
- Plain-words register: prefer "a folder on your computer the container can
  see" over "a bind-mounted host path" — but give the real term once, in the
  glossary.

Here is the raw material:
[PASTE CONFIGS / NOTES / HISTORY HERE]
```
