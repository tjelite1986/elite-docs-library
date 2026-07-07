# Sanitize internal docs for public release

## What it's for

Preparing internal material — configs, runbooks, guides written against your
real environment — for publication in a public repo. The failure mode it
guards against: a document that *looks* clean but still leaks a real hostname
in a code block, a token in an example command, or an internal URL in a
troubleshooting table.

This is the checklist used on every guide in this repository.

## How to use

Run it as a review pass over a finished document, with a capable model. Also
worth running on your own writing — the author is the worst person at spotting
their own leaks, because everything looks normal to them.

## The prompt

```text
Review the document below as a pre-publication security and privacy check. It
was written against a real, private environment and is about to be published
in a public repository. Find everything that ties it to that environment.

Hunt for, everywhere — prose, code blocks, tables, comments, URLs, example
output:

1. Credentials in any form: passwords, API keys/tokens, password hashes
   (bcrypt/PBKDF2 strings), private keys, session cookies, connection strings.
   Hashes count — they invite offline cracking.
2. Real identities: usernames, real names, email addresses, account handles.
3. Real infrastructure: domains and subdomains, public IPs, internal hostnames,
   machine names, filesystem paths containing a username (/home/<name>/...).
   Private LAN IPs are lower risk but should still be normalized to
   documentation examples (192.168.1.10).
4. Identifiers that look opaque but are real: cloud resource IDs, spreadsheet
   or document IDs in URLs, service-account emails, OAuth client IDs, UUIDs
   copied from a live system.
5. Context leaks in prose: references to internal projects, other private
   services, or organizational details a public reader shouldn't learn.
6. Legally or reputationally risky references (for example, naming specific
   piracy services) — flag them; the author decides.

For each finding report: the exact text, where it appears, why it matters, and
a suggested replacement (PUT_YOUR_API_KEY_HERE, example.com, 192.168.1.10,
youruser — matching the document's existing placeholder style).

Then check the placeholders themselves: every placeholder must be OBVIOUSLY
fake. A realistic-looking example key is a finding, not a solution — readers
copy examples verbatim, and secret scanners flag them.

End with a verdict: SAFE TO PUBLISH or NEEDS CHANGES, plus a one-line summary.
Do not rewrite the document; report findings only.

Document:
[PASTE DOCUMENT HERE]
```
