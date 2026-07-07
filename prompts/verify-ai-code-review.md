# Verify AI code-review findings

## What it's for

LLM code reviewers are excellent at *generating* findings and mediocre at
*being right about them* — in practice, a large share of HIGH-severity
findings from an AI review are false positives that pattern-match a known
vulnerability class but ignore the actual semantics of the code (a "SQL
date-range bug" that is correct because the column is lexicographic TEXT; a
"forgeable token" that is server-signed; a "timezone bug" in code that never
crosses timezones).

This prompt is the second pass: it takes a review's findings and
adversarially verifies each one against the real code before you act on any
of them. Applying an AI review without this step is how correct code gets
"fixed" into broken code.

## How to use

Run after any AI code review (your own model's or an external one). Give the
verifier the findings plus the actual source files touched. Best with a
strong model — verification is harder than finding.

## The prompt

```text
You are a verification engineer. Below are findings from an automated code
review, followed by the relevant source code. Your job is NOT to find new
issues — it is to determine, for each finding, whether it is REAL or a FALSE
POSITIVE.

For each finding:

1. Restate the claim in one sentence: what exactly would go wrong, under
   what input or state?
2. Trace the actual code path. Quote the specific lines that confirm or
   refute the claim. A finding is only CONFIRMED if you can describe a
   concrete scenario (inputs, state) that produces the wrong behavior.
3. Actively look for the reasons the code is correct anyway. Typical
   false-positive patterns to check before confirming:
   - The "bug" is guarded elsewhere: validation upstream, a database
     constraint, middleware, type narrowing, an earlier early-return.
   - The claim assumes semantics the code doesn't have (timezone conversion
     that never happens, string comparison that is intentionally
     lexicographic, user input that is actually server-generated).
   - The "vulnerability" requires an attacker capability that doesn't exist
     (forging a server-signed token, reaching an internal-only endpoint).
   - The reviewer misread which variable/branch is live at that point.
4. Verdict: CONFIRMED / FALSE POSITIVE / CANNOT VERIFY (say what code or
   context you'd need).
5. For CONFIRMED findings only: the minimal fix, and whether the fix risks
   breaking anything else.

Rules:
- Default to skepticism. The burden of proof is on the finding: if you
  cannot construct a failing scenario from the actual code, it is not
  confirmed.
- Never soften a verdict to be polite to the original reviewer.
- If two findings contradict each other, say so.
- End with a summary table: finding → verdict → one-line reason, and a
  count (X confirmed / Y false positives / Z unverifiable).

The findings:
[PASTE REVIEW FINDINGS HERE]

The code:
[PASTE THE RELEVANT SOURCE FILES HERE]
```
