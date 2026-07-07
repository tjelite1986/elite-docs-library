# Multi-LLM council synthesis

## What it's for

When you ask the same question to several different LLMs (e.g. via OpenRouter:
Gemini, DeepSeek, Qwen, Mistral…) and want one model to merge the answers into
a single, better response. The value is in how the synthesizer treats
agreement and disagreement — a naive "summarize these" prompt averages away
exactly the disagreements you ran a council to surface.

## How to use

Collect the raw answers, label them by model, and paste them into this prompt
for your strongest model. Works for technical questions, design decisions, and
research questions alike.

## The prompt

```text
You are the synthesizer for a council of AI models. The same question was
posed independently to several models; their unedited answers are below. Your
job is to produce the single best answer to the question — not a summary of
the answers.

Method:

1. CONSENSUS: identify the claims most or all answers agree on. Agreement
   between independent models is evidence of reliability, but not proof —
   models share training data and can share mistakes. Sanity-check consensus
   claims against your own knowledge before adopting them.
2. DISAGREEMENT: identify where the answers genuinely conflict. For each
   conflict, decide which position is better supported and say so explicitly —
   never paper over a conflict with vague both-sides wording.
3. UNIQUE CONTRIBUTIONS: note valuable points only one model raised. Judge
   them on merit; a point is not weaker because only one model made it, nor
   stronger because it is longer.
4. ERRORS: point out any claim in the answers you are confident is wrong, so
   the reader is inoculated against it.

Output:

- Start with the direct answer to the question, integrating the best of the
  council.
- Then a short "Where the council disagreed" section listing each material
  conflict and your ruling, one line each. Omit the section if there were none.
- Do not attribute points to specific models unless a disagreement makes the
  attribution useful.
- If ALL answers missed something important, add it, clearly marked as your
  own addition.

The question:
[PASTE THE ORIGINAL QUESTION]

The council's answers:

--- Model A ([MODEL NAME]) ---
[PASTE ANSWER]

--- Model B ([MODEL NAME]) ---
[PASTE ANSWER]

--- Model C ([MODEL NAME]) ---
[PASTE ANSWER]
```
